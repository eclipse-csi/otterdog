#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import update_or_create_pull_request
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.webhook.github_models import PullRequest


@dataclass(repr=False)
class UpdatePullRequestTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    pull_request: PullRequest

    @property
    def pull_request_number(self) -> int:
        return self.pull_request.number

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _pre_execute(self) -> None:
        self.logger.info(
            "updating pull request #%d of repo '%s/%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )

    async def _execute(self) -> None:
        await update_or_create_pull_request(
            self.org_id,
            self.repo_name,
            self.pull_request,
        )

    def __repr__(self) -> str:
        return f"UpdatePullRequestTask(repo={self.org_id}/{self.repo_name}, pull_request=#{self.pull_request_number})"
