#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from logging import getLogger
from typing import Any

from odmantic import EmbeddedModel, Field, Model

from otterdog.webapp.utils import current_utc_time

logger = getLogger(__name__)


class InstallationStatus(StrEnum):
    INSTALLED = "installed"
    NOT_INSTALLED = "not_installed"
    SUSPENDED = "suspended"

    def __str__(self) -> str:
        return self.name


class InstallationModel(Model):
    github_id: str = Field(primary_field=True)
    project_name: str | None = Field(unique=True, index=True)
    installation_id: int = Field(index=True, default=0)
    installation_status: InstallationStatus
    config_repo: str | None = None
    base_template: str | None = None
    approval_teams: str | None = None
    admin_teams: str | None = None


class TaskStatus(StrEnum):
    CREATED = "created"
    SCHEDULED = "scheduled"
    FINISHED = "finished"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.name


class TaskModel(Model):
    type: str = Field(index=True)
    org_id: str = Field(index=True)
    repo_name: str = Field(index=True)
    pull_request: int = 0
    status: TaskStatus = TaskStatus.CREATED
    log: str | None = None
    cache_stats: str = ""
    rate_limit_remaining: str = ""
    created_at: datetime = Field(index=True, default_factory=current_utc_time)
    updated_at: datetime = Field(default_factory=current_utc_time)


class ConfigurationModel(Model):
    github_id: str = Field(primary_field=True)
    project_name: str | None = Field(unique=True, index=True)
    config: dict
    sha: str


class PullRequestStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"

    def __str__(self) -> str:
        return self.name


class ApplyStatus(StrEnum):
    NOT_APPLIED = "not_applied"
    FAILED = "failed"
    PARTIALLY_APPLIED = "partially_applied"
    COMPLETED = "completed"

    def __str__(self) -> str:
        return self.name


class PullRequestId(EmbeddedModel):
    org_id: str
    repo_name: str
    pull_request: int


class PullRequestModel(Model):
    id: PullRequestId = Field(primary_field=True)
    draft: bool
    status: PullRequestStatus = Field(index=True)
    apply_status: ApplyStatus = Field(index=True, default=ApplyStatus.NOT_APPLIED)

    valid: bool | None = None
    in_sync: bool | None = None
    requires_manual_apply: bool | None = None
    supports_auto_merge: bool | None = None
    author_can_auto_merge: bool | None = None
    has_required_approvals: bool | None = None

    created_at: datetime = Field(index=True)
    updated_at: datetime = Field(index=True)

    closed_at: datetime | None = None
    merged_at: datetime | None = Field(index=True, default=None)

    async def automerge_problems(self, matching_teams: list[str] | None = None) -> list[str]:
        """
        matching_teams, when passed, is the list of team slugs in the org that were
        actually resolved (via the GitHub API) to match one of the entries in
        GITHUB_APPROVAL_TEAMS (or its per-organization override). Left as None when
        the caller didn't resolve it (e.g. a plain boolean check), in which case the
        raw patterns are shown instead of a concrete team name.
        """
        logger.debug(
            "automerge_problems for pull request '%s': status=%s, draft=%s, apply_status=%s, valid=%s, "
            "in_sync=%s, requires_manual_apply=%s, supports_auto_merge=%s, author_can_auto_merge=%s, "
            "has_required_approvals=%s, matching_teams=%s",
            self.id,
            self.status,
            self.draft,
            self.apply_status,
            self.valid,
            self.in_sync,
            self.requires_manual_apply,
            self.supports_auto_merge,
            self.author_can_auto_merge,
            self.has_required_approvals,
            matching_teams,
        )

        problems = []
        if self.status != PullRequestStatus.OPEN:
            return [f"pull request is {self.status.value}, only open pull requests can be managed"]
        if self.valid is None:
            return ["pull request has not been validated yet, run `/otterdog validate` first"]
        if self.valid is False:
            problems.append(
                "pull request is not valid, check the `/otterdog validate` comment for details and push a fix"
            )
        if self.supports_auto_merge is None:
            return ["it has not been checked whether the pull request supports auto merge"]
        if self.supports_auto_merge is False:
            problems.append(
                "pull request cannot be automatically merged  "
                "(contains secrets, requires web UI changes, includes deletions or touches non-configuration files)"
            )
        # If either is true, the pull request can be automerged
        # (author can auto merge without approvals, or it has the required approvals)
        if self.author_can_auto_merge is not True and self.has_required_approvals is not True:
            from quart import render_template

            from otterdog.webapp.utils import describe_admin_teams, describe_approval_teams

            team_description = await describe_approval_teams(matching_teams, self.id.org_id)
            admin_team_description = await describe_admin_teams(self.id.org_id)

            # auto-merge requires ONE of these two independent conditions to hold. None does
            # not mean "still pending / will resolve on its own" - it means the corresponding
            # event never happened, so say what needs to happen instead of "not checked yet".
            if self.has_required_approvals is None:
                approval_status = (
                    f"No approval from a member of `{team_description}` or of `{admin_team_description}` "
                    "has been submitted yet"
                )
            else:
                approval_status = (
                    f"No approval from a member of `{team_description}` or of `{admin_team_description}` was found"
                )

            if self.author_can_auto_merge is None:
                author_status = (
                    "The author's team membership is unknown "
                    "(comment `/otterdog team-info` on the pull request to refresh it)"
                )
            else:
                author_status = f"The author is not a member of `{team_description}` or of `{admin_team_description}`"

            problems.append(
                await render_template(
                    "comment/automerge_eligibility.txt",
                    team_description=team_description,
                    admin_team_description=admin_team_description,
                    approval_status=approval_status,
                    author_status=author_status,
                )
            )

        return problems

    async def can_be_automerged(self) -> bool:
        return not await self.automerge_problems()


class StatisticsModel(Model):
    project_name: str = Field(primary_field=True)
    github_id: str = Field(index=True)
    two_factor_enforced: int
    total_repos: int
    archived_repos: int
    repos_with_secret_scanning: int
    repos_with_secret_scanning_push_protection: int
    repos_with_branch_protection: int
    repos_with_dependabot_alerts: int
    repos_with_dependabot_security_updates: int
    repos_with_private_vulnerability_reporting: int


class UserModel(Model):
    node_id: str = Field(primary_field=True)
    username: str
    email: str | None = None
    full_name: str | None = None
    projects: list[str] = Field(default_factory=list)


class PolicyId(EmbeddedModel):
    org_id: str
    policy_type: str


class PolicyModel(Model):
    id: PolicyId = Field(primary_field=True)
    path: str
    name: str | None = None
    description: str | None = None
    config: dict


class PolicyStatusModel(Model):
    id: PolicyId = Field(primary_field=True)
    status: dict = Field(default_factory=dict)


class BlueprintId(EmbeddedModel):
    org_id: str
    blueprint_type: str
    blueprint_id: str


class BlueprintModel(Model):
    id: BlueprintId = Field(primary_field=True)
    path: str
    name: str | None = None
    description: str | None = None
    recheck_needed: bool = True
    last_checked: datetime | None = Field(index=True, default=None)
    config: dict


class BlueprintStatusId(EmbeddedModel):
    org_id: str
    repo_name: str
    blueprint_id: str


class BlueprintStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    SUCCESS = "success"
    FAILURE = "failure"
    REMEDIATION_PREPARED = "remediation_prepared"
    DISMISSED = "dismissed"
    RECHECK = "recheck"

    def __str__(self) -> str:
        return self.name


class BlueprintStatusModel(Model):
    id: BlueprintStatusId = Field(primary_field=True)

    updated_at: datetime = Field(index=True, default_factory=current_utc_time)
    status: BlueprintStatus = Field(default=BlueprintStatus.NOT_CHECKED)
    remediation_pr: int | None = Field(index=True, default=None)


class ScorecardId(EmbeddedModel):
    org_id: str
    repo_name: str


class ScorecardResultModel(Model):
    id: ScorecardId = Field(primary_field=True)

    updated_at: datetime = Field(index=True, default_factory=current_utc_time)
    score: float | None = None
    scorecard_version: str | None = None
    checks: list[dict[str, Any]] = Field(default_factory=list)
