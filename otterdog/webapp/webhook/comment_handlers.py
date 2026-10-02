#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from enum import StrEnum
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar

from quart import current_app

from otterdog.utils import LogLevel, unwrap

if TYPE_CHECKING:
    from re import Match, Pattern

    from otterdog.webapp.tasks import Task
    from otterdog.webapp.webhook import IssueCommentEvent


class CommentScope(StrEnum):
    """Where a comment command is accepted."""

    # only on pull requests of the configuration repository, the default
    CONFIG_REPO_PULL_REQUEST = "config_repo_pull_request"
    # on pull requests of any repository of the organization, e.g. remediation PRs of blueprints
    PULL_REQUEST = "pull_request"
    # on issues and pull requests of any repository of the organization
    ANY = "any"


class CommentHandler(ABC):
    @property
    def scope(self) -> CommentScope:
        return CommentScope.CONFIG_REPO_PULL_REQUEST

    def applies_to(self, is_pull_request: bool, is_config_repo: bool) -> bool:
        match self.scope:
            case CommentScope.CONFIG_REPO_PULL_REQUEST:
                return is_pull_request and is_config_repo
            case CommentScope.PULL_REQUEST:
                return is_pull_request
            case CommentScope.ANY:
                return True

    @cached_property
    def pattern(self) -> Pattern:
        return self._create_pattern()

    @abstractmethod
    def _create_pattern(self) -> Pattern:
        pass

    def matches(self, comment: str) -> Match | None:
        return self.pattern.match(comment)

    @abstractmethod
    def process(self, match: Match, event: IssueCommentEvent) -> None:
        pass

    @staticmethod
    def schedule_task(task: Task) -> None:
        current_app.add_background_task(task)


class HelpCommentHandler(CommentHandler):
    def _create_pattern(self) -> re.Pattern:
        return re.compile(r"/otterdog\s+help")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.help_comment import HelpCommentTask

        self.schedule_task(
            HelpCommentTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
            )
        )


class TeamInfoCommentHandler(CommentHandler):
    def _create_pattern(self) -> re.Pattern:
        return re.compile(r"/otterdog\s+team-info")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.retrieve_team_membership import (
            RetrieveTeamMembershipTask,
        )

        self.schedule_task(
            RetrieveTeamMembershipTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
            )
        )


class CheckSyncCommentHandler(CommentHandler):
    def _create_pattern(self) -> re.Pattern:
        return re.compile(r"/otterdog\s+check-sync")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.check_sync import CheckConfigurationInSyncTask

        self.schedule_task(
            CheckConfigurationInSyncTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
            )
        )


class DoneCommentHandler(CommentHandler):
    def _create_pattern(self) -> re.Pattern:
        return re.compile(r"/otterdog\s+done")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.complete_pull_request import CompletePullRequestTask

        self.schedule_task(
            CompletePullRequestTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
                event.sender.login,
            )
        )


class ApplyCommentHandler(CommentHandler):
    def _create_pattern(self) -> re.Pattern:
        return re.compile(r"/otterdog\s+apply")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.apply_changes import ApplyChangesTask

        self.schedule_task(
            ApplyChangesTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
                event.sender.login,
            )
        )


class MergeCommentHandler(CommentHandler):
    def _create_pattern(self) -> re.Pattern:
        return re.compile(r"/otterdog\s+merge")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.merge_pull_request import MergePullRequestTask

        self.schedule_task(
            MergePullRequestTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
                event.sender.login,
            )
        )


class ValidateCommentHandler(CommentHandler):
    def _create_pattern(self) -> re.Pattern:
        return re.compile(r"/otterdog\s+validate(\s+info)?")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.validate_pull_request import ValidatePullRequestTask

        log_level_str = match.group(1)
        log_level = LogLevel.WARN

        if log_level_str is not None and log_level_str.strip() == "info":
            log_level = LogLevel.INFO

        self.schedule_task(
            ValidatePullRequestTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
                log_level,
            )
        )


class RecheckCommentHandler(CommentHandler):
    """`/otterdog recheck [<blueprint-id>]`: force an evaluation of blueprints."""

    @property
    def scope(self) -> CommentScope:
        return CommentScope.ANY

    def _create_pattern(self) -> re.Pattern:
        return re.compile(r"/otterdog\s+recheck(?:\s+(?P<blueprint_id>[\w.-]+))?\s*$")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.blueprints.recheck import RecheckBlueprintsTask

        self.schedule_task(
            RecheckBlueprintsTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
                event.sender.login,
                match.group("blueprint_id"),
            )
        )


class RemediationCommandHandler(CommentHandler, ABC):
    """Base for commands acting on a remediation pull request of a blueprint."""

    @property
    def scope(self) -> CommentScope:
        return CommentScope.PULL_REQUEST

    @property
    @abstractmethod
    def command(self) -> str: ...

    def _create_pattern(self) -> re.Pattern:
        return re.compile(rf"/otterdog\s+{self.command}\s*$")

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.blueprints.remediation_command import RemediationCommand, RemediationCommandTask

        self.schedule_task(
            RemediationCommandTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
                event.sender.login,
                RemediationCommand(self.command),
            )
        )


class RebaseCommentHandler(RemediationCommandHandler):
    """`/otterdog rebase`: bring the remediation branch up to date and rewrite the blueprint's files."""

    @property
    def command(self) -> str:
        return "rebase"


class RecreateCommentHandler(RemediationCommandHandler):
    """`/otterdog recreate`: recreate the remediation branch and reuse or reopen the pull request."""

    @property
    def command(self) -> str:
        return "recreate"


class IgnoreCommentHandler(RemediationCommandHandler):
    """`/otterdog ignore`: dismiss the blueprint for this repository explicitly."""

    @property
    def command(self) -> str:
        return "ignore"


class StatusCommentHandler(CommentHandler):
    """`/otterdog status [<blueprint-id>] [--workflow <name>] [--label <label>] [--status <status>]`."""

    _OPTIONS: ClassVar[re.Pattern] = re.compile(r"--(workflow|label|status)\s+(\S+)")

    @property
    def scope(self) -> CommentScope:
        return CommentScope.ANY

    def _create_pattern(self) -> re.Pattern:
        return re.compile(
            r"/otterdog\s+status(?:\s+(?P<blueprint_id>[\w.-]+))?(?P<options>(?:\s+--(?:workflow|label|status)\s+\S+)*)\s*$"
        )

    @classmethod
    def parse_options(cls, options: str | None) -> dict[str, str]:
        return dict(cls._OPTIONS.findall(options or ""))

    def process(self, match: re.Match, event: IssueCommentEvent) -> None:
        from otterdog.webapp.tasks.blueprints.status_comment import BlueprintStatusCommentTask

        options = self.parse_options(match.group("options"))

        self.schedule_task(
            BlueprintStatusCommentTask(
                unwrap(event.installation).id,
                unwrap(event.organization).login,
                event.repository.name,
                event.issue.number,
                event.sender.login,
                match.group("blueprint_id"),
                options.get("workflow"),
                options.get("label"),
                options.get("status"),
            )
        )
