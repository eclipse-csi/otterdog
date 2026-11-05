#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import re
from typing import Any

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest import RestApi, RestClient

_logger = get_logger(__name__)

# status codes returned when team synchronization or external groups are not available for an organization,
# e.g. team synchronization is not enabled, or the organization is not part of an enterprise using
# Enterprise Managed Users (external groups) or is part of one (team synchronization)
_FEATURE_NOT_AVAILABLE_STATUSES = (400, 402, 403, 404, 422)

# key of the external group id in the team data, it is not part of the team itself
_EXTERNAL_GROUP_ID_KEY = "external_group_id"


class TeamClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_team_ids(self, combined_slug: str) -> tuple[int, str]:
        _logger.debug("retrieving team ids for slug '%s'", combined_slug)
        org_id, team_slug = re.split("/", combined_slug)

        try:
            response = await self.requester.request_json("GET", f"/orgs/{org_id}/teams/{team_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving team node id:\n{ex}") from ex

    async def get_teams(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving teams for org '%s'", org_id)

        try:
            return await self.requester.request_paged_json("GET", f"/orgs/{org_id}/teams")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving teams for org '{org_id}':\n{ex}") from ex

    async def get_team_slugs(self, org_id: str) -> list[str]:
        _logger.debug("retrieving team slugs for org '%s'", org_id)

        try:
            teams = await self.get_teams(org_id)
            return [team["slug"] for team in teams]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving teams:\n{ex}") from ex

    async def get_team_slug(self, org_id: str, team_name: str) -> str | None:
        _logger.debug("retrieving team slug for team %s in org '%s'", team_name, org_id)

        try:
            teams = await self.get_teams(org_id)
            for team in teams:
                if team["name"] == team_name:
                    return team["slug"]

            return None
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving teams:\n{ex}") from ex

    async def add_team(self, org_id: str, team_name: str, data: dict[str, str]) -> str:
        _logger.debug("adding team '%s' for org '%s'", team_name, org_id)

        team_data = {k: v for k, v in data.items() if k != _EXTERNAL_GROUP_ID_KEY}
        status, body = await self.requester.request_raw("POST", f"/orgs/{org_id}/teams", json.dumps(team_data))

        if status != 201:
            raise RuntimeError(f"failed to add team '{team_name}': {body}")

        team_data = json.loads(body)
        team_slug = team_data["slug"]

        # GitHub automatically adds the creator of the team to the list of maintainers
        # Remove any member of the team right after creation again
        current_members = await self.get_team_members(org_id, team_slug)
        for current_member in current_members:
            await self.remove_member_from_team(org_id, team_slug, current_member["login"])

        if "members" in data:
            members = data["members"]
            for user in members:
                await self.add_member_to_team(org_id, team_slug, user)

        external_group_id = data.get(_EXTERNAL_GROUP_ID_KEY)
        if external_group_id is not None:
            await self.update_team_external_group(org_id, team_slug, int(external_group_id))

        _logger.debug("added team '%s'", team_name)
        return team_slug

    async def update_team(self, org_id: str, team_slug: str, team: dict[str, Any]) -> None:
        _logger.debug("updating team '%s' for org '%s'", team_slug, org_id)

        try:
            team_data = {k: v for k, v in team.items() if k != _EXTERNAL_GROUP_ID_KEY}
            await self.requester.request_json("PATCH", f"/orgs/{org_id}/teams/{team_slug}", team_data)

            # the members of a team connected to an external group can not be changed:
            # disconnect the external group before updating the members, connect it afterward
            update_external_group = _EXTERNAL_GROUP_ID_KEY in team
            external_group_id = team.get(_EXTERNAL_GROUP_ID_KEY)

            if update_external_group and external_group_id is None:
                await self.delete_team_external_group(org_id, team_slug)

            if "members" in team:
                await self.update_team_members(org_id, team_slug, team["members"])

            if update_external_group and external_group_id is not None:
                await self.connect_team_external_group(org_id, team_slug, int(external_group_id))

            _logger.debug("updated team '%s'", team_slug)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update team '{team_slug}':\n{ex}") from ex

    async def get_team_members(self, org_id: str, team_slug: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving team members for team '%s/%s'", org_id, team_slug)

        try:
            return await self.requester.request_paged_json("GET", f"/orgs/{org_id}/teams/{team_slug}/members")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving team members for team '{org_id}/{team_slug}':\n{ex}") from ex

    async def update_team_members(self, org_id: str, team_slug: str, members: list[str]) -> None:
        _logger.debug("updating team members for team '%s' in org '%s'", team_slug, org_id)

        current_members = {x["login"] for x in await self.get_team_members(org_id, team_slug)}

        # first, add all users that are not members yet.
        for member in members:
            if member in current_members:
                current_members.remove(member)
            else:
                await self.add_member_to_team(org_id, team_slug, member)

        # second, remove the current members that are remaining.
        for member in current_members:
            await self.remove_member_from_team(org_id, team_slug, member)

    async def add_member_to_team(self, org_id: str, team_slug: str, user: str) -> None:
        _logger.debug("adding user with id '%s' to team '%s' in org '%s'", user, team_slug, org_id)

        data = {"role": "member"}
        status, body = await self.requester.request_raw(
            "PUT", f"/orgs/{org_id}/teams/{team_slug}/memberships/{user}", data=json.dumps(data)
        )

        if status == 200:
            _logger.debug("added user '%s' to team '%s' for org '%s'", user, team_slug, org_id)
        else:
            raise RuntimeError(f"failed adding user '{user}' to team '{team_slug}' in org '{org_id}'\n{status}: {body}")

    async def remove_member_from_team(self, org_id: str, team_slug: str, user: str) -> None:
        _logger.debug("removing user '%s' from team '%s' in org '%s'", user, team_slug, org_id)

        status, body = await self.requester.request_raw(
            "DELETE", f"/orgs/{org_id}/teams/{team_slug}/memberships/{user}"
        )
        if status != 204:
            raise RuntimeError(
                f"failed removing user '{user}' from team '{team_slug}' in org '{org_id}'\n{status}: {body}"
            )

        _logger.debug("removed user '%s' from team '%s' in org '%s'", user, team_slug, org_id)

    async def delete_team(self, org_id: str, team_slug: str) -> None:
        _logger.debug("deleting team '%s' for org '%s'", team_slug, org_id)

        status, body = await self.requester.request_raw("DELETE", f"/orgs/{org_id}/teams/{team_slug}")

        if status != 204:
            raise RuntimeError(f"failed to delete team '{team_slug}': {body}")

        _logger.debug("removed team '%s'", team_slug)

    async def is_user_member_of_team(self, org_id: str, team_slug: str, user: str) -> bool:
        _logger.debug("retrieving membership of user '%s' for team '%s' in org '%s'", user, team_slug, org_id)

        status, body = await self.requester.request_raw("GET", f"/orgs/{org_id}/teams/{team_slug}/memberships/{user}")

        if status == 200:
            return True
        elif status == 404:
            return False
        else:
            raise RuntimeError(
                f"failed retrieving team membership for user '{user}' in org '{org_id}'\n{status}: {body}"
            )

    async def get_membership(self, org_id: str, user_name: str) -> dict[str, Any]:
        _logger.debug("retrieving membership for user '%s' in org '%s'", user_name, org_id)

        try:
            return await self.requester.request_json("GET", f"/orgs/{org_id}/memberships/{user_name}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving membership for user '{user_name}' in org '{org_id}':\n{ex}") from ex

    async def get_team_sync_groups(self, org_id: str, team_slug: str) -> list[dict[str, Any]] | None:
        """
        Returns the IdP groups connected to the team via team synchronization,
        or None if team synchronization is not available.
        """
        _logger.debug("retrieving team sync groups for team '%s/%s'", org_id, team_slug)

        response = await self._get_optional_json(
            f"/orgs/{org_id}/teams/{team_slug}/team-sync/group-mappings",
            feature_description=f"team synchronization for team '{org_id}/{team_slug}'",
            unavailable_statuses=_FEATURE_NOT_AVAILABLE_STATUSES,
            # unknown connections to IdP groups must not be taken as not connected
            raise_on_access_denied=True,
        )

        return None if response is None else response.get("groups", [])

    async def update_team_sync_groups(self, org_id: str, team_slug: str, groups: list[dict[str, Any]]) -> None:
        _logger.debug("updating team sync groups for team '%s/%s'", org_id, team_slug)

        try:
            # the group mappings are replaced as a whole, an empty list disconnects all groups
            await self.requester.request_json(
                "PATCH", f"/orgs/{org_id}/teams/{team_slug}/team-sync/group-mappings", {"groups": groups}
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed updating team sync groups for team '{org_id}/{team_slug}':\n{ex}") from ex

        _logger.debug("updated team sync groups for team '%s/%s'", org_id, team_slug)

    async def get_team_external_groups(self, org_id: str, team_slug: str) -> list[dict[str, Any]] | None:
        """
        Returns the external groups connected to the team, or None if external groups are not available.
        """
        _logger.debug("retrieving external groups for team '%s/%s'", org_id, team_slug)

        response = await self._get_optional_json(
            f"/orgs/{org_id}/teams/{team_slug}/external-groups",
            feature_description=f"external groups for team '{org_id}/{team_slug}'",
            unavailable_statuses=_FEATURE_NOT_AVAILABLE_STATUSES,
            # unknown connections to IdP groups must not be taken as not connected
            raise_on_access_denied=True,
        )

        return None if response is None else response.get("groups", [])

    async def connect_team_external_group(self, org_id: str, team_slug: str, group_id: int) -> None:
        """
        Connects an existing team to an external group, removing its members first if the team is not yet
        connected to an external group, as required by GitHub: the members are then provisioned by the IdP.
        """
        external_groups = await self.get_team_external_groups(org_id, team_slug)
        if external_groups is None:
            raise RuntimeError(f"external groups are not available for team '{org_id}/{team_slug}'")

        if len(external_groups) == 0:
            for member in await self.get_team_members(org_id, team_slug):
                await self.remove_member_from_team(org_id, team_slug, member["login"])

        await self.update_team_external_group(org_id, team_slug, group_id)

    async def update_team_external_group(self, org_id: str, team_slug: str, group_id: int) -> None:
        _logger.debug("connecting external group '%d' to team '%s/%s'", group_id, org_id, team_slug)

        try:
            await self.requester.request_json(
                "PATCH", f"/orgs/{org_id}/teams/{team_slug}/external-groups", {"group_id": group_id}
            )
        except GitHubException as ex:
            raise RuntimeError(
                f"failed connecting external group '{group_id}' to team '{org_id}/{team_slug}':\n{ex}"
            ) from ex

        _logger.debug("connected external group '%d' to team '%s/%s'", group_id, org_id, team_slug)

    async def delete_team_external_group(self, org_id: str, team_slug: str) -> None:
        _logger.debug("disconnecting external group from team '%s/%s'", org_id, team_slug)

        status, body = await self.requester.request_raw("DELETE", f"/orgs/{org_id}/teams/{team_slug}/external-groups")
        if status != 204:
            raise RuntimeError(
                f"failed disconnecting external group from team '{org_id}/{team_slug}'\n{status}: {body}"
            )

        _logger.debug("disconnected external group from team '%s/%s'", org_id, team_slug)
