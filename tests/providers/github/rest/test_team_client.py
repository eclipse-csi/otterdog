#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

import pretend
import pytest

from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.team_client import TeamClient

TEAM_URL = "/orgs/org/teams/team"
TEAM_SYNC_URL = f"{TEAM_URL}/team-sync/group-mappings"
EXTERNAL_GROUPS_URL = f"{TEAM_URL}/external-groups"
EXTERNAL_GROUP_URL = "/orgs/org/external-group/123"
MEMBERSHIP_URL = f"{TEAM_URL}/memberships"


class FakeRequester:
    """Records the requests and returns the configured response for a method and url, (200, {}) by default."""

    def __init__(
        self, responses: dict[tuple[str, str], tuple[int, Any]] | None = None, members: dict[str, str] | None = None
    ):
        self.responses = responses or {}
        # the role of each member of the team
        self.members = members or {}
        self.requests: list[tuple[str, str, Any]] = []

    def _respond(self, method: str, url_path: str, data: Any) -> tuple[int, str]:
        self.requests.append((method, url_path, data))
        status, body = self.responses.get((method, url_path), (200, {}))
        return status, json.dumps(body)

    async def request_raw(self, method: str, url_path: str, data: str | None = None, params: Any = None):
        return self._respond(method, url_path, json.loads(data) if data is not None else None)

    async def request_json(self, method: str, url_path: str, data: Any = None, params: Any = None):
        status, body = self._respond(method, url_path, data)
        if status >= 400:
            raise GitHubException(url_path, status, body)
        return json.loads(body)

    async def request_paged_json(self, method: str, url_path: str, data: Any = None, params: Any = None):
        # only used to retrieve the members of a team, possibly with a role, not recorded
        role = (params or {}).get("role", "all")
        return [{"login": member} for member, member_role in self.members.items() if role in ("all", member_role)]


def team_client(requester: FakeRequester) -> TeamClient:
    return TeamClient(pretend.stub(requester=requester))


class TestTeamSyncGroups:
    async def test_get_team_sync_groups(self):
        groups = [{"group_id": "123", "group_name": "admins", "group_description": "", "status": "synced"}]
        requester = FakeRequester({("GET", TEAM_SYNC_URL): (200, {"groups": groups})})

        assert await team_client(requester).get_team_sync_groups("org", "team") == groups

    @pytest.mark.parametrize("status", [400, 403, 404, 422])
    async def test_get_team_sync_groups_not_available(self, status):
        requester = FakeRequester({("GET", TEAM_SYNC_URL): (status, {"message": "not available"})})

        assert await team_client(requester).get_team_sync_groups("org", "team") is None

    async def test_get_team_sync_groups_rate_limited(self):
        # a rate limit must not be taken as team synchronization not being available for the organization
        rate_limit = {"message": "API rate limit exceeded for installation ID 1."}
        client = team_client(FakeRequester({("GET", TEAM_SYNC_URL): (403, rate_limit)}))

        with pytest.raises(RuntimeError, match="team synchronization for team 'org/team': 403"):
            await client.get_team_sync_groups("org", "team")

    @pytest.mark.parametrize(
        "message",
        [
            "Resource not accessible by integration",
            "Resource not accessible by personal access token",
            "Resource protected by organization SAML enforcement. You must grant your Personal Access token access.",
        ],
    )
    async def test_get_team_sync_groups_access_denied(self, message):
        # unknown connections to IdP groups must not be taken as not connected
        client = team_client(FakeRequester({("GET", TEAM_SYNC_URL): (403, {"message": message})}))

        with pytest.raises(RuntimeError, match="team synchronization for team 'org/team': 403"):
            await client.get_team_sync_groups("org", "team")

    async def test_get_team_sync_groups_fails(self):
        client = team_client(FakeRequester({("GET", TEAM_SYNC_URL): (500, {"message": "error"})}))

        with pytest.raises(RuntimeError, match="team synchronization for team 'org/team': 500"):
            await client.get_team_sync_groups("org", "team")

    async def test_update_team_sync_groups(self):
        groups = [{"group_id": "123", "group_name": "admins", "group_description": ""}]
        requester = FakeRequester()

        await team_client(requester).update_team_sync_groups("org", "team", groups)

        assert requester.requests == [("PATCH", TEAM_SYNC_URL, {"groups": groups})]


class TestExternalGroups:
    async def test_get_team_external_groups(self):
        # the API returns an object with a list of groups, the group id is an integer
        groups = [{"group_id": 123, "group_name": "admins", "updated_at": "2026-01-01T00:00:00Z"}]
        requester = FakeRequester({("GET", EXTERNAL_GROUPS_URL): (200, {"groups": groups})})

        assert await team_client(requester).get_team_external_groups("org", "team") == groups

    @pytest.mark.parametrize("status", [400, 403, 404, 422])
    async def test_get_team_external_groups_not_available(self, status):
        requester = FakeRequester({("GET", EXTERNAL_GROUPS_URL): (status, {"message": "not available"})})

        assert await team_client(requester).get_team_external_groups("org", "team") is None

    async def test_get_team_external_groups_access_denied(self):
        denied = {"message": "Resource not accessible by integration"}
        client = team_client(FakeRequester({("GET", EXTERNAL_GROUPS_URL): (403, denied)}))

        with pytest.raises(RuntimeError, match="external groups for team 'org/team': 403"):
            await client.get_team_external_groups("org", "team")

    async def test_update_team_connects_external_group(self):
        requester = FakeRequester()

        await team_client(requester).update_team("org", "team", {"description": "desc", "external_group_id": 123})

        assert requester.requests == [
            ("PATCH", TEAM_URL, {"description": "desc"}),
            ("GET", EXTERNAL_GROUPS_URL, None),
            ("GET", EXTERNAL_GROUP_URL, None),
            ("PATCH", EXTERNAL_GROUPS_URL, {"group_id": 123}),
        ]

    async def test_first_connection_to_external_group_removes_members(self):
        # GitHub requires to remove the members of an existing team before connecting it to an IdP group
        requester = FakeRequester(
            {
                ("GET", EXTERNAL_GROUPS_URL): (200, {"groups": []}),
                ("DELETE", f"{MEMBERSHIP_URL}/alice"): (204, ""),
                ("DELETE", f"{MEMBERSHIP_URL}/bob"): (204, ""),
            },
            members={"alice": "maintainer", "bob": "member"},
        )

        await team_client(requester).update_team("org", "team", {"external_group_id": 123})

        assert requester.requests == [
            ("PATCH", TEAM_URL, {}),
            ("GET", EXTERNAL_GROUPS_URL, None),
            # the external group is checked before removing the members
            ("GET", EXTERNAL_GROUP_URL, None),
            ("DELETE", f"{MEMBERSHIP_URL}/alice", None),
            ("DELETE", f"{MEMBERSHIP_URL}/bob", None),
            ("PATCH", EXTERNAL_GROUPS_URL, {"group_id": 123}),
        ]

    async def test_first_connection_to_unknown_external_group_keeps_members(self):
        requester = FakeRequester(
            {
                ("GET", EXTERNAL_GROUPS_URL): (200, {"groups": []}),
                ("GET", EXTERNAL_GROUP_URL): (404, {"message": "Not Found"}),
            },
            members={"alice": "member"},
        )
        client = team_client(requester)

        with pytest.raises(RuntimeError, match="failed retrieving external group '123' of org 'org'"):
            await client.connect_team_external_group("org", "team", 123)

        assert requester.requests == [("GET", EXTERNAL_GROUPS_URL, None), ("GET", EXTERNAL_GROUP_URL, None)]

    async def test_failed_first_connection_to_external_group_restores_members(self):
        # the removed members are restored with their role
        requester = FakeRequester(
            {
                ("GET", EXTERNAL_GROUPS_URL): (200, {"groups": []}),
                ("DELETE", f"{MEMBERSHIP_URL}/alice"): (204, ""),
                ("DELETE", f"{MEMBERSHIP_URL}/bob"): (204, ""),
                ("PATCH", EXTERNAL_GROUPS_URL): (422, {"message": "Validation Failed"}),
            },
            members={"alice": "maintainer", "bob": "member"},
        )
        client = team_client(requester)

        with pytest.raises(RuntimeError, match="failed connecting external group '123' to team 'org/team'"):
            await client.connect_team_external_group("org", "team", 123)

        assert requester.requests[-3:] == [
            ("PATCH", EXTERNAL_GROUPS_URL, {"group_id": 123}),
            ("PUT", f"{MEMBERSHIP_URL}/alice", {"role": "maintainer"}),
            ("PUT", f"{MEMBERSHIP_URL}/bob", {"role": "member"}),
        ]

    async def test_failed_member_removal_restores_removed_members(self):
        requester = FakeRequester(
            {
                ("GET", EXTERNAL_GROUPS_URL): (200, {"groups": []}),
                ("DELETE", f"{MEMBERSHIP_URL}/alice"): (204, ""),
                ("DELETE", f"{MEMBERSHIP_URL}/bob"): (403, {"message": "Forbidden"}),
            },
            members={"alice": "maintainer", "bob": "member"},
        )
        client = team_client(requester)

        with pytest.raises(RuntimeError, match="failed removing user 'bob'"):
            await client.connect_team_external_group("org", "team", 123)

        # only the removed member is restored, the team is not connected
        assert requester.requests[-2:] == [
            ("DELETE", f"{MEMBERSHIP_URL}/bob", None),
            ("PUT", f"{MEMBERSHIP_URL}/alice", {"role": "maintainer"}),
        ]

    async def test_changing_external_group_keeps_members(self):
        # the members of a team already connected to an external group are provisioned by the IdP
        requester = FakeRequester(
            {("GET", EXTERNAL_GROUPS_URL): (200, {"groups": [{"group_id": 1, "group_name": "previous"}]})},
            members={"alice": "member"},
        )

        await team_client(requester).update_team("org", "team", {"external_group_id": 123})

        assert requester.requests == [
            ("PATCH", TEAM_URL, {}),
            ("GET", EXTERNAL_GROUPS_URL, None),
            ("PATCH", EXTERNAL_GROUPS_URL, {"group_id": 123}),
        ]

    async def test_connect_external_group_fails_if_not_available(self):
        # the members are not removed if the team can not be connected
        requester = FakeRequester(
            {("GET", EXTERNAL_GROUPS_URL): (404, {"message": "Not Found"})}, members={"alice": "member"}
        )
        client = team_client(requester)

        with pytest.raises(RuntimeError, match="external groups are not available for team 'org/team'"):
            await client.connect_team_external_group("org", "team", 123)

        assert requester.requests == [("GET", EXTERNAL_GROUPS_URL, None)]

    async def test_update_team_disconnects_external_group(self):
        requester = FakeRequester({("DELETE", EXTERNAL_GROUPS_URL): (204, "")})

        await team_client(requester).update_team("org", "team", {"external_group_id": None})

        assert requester.requests == [("PATCH", TEAM_URL, {}), ("DELETE", EXTERNAL_GROUPS_URL, None)]

    async def test_update_team_disconnects_external_group_before_updating_members(self):
        # the members of a team connected to an external group can not be changed
        requester = FakeRequester({("DELETE", EXTERNAL_GROUPS_URL): (204, "")})

        await team_client(requester).update_team("org", "team", {"external_group_id": None, "members": ["netomi"]})

        assert requester.requests == [
            ("PATCH", TEAM_URL, {"members": ["netomi"]}),
            ("DELETE", EXTERNAL_GROUPS_URL, None),
            ("PUT", f"{TEAM_URL}/memberships/netomi", {"role": "member"}),
        ]

    async def test_update_team_connects_external_group_after_updating_members(self):
        requester = FakeRequester()

        await team_client(requester).update_team("org", "team", {"external_group_id": 123, "members": ["netomi"]})

        assert requester.requests == [
            ("PATCH", TEAM_URL, {"members": ["netomi"]}),
            ("PUT", f"{TEAM_URL}/memberships/netomi", {"role": "member"}),
            ("GET", EXTERNAL_GROUPS_URL, None),
            ("GET", EXTERNAL_GROUP_URL, None),
            ("PATCH", EXTERNAL_GROUPS_URL, {"group_id": 123}),
        ]

    async def test_update_team_without_external_group(self):
        requester = FakeRequester()

        await team_client(requester).update_team("org", "team", {"description": "desc"})

        assert requester.requests == [("PATCH", TEAM_URL, {"description": "desc"})]

    async def test_disconnect_external_group_fails(self):
        client = team_client(FakeRequester({("DELETE", EXTERNAL_GROUPS_URL): (422, {"message": "error"})}))

        with pytest.raises(RuntimeError, match="failed disconnecting external group"):
            await client.delete_team_external_group("org", "team")

    async def test_add_team_connects_external_group(self):
        requester = FakeRequester({("POST", "/orgs/org/teams"): (201, {"slug": "team"})})

        await team_client(requester).add_team("org", "Team", {"name": "Team", "external_group_id": 123})

        assert requester.requests == [
            ("POST", "/orgs/org/teams", {"name": "Team"}),
            ("PATCH", EXTERNAL_GROUPS_URL, {"group_id": 123}),
        ]
