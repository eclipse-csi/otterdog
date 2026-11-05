#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
The cards of the organizations of the projects pages (home/projects.html), built from what the dashboard stores about
them: their installation, their configuration, the statistics of their repositories, the pull requests of their
configuration repository, the last fetch of their configuration, their blueprints and their scorecards.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from itertools import groupby
from typing import TYPE_CHECKING, Any

from otterdog.webapp.db.models import BlueprintStatus, InstallationStatus, PullRequestStatus, TaskStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from otterdog.webapp.db.models import (
        ConfigurationModel,
        InstallationModel,
        PullRequestModel,
        StatisticsModel,
        TaskModel,
    )

# the share of the active repositories from which a protection is good, and from which it is partial
GOOD_SHARE = 80
PARTIAL_SHARE = 50

# the task fetching the configuration of an organization, the dashboard has none without it
FETCH_CONFIG_TASK = "FetchConfigTask"


@dataclasses.dataclass(frozen=True)
class Share:
    """The share of the active repositories of an organization with a protection, None without repositories."""

    label: str
    percentage: float | None

    @property
    def status(self) -> str:
        if self.percentage is None:
            return "unknown"
        if self.percentage >= GOOD_SHARE:
            return "good"
        if self.percentage >= PARTIAL_SHARE:
            return "warning"
        return "critical"


@dataclasses.dataclass(frozen=True)
class Fetch:
    """The last fetch of the configuration of an organization."""

    failed: bool
    at: datetime
    log: str | None


@dataclasses.dataclass(frozen=True)
class ProjectCard:
    project_name: str
    github_id: str
    group: str
    # configured, unconfigured (installed without configuration) or inactive (not installed or suspended)
    state: str
    status: InstallationStatus
    base_template: str | None
    defaults_version: str | None
    two_factor: bool | None = None
    workflow_permissions: str | None = None
    signoff: bool | None = None
    default_permission: str | None = None
    plan: str | None = None
    repositories: int | None = None
    archived: int | None = None
    shares: tuple[Share, ...] = ()
    open_pull_requests: int = 0
    fetch: Fetch | None = None
    failing_blueprints: int = 0
    scorecard: float | None = None

    @property
    def linked(self) -> bool:
        """Whether the card opens the page of the project, which needs its installation and its configuration."""
        return self.state == "configured"

    @property
    def security(self) -> float | None:
        """The mean of the shares of the repositories with each protection, to sort the organizations."""
        known = [share.percentage for share in self.shares if share.percentage is not None]
        return sum(known) / len(known) if known else None


def defaults_version(base_template: str | None) -> str | None:
    """The version of the default configuration, e.g. v0.15.0 of <url>#otterdog-defaults.libsonnet@v0.15.0."""
    fragment = base_template.partition("#")[2] if base_template else ""
    if "@" not in fragment:
        return None
    return fragment.rpartition("@")[2] or None


def ago(at: datetime, now: datetime) -> str:
    """How long ago a date was, e.g. 3 h ago, the dates stored by the database being in UTC."""
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    seconds = max(0, int((now - at).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def _shares(statistics: StatisticsModel | None) -> tuple[Share, ...]:
    labels = ("Branch protection", "Secret scanning", "Dependabot", "Code scanning")
    active = statistics.total_repos - statistics.archived_repos if statistics is not None else 0
    if statistics is None or active <= 0:
        return tuple(Share(label, None) for label in labels)

    # secret scanning and its push protection, Dependabot alerts and security updates count distinct repositories
    counts = (
        statistics.repos_with_branch_protection,
        statistics.repos_with_secret_scanning + statistics.repos_with_secret_scanning_push_protection,
        statistics.repos_with_dependabot_alerts + statistics.repos_with_dependabot_security_updates,
        statistics.repos_with_code_scanning,
    )
    return tuple(Share(label, count / active * 100) for label, count in zip(labels, counts, strict=True))


def project_card(
    installation: InstallationModel,
    configuration: ConfigurationModel | None,
    statistics: StatisticsModel | None,
    pull_requests: list[PullRequestModel],
    fetch_task: TaskModel | None,
    blueprint_counts: Mapping[str, int],
    scorecard: float | None,
) -> ProjectCard:
    installed = installation.installation_status == InstallationStatus.INSTALLED
    config: dict[str, Any] | None = configuration.config if configuration is not None else None
    state = "inactive" if not installed else ("configured" if config is not None else "unconfigured")
    project_name = installation.project_name or installation.github_id

    facts: dict[str, Any] = {}
    if config is not None:
        settings = config.get("settings", {})
        repositories = config.get("repositories", [])
        facts = {
            "two_factor": settings.get("two_factor_requirement"),
            "workflow_permissions": settings.get("workflows", {}).get("default_workflow_permissions"),
            "signoff": settings.get("web_commit_signoff_required"),
            "default_permission": settings.get("default_repository_permission"),
            "plan": settings.get("plan"),
            "repositories": len(repositories),
            "archived": sum(1 for repository in repositories if repository.get("archived")),
        }

    fetch = (
        Fetch(fetch_task.status == TaskStatus.FAILED, fetch_task.updated_at, fetch_task.log)
        if fetch_task is not None
        else None
    )

    return ProjectCard(
        project_name=project_name,
        github_id=installation.github_id,
        group=project_name.split(".")[0],
        state=state,
        status=installation.installation_status,
        base_template=installation.base_template,
        defaults_version=defaults_version(installation.base_template),
        shares=_shares(statistics),
        open_pull_requests=sum(1 for x in pull_requests if x.status == PullRequestStatus.OPEN),
        fetch=fetch,
        failing_blueprints=blueprint_counts.get(BlueprintStatus.FAILURE.value, 0),
        scorecard=scorecard,
        **facts,
    )


def project_cards(
    installations: Iterable[InstallationModel],
    configurations: Mapping[str, ConfigurationModel],
    statistics: Mapping[str, StatisticsModel],
    pull_requests: Iterable[PullRequestModel],
    fetch_tasks: Mapping[str, TaskModel],
    blueprint_counts: Mapping[str, Mapping[str, int]],
    scorecards: Mapping[str, float],
) -> list[ProjectCard]:
    """The cards of the organizations, sorted by their project."""
    pull_requests_by_organization: dict[str, list[PullRequestModel]] = {}
    for pull_request in pull_requests:
        pull_requests_by_organization.setdefault(pull_request.id.org_id, []).append(pull_request)

    cards = [
        project_card(
            installation,
            configurations.get(installation.github_id),
            statistics.get(installation.github_id),
            pull_requests_by_organization.get(installation.github_id, []),
            fetch_tasks.get(installation.github_id),
            blueprint_counts.get(installation.github_id, {}),
            scorecards.get(installation.github_id),
        )
        for installation in installations
    ]
    return sorted(cards, key=lambda card: card.project_name)


def group_cards(cards: list[ProjectCard]) -> list[tuple[str, list[ProjectCard]]]:
    """The cards by their top-level project, e.g. ecd for ecd.che, sorted by it."""
    ordered = sorted(cards, key=lambda card: (card.group, card.project_name))
    return [(group, list(members)) for group, members in groupby(ordered, key=lambda card: card.group)]


def now() -> datetime:
    return datetime.now(UTC)
