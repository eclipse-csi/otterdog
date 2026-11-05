#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
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
from otterdog.models import FailureType, LivePatch, ModelObject, ValidationContext
from otterdog.models.team import Team
from otterdog.models.team_sync import TeamSync
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET

from . import ModelTest

GROUP_ADMINS = {"group_id": "123", "group_name": "admins", "group_description": "The admins"}
GROUP_DEVS = {"group_id": "456", "group_name": "devs", "group_description": "The developers"}


def validation_context() -> ValidationContext:
    return ValidationContext(
        root_object=None,
        secret_resolver=stub(),
        template_dir="",
        org_members=set(),
        default_team_names=set(),
        exclude_teams_pattern=None,
    )


def provider_with_groups(groups: list[dict[str, Any]] | None, team_slug: str = "test-team"):
    rest_api = stub(
        team=stub(
            get_team_slug=AsyncMock(return_value=team_slug),
            get_team_sync_groups=AsyncMock(return_value=groups),
            update_team_sync_groups=AsyncMock(),
        )
    )
    provider = GitHubProvider(None)
    provider.rest_api = rest_api
    return provider, rest_api


def team(slug: Any = "test-team") -> Team:
    team = Team.from_model_data({"name": "Test Team", "privacy": "visible"})
    team.slug = slug
    return team


class TeamSyncTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return TeamSync.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_team_sync

    @property
    def model_data(self):
        return {"id": "123", "name": "admins", "description": "The admins"}

    @property
    def provider_data(self):
        # the GitHub API returns additional properties which are not part of the model
        return {**GROUP_ADMINS, "status": "synced", "synced_at": "2026-01-01T00:00:00Z"}

    def test_load_from_model(self):
        team_sync = TeamSync.from_model_data(self.model_data)

        assert team_sync.id == "123"
        assert team_sync.name == "admins"
        assert team_sync.description == "The admins"
        assert team_sync.get_key_value() == "123"

    def test_load_from_provider(self):
        team_sync = TeamSync.from_provider_data(self.org_id, self.provider_data)

        assert team_sync.id == "123"
        assert team_sync.name == "admins"
        assert team_sync.description == "The admins"

    def test_load_from_provider_without_description(self):
        team_sync = TeamSync.from_provider_data(self.org_id, {"group_id": "123", "group_name": "admins"})

        assert team_sync.description == ""

    async def test_to_provider(self):
        team_sync = TeamSync.from_model_data(self.model_data)

        assert await team_sync.to_provider_data(self.org_id, self.provider) == GROUP_ADMINS

    async def test_to_provider_without_description(self):
        team_sync = TeamSync.from_model_data({"id": "123", "name": "admins"})

        assert team_sync.description is UNSET
        assert await team_sync.to_provider_data(self.org_id, self.provider) == {**GROUP_ADMINS, "group_description": ""}

    def test_validate(self):
        context = validation_context()

        TeamSync.from_model_data(self.model_data).validate(context, team())
        TeamSync.from_model_data({"id": "123", "name": "admins", "description": ""}).validate(context, team())

        assert context.validation_failures == []

    def test_validate_missing_fields(self):
        for data, missing in [
            ({"id": "", "name": "admins", "description": ""}, "id"),
            ({"id": "123", "name": " ", "description": ""}, "name"),
            ({"id": " ", "name": "", "description": ""}, "id, name"),
        ]:
            with self.subTest(data=data):
                context = validation_context()

                TeamSync.from_model_data(data).validate(context, team())

                assert len(context.validation_failures) == 1
                failure_type, message = context.validation_failures[0]
                assert failure_type == FailureType.ERROR
                assert f"missing required fields: {missing}" in message

    async def test_add_keeps_other_groups(self):
        provider, rest_api = provider_with_groups([{**GROUP_DEVS, "status": "synced", "synced_at": None}])
        patch = LivePatch.of_addition(TeamSync.from_model_data(self.model_data), team(), TeamSync.apply_live_patch)

        await patch.apply(self.org_id, provider)

        rest_api.team.get_team_slug.assert_not_awaited()
        rest_api.team.update_team_sync_groups.assert_awaited_once_with(
            self.org_id, "test-team", [GROUP_DEVS, GROUP_ADMINS]
        )

    async def test_add_to_team_loaded_from_model_resolves_slug(self):
        provider, rest_api = provider_with_groups([])
        patch = LivePatch.of_addition(TeamSync.from_model_data(self.model_data), team(UNSET), TeamSync.apply_live_patch)

        await patch.apply(self.org_id, provider)

        rest_api.team.get_team_slug.assert_awaited_once_with(self.org_id, "Test Team")
        rest_api.team.update_team_sync_groups.assert_awaited_once_with(self.org_id, "test-team", [GROUP_ADMINS])

    async def test_change_replaces_group_in_place(self):
        provider, rest_api = provider_with_groups([GROUP_ADMINS, GROUP_DEVS])
        expected = TeamSync.from_model_data({"id": "123", "name": "admins", "description": "changed"})
        current = TeamSync.from_provider_data(self.org_id, GROUP_ADMINS)
        changes = expected.get_difference_from(current)
        patch = LivePatch.of_changes(expected, current, changes, team(), False, TeamSync.apply_live_patch)

        await patch.apply(self.org_id, provider)

        rest_api.team.update_team_sync_groups.assert_awaited_once_with(
            self.org_id, "test-team", [{**GROUP_ADMINS, "group_description": "changed"}, GROUP_DEVS]
        )

    async def test_remove_keeps_other_groups(self):
        provider, rest_api = provider_with_groups([GROUP_ADMINS, GROUP_DEVS])
        current = TeamSync.from_provider_data(self.org_id, GROUP_ADMINS)
        patch = LivePatch.of_deletion(current, team(), TeamSync.apply_live_patch)

        await patch.apply(self.org_id, provider)

        rest_api.team.update_team_sync_groups.assert_awaited_once_with(self.org_id, "test-team", [GROUP_DEVS])

    async def test_remove_group_not_connected(self):
        provider, rest_api = provider_with_groups([GROUP_DEVS])
        current = TeamSync.from_provider_data(self.org_id, GROUP_ADMINS)
        patch = LivePatch.of_deletion(current, team(), TeamSync.apply_live_patch)

        await patch.apply(self.org_id, provider)

        rest_api.team.update_team_sync_groups.assert_not_awaited()

    async def test_update_fails_if_team_sync_not_available(self):
        # the existing group mappings are unknown, updating them would disconnect all other groups
        provider, rest_api = provider_with_groups(None)
        patch = LivePatch.of_addition(TeamSync.from_model_data(self.model_data), team(), TeamSync.apply_live_patch)

        with pytest.raises(RuntimeError, match="team synchronization is not available"):
            await patch.apply(self.org_id, provider)

        rest_api.team.update_team_sync_groups.assert_not_awaited()
