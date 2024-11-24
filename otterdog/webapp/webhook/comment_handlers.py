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
from functools import cached_property
from typing import TYPE_CHECKING

from quart import current_app

from otterdog.utils import LogLevel, unwrap

if TYPE_CHECKING:
    from re import Match, Pattern

    from otterdog.webapp.tasks import Task
    from otterdog.webapp.webhook import IssueCommentEvent


class CommentHandler(ABC):
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
