#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses
from typing import cast

from pydantic import ValidationError
from quart import render_template

from otterdog.webapp.tasks import Task
from otterdog.webapp.webhook.github_models import PullRequest, Repository


@dataclasses.dataclass(repr=False)
class RetrieveTeamMembershipTask(Task[None]):
    installation_id: int
    org_id: str
    repository: Repository
    pull_request_or_number: PullRequest | int

    async def _pre_execute(self) -> None:
        rest_api = await self.get_rest_api(self.installation_id)

        if isinstance(self.pull_request_or_number, int):
            response = await rest_api.pull_request.get_pull_request(
                self.org_id, self.repository.name, str(self.pull_request_or_number)
            )
            try:
                self.pull_request = PullRequest.model_validate(response)
            except ValidationError as ex:
                self.logger.exception("failed to load pull request event data", exc_info=ex)
                return
        else:
            self.pull_request = cast(PullRequest, self.pull_request_or_number)

        self.logger.info(
            "retrieving team membership of author '%s' for pull request #%d of repo '%s'",
            self.pull_request.user.login,
            self.pull_request.number,
            self.repository.full_name,
        )

    async def _execute(self) -> None:
        rest_api = await self.get_rest_api(self.installation_id)

        user = self.pull_request.user.login
        team_slugs = await rest_api.team.get_team_slugs(self.org_id)
        team_membership = []

        for team_slug in team_slugs:
            if await rest_api.team.is_user_member_of_team(self.org_id, team_slug, user):
                team_membership.append(team_slug)

        teams = [(team, f"https://github.com/orgs/{self.org_id}/teams/{team}") for team in team_membership]
        comment = await render_template("team_membership_comment.txt", user=user, teams=teams)
        await rest_api.issue.create_comment(self.org_id, self.repository.name, str(self.pull_request.number), comment)

    def __repr__(self) -> str:
        pull_request_number = (
            self.pull_request_or_number
            if isinstance(self.pull_request_or_number, int)
            else self.pull_request_or_number.number
        )
        return f"RetrieveTeamMembershipTask(repo={self.repository.full_name}, pull_request={pull_request_number})"
