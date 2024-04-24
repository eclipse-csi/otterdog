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
from otterdog.webapp.tasks import (
    InstallationBasedTask,
    Task,
    contains_valid_team_for_approval,
)
from otterdog.webapp.webhook.github_models import PullRequest, Review


@dataclass(repr=False)
class UpdatePullRequestTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    pull_request: PullRequest
    review: Review | None = None

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

    async def _execute(self) -> None:
        self.logger.info(
            "updating pull request #%d of repo '%s/%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )

        if self.review is not None:
            rest_api = await self.rest_api

            # check if the PR was approved by a team eligible for auto-merge
            reviews = await rest_api.pull_request.get_reviews(
                self.org_id, self.repo_name, str(self.pull_request_number)
            )

            approved_by_users = list(
                map(
                    lambda x: x["user"]["login"],
                    filter(lambda x: x["state"] == "APPROVED", reviews),
                )
            )

            self.logger.debug(f"approved by users: {approved_by_users}")

            graphql_api = await self.graphql_api
            approved_by_teams: set[str] = set()
            for user_login in approved_by_users:
                teams = await graphql_api.get_team_membership(self.org_id, user_login)
                for team in teams:
                    approved_by_teams.add(team["name"])

            self.logger.debug(f"approved by teams: {approved_by_teams}")

            has_required_approvals = contains_valid_team_for_approval(approved_by_teams)

            pull_request_model = await update_or_create_pull_request(
                self.org_id,
                self.repo_name,
                self.pull_request,
                has_required_approvals=has_required_approvals,
            )

            if pull_request_model.can_be_automerged():
                self.schedule_automerge_task(self.org_id, self.repo_name, self.pull_request_number)
        else:
            await update_or_create_pull_request(
                self.org_id,
                self.repo_name,
                self.pull_request,
            )

    def __repr__(self) -> str:
        return f"UpdatePullRequestTask(repo={self.org_id}/{self.repo_name}, pull_request=#{self.pull_request_number})"
