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


class FakeRequester:
    """Records the requests and returns the configured response for a method and url, (200, {}) by default."""

    def __init__(self, responses: dict[tuple[str, str], tuple[int, Any]] | None = None):
        self.responses = responses or {}
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
        # only used to retrieve the members of a team, not recorded
        return []


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

    async def test_get_team_sync_groups_fails(self):
        requester = FakeRequester({("GET", TEAM_SYNC_URL): (500, {"message": "error"})})

        with pytest.raises(RuntimeError, match="team synchronization for team 'org/team': 500"):
            await team_client(requester).get_team_sync_groups("org", "team")

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

    async def test_update_team_connects_external_group(self):
        requester = FakeRequester()

        await team_client(requester).update_team("org", "team", {"description": "desc", "external_group_id": 123})

        assert requester.requests == [
            ("PATCH", TEAM_URL, {"description": "desc"}),
            ("PATCH", EXTERNAL_GROUPS_URL, {"group_id": 123}),
        ]

    async def test_update_team_disconnects_external_group(self):
        requester = FakeRequester({("DELETE", EXTERNAL_GROUPS_URL): (204, "")})

        await team_client(requester).update_team("org", "team", {"external_group_id": None})

        assert requester.requests == [("PATCH", TEAM_URL, {}), ("DELETE", EXTERNAL_GROUPS_URL, None)]

    async def test_update_team_without_external_group(self):
        requester = FakeRequester()

        await team_client(requester).update_team("org", "team", {"description": "desc"})

        assert requester.requests == [("PATCH", TEAM_URL, {"description": "desc"})]

    async def test_disconnect_external_group_fails(self):
        requester = FakeRequester({("DELETE", EXTERNAL_GROUPS_URL): (422, {"message": "error"})})

        with pytest.raises(RuntimeError, match="failed disconnecting external group"):
            await team_client(requester).delete_team_external_group("org", "team")

    async def test_add_team_connects_external_group(self):
        requester = FakeRequester({("POST", "/orgs/org/teams"): (201, {"slug": "team"})})

        await team_client(requester).add_team("org", "Team", {"name": "Team", "external_group_id": 123})

        assert requester.requests == [
            ("POST", "/orgs/org/teams", {"name": "Team"}),
            ("PATCH", EXTERNAL_GROUPS_URL, {"group_id": 123}),
        ]
