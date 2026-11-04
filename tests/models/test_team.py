#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pretend import stub

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import LivePatch, ModelObject
from otterdog.models.team import Team
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, query_json

from . import ModelTest


class TeamTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return Team.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_team

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-team.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-team.json")

    def test_load_from_model(self):
        team = Team.from_model_data(self.model_data)

        assert team.id is UNSET
        assert team.slug is UNSET
        assert team.name == "Test Team"
        assert team.description == "Blabla"
        assert team.privacy == "visible"
        assert team.notifications is True
        assert team.members == ["netomi"]

    def test_load_from_provider(self):
        team = Team.from_provider_data(self.org_id, self.provider_data)

        assert team.id == 1102681190
        assert team.slug == "test-team"
        assert team.name == "Test Team"
        assert team.description == "Blabla"
        assert team.privacy == "visible"
        assert team.notifications is True
        assert team.members == ["netomi"]

    async def test_to_provider(self):
        team = Team.from_model_data(self.model_data)

        provider_data = await team.to_provider_data(self.org_id, self.provider)

        assert len(provider_data) == 5
        assert provider_data["name"] == "Test Team"
        assert provider_data["privacy"] == "closed"
        assert provider_data["notification_setting"] == "notifications_enabled"

        assert query_json("members[0]", provider_data) == "netomi"

    async def test_remove_team_loaded_from_model(self):
        # a team loaded from a configuration, e.g. by a local apply, has no slug
        team = Team.from_model_data(self.model_data)
        rest_api = stub(team=stub(get_team_slug=AsyncMock(return_value="test-team"), delete_team=AsyncMock()))
        provider = GitHubProvider(None)
        provider.rest_api = rest_api

        await LivePatch.of_deletion(team, None, Team.apply_live_patch).apply(self.org_id, provider)

        rest_api.team.get_team_slug.assert_awaited_once_with(self.org_id, "Test Team")
        rest_api.team.delete_team.assert_awaited_once_with(self.org_id, "test-team")

    async def test_remove_team_loaded_from_provider(self):
        team = Team.from_provider_data(self.org_id, self.provider_data)
        rest_api = stub(team=stub(get_team_slug=AsyncMock(), delete_team=AsyncMock()))
        provider = GitHubProvider(None)
        provider.rest_api = rest_api

        await LivePatch.of_deletion(team, None, Team.apply_live_patch).apply(self.org_id, provider)

        rest_api.team.get_team_slug.assert_not_awaited()
        rest_api.team.delete_team.assert_awaited_once_with(self.org_id, "test-team")

    async def test_remove_team_missing_on_github(self):
        # e.g. a team of the BASE configuration that was already deleted or renamed on GitHub
        team = Team.from_model_data(self.model_data)
        rest_api = stub(team=stub(get_team_slug=AsyncMock(return_value=None), delete_team=AsyncMock()))
        provider = GitHubProvider(None)
        provider.rest_api = rest_api

        with pytest.raises(RuntimeError, match="failed to find team with name 'Test Team'"):
            await LivePatch.of_deletion(team, None, Team.apply_live_patch).apply(self.org_id, provider)

        rest_api.team.delete_team.assert_not_awaited()

    async def test_update_team_missing_on_github(self):
        rest_api = stub(team=stub(get_team_slug=AsyncMock(return_value=None), update_team=AsyncMock()))
        provider = GitHubProvider(None)
        provider.rest_api = rest_api

        with pytest.raises(RuntimeError, match="failed to find team with name 'Test Team'"):
            await provider.update_org_team(self.org_id, UNSET, "Test Team", {"description": "changed"})

        rest_api.team.update_team.assert_not_awaited()
