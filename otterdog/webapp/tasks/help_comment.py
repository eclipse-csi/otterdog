#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from quart import render_template

from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.webhook.github_models import PullRequest


@dataclass(repr=False)
class HelpCommentTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    pull_request_or_number: PullRequest | int

    @property
    def pull_request_number(self) -> int:
        return (
            self.pull_request_or_number
            if isinstance(self.pull_request_or_number, int)
            else self.pull_request_or_number.number
        )

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _pre_execute(self) -> bool:
        if isinstance(self.pull_request_or_number, PullRequest):
            if self.pull_request_or_number.user.type.lower() == "bot":
                self.logger.debug("not adding help comment for bot user '%s'", self.pull_request_or_number.user.login)
                return False

        return True

    async def _execute(self) -> None:
        self.logger.info(
            "adding help text to pull request #%d of repo '%s/%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )

        rest_api = await self.rest_api
        comment = await render_template("comment/help_comment.txt")

        await self.minimize_outdated_comments(
            self.org_id,
            self.repo_name,
            self.pull_request_number,
            "<!-- Otterdog Comment: help -->",
        )

        await rest_api.issue.create_comment(
            self.org_id,
            self.repo_name,
            str(self.pull_request_number),
            comment,
        )

    def __repr__(self) -> str:
        return f"HelpCommentTask(repo='{self.org_id}/{self.repo_name}', pull_request=#{self.pull_request_number})"
