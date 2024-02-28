#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from quart import render_template

from otterdog.webapp.db.models import ApplyStatus, PullRequestStatus, TaskModel
from otterdog.webapp.db.service import find_pull_request, update_pull_request
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import get_admin_team


@dataclass(repr=False)
class CompletePullRequestTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    pull_request_number: int
    author: str

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _pre_execute(self) -> None:
        self.logger.info(
            "completing pull request #%d on behalf of user '%s' for repo '%s/%s'",
            self.pull_request_number,
            self.author,
            self.org_id,
            self.repo_name,
        )

    async def _execute(self) -> None:
        pr_model = await find_pull_request(self.org_id, self.repo_name, self.pull_request_number)
        if pr_model is None:
            self.logger.warning(f"failed to find data for pull request #%d in repo '{self.org_id}/{self.repo_name}'")
            return

        if pr_model.status != PullRequestStatus.MERGED:
            return

        if pr_model.apply_status != ApplyStatus.PARTIALLY_APPLIED and pr_model.apply_status != ApplyStatus.FAILED:
            return

        rest_api = await self.rest_api
        admin_team = get_admin_team()
        if not await rest_api.team.is_user_member_of_team(self.org_id, admin_team, self.author):
            comment = await render_template("comment/wrong_team_done_comment.txt", admin_team=admin_team)
            await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.pull_request_number), comment)
            return

        pr_model.apply_status = ApplyStatus.COMPLETED
        await update_pull_request(pr_model)

        comment = await render_template("comment/done_comment.txt")
        await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.pull_request_number), comment)

    def __repr__(self) -> str:
        return f"CompletePullRequestTask(repo={self.org_id}/{self.repo_name}, pull_request=#{self.pull_request_number})"
