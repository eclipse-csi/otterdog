#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest import RestApi, RestClient
from otterdog.utils import print_debug


class TeamClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_team_slugs(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving teams for org '{org_id}'")

        try:
            response = await self.requester.async_request_json("GET", f"/orgs/{org_id}/teams")
            return list(map(lambda team: team["slug"], response))
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving teams:\n{ex}").with_traceback(tb)

    async def is_user_member_of_team(self, org_id: str, team_slug: str, user: str) -> bool:
        print_debug(f"retrieving membership of user '{user}' for team '{team_slug}' in org '{org_id}'")

        status, body = await self.requester.async_request_raw(
            "GET", f"/orgs/{org_id}/teams/{team_slug}/memberships/{user}"
        )

        if status == 200:
            return True
        elif status == 404:
            return False
        else:
            raise RuntimeError(
                f"failed retrieving team membership for user '{user}' in org '{org_id}'" f"\n{status}: {body}"
            )
