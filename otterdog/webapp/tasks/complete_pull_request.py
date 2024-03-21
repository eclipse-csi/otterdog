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
from otterdog.webapp.utils import get_admin_teams, get_full_admin_team_slugs


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

    async def _pre_execute(self) -> bool:
        self.logger.info(
            "completing pull request #%d on behalf of user '%s' for repo '%s/%s'",
            self.pull_request_number,
            self.author,
            self.org_id,
            self.repo_name,
        )

        pr_model = await find_pull_request(self.org_id, self.repo_name, self.pull_request_number)
        if pr_model is None:
            raise RuntimeError(
                f"failed to fetch pull request #{self.pull_request_number} in repo '{self.org_id}/{self.repo_name}'"
            )
        else:
            self._pr_model = pr_model

        if pr_model.status != PullRequestStatus.MERGED:
            self.logger.info(
                f"pull request #{self.pull_request_number} for repo '{self.org_id}/{self.repo_name}' "
                "is not merged yet, skipping"
            )
            return False

        if pr_model.apply_status == ApplyStatus.COMPLETED:
            self.logger.info(
                f"pull request #{self.pull_request_number} for repo '{self.org_id}/{self.repo_name}' "
                "is already applied, skipping"
            )
            return False

        rest_api = await self.rest_api
        admin_teams = get_admin_teams()
        is_admin = False
        for admin_team in admin_teams:
            if await rest_api.team.is_user_member_of_team(self.org_id, admin_team, self.author):
                is_admin = True
                break

        if not is_admin:
            comment = await render_template(
                "comment/wrong_team_done_comment.txt", admin_teams=get_full_admin_team_slugs(self.org_id)
            )
            await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.pull_request_number), comment)

            self.logger.error(
                f"apply for pull request #{self.pull_request_number} triggered by user '{self.author}' "
                f"who is not a member of the admin team, skipping"
            )

            return False

        return True

    async def _execute(self) -> None:
        self._pr_model.apply_status = ApplyStatus.COMPLETED
        await update_pull_request(self._pr_model)

        comment = await render_template("comment/done_comment.txt")
        rest_api = await self.rest_api
        await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.pull_request_number), comment)

    def __repr__(self) -> str:
        return f"CompletePullRequestTask(repo={self.org_id}/{self.repo_name}, pull_request=#{self.pull_request_number})"
