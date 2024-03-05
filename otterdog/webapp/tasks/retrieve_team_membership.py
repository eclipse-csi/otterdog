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
class RetrieveTeamMembershipTask(InstallationBasedTask, Task[None]):
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

    async def _pre_execute(self) -> None:
        if isinstance(self.pull_request_or_number, int):
            rest_api = await self.rest_api
            response = await rest_api.pull_request.get_pull_request(
                self.org_id, self.repo_name, str(self.pull_request_number)
            )
            self._pull_request = PullRequest.model_validate(response)
        else:
            self._pull_request = self.pull_request_or_number

        self.logger.info(
            "retrieving team membership of author '%s' for pull request #%d of repo '%s/%s'",
            self._pull_request.user.login,
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )

    async def _execute(self) -> None:
        rest_api = await self.rest_api

        user = self._pull_request.user.login
        association = self._pull_request.author_association

        graphql_api = await self.graphql_api
        team_data = await graphql_api.get_team_membership(self.org_id, user)
        team_membership = [team["name"] for team in team_data]

        teams = [(team, f"https://github.com/orgs/{self.org_id}/teams/{team}") for team in team_membership]
        comment = await render_template(
            "comment/team_membership_comment.txt",
            user=user,
            association=association,
            teams=teams,
        )

        await self.minimize_outdated_comments(
            self.org_id,
            self.repo_name,
            self.pull_request_number,
            "<!-- Otterdog Comment: team-info -->",
        )

        await rest_api.issue.create_comment(
            self.org_id,
            self.repo_name,
            str(self.pull_request_number),
            comment,
        )

    def __repr__(self) -> str:
        return (
            f"RetrieveTeamMembershipTask(repo='{self.org_id}/{self.repo_name}', "
            f"pull_request=#{self.pull_request_number})"
        )
