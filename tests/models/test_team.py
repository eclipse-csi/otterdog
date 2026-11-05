#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from collections.abc import Mapping
from io import StringIO
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pretend import stub

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import FailureType, LivePatch, LivePatchContext, ModelObject, ValidationContext
from otterdog.models.team import Team
from otterdog.models.team_sync import TeamSync
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, IndentingPrinter, jsonnet_evaluate_snippet, query_json

from . import _EXAMPLE_CONFIG, ModelTest


def _validation_context():
    return ValidationContext(
        root_object=None,
        secret_resolver=stub(),
        template_dir="",
        org_members=None,
        default_team_names=set(),
        exclude_teams_pattern=None,
    )


def _live_patch_context():
    return LivePatchContext("OtterdogTest", "*", False, False, "*", None, stub())


def _default_config(function: str) -> dict[str, Any]:
    return jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').{function}('default')")


def _team_sync_id(patch: LivePatch) -> str:
    obj = patch.expected_object if patch.expected_object is not None else patch.current_object
    return obj.id  # type: ignore[union-attr]


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
        patch = LivePatch.of_deletion(team, None, Team.apply_live_patch)

        with pytest.raises(RuntimeError, match="failed to find team with name 'Test Team'"):
            await patch.apply(self.org_id, provider)

        rest_api.team.delete_team.assert_not_awaited()

    async def test_update_team_missing_on_github(self):
        rest_api = stub(team=stub(get_team_slug=AsyncMock(return_value=None), update_team=AsyncMock()))
        provider = GitHubProvider(None)
        provider.rest_api = rest_api

        with pytest.raises(RuntimeError, match="failed to find team with name 'Test Team'"):
            await provider.update_org_team(self.org_id, UNSET, "Test Team", {"description": "changed"})

        rest_api.team.update_team.assert_not_awaited()

    @property
    def team_sync_data(self) -> list[dict[str, Any]]:
        return [
            {"id": "123", "name": "admins", "description": "The admins"},
            {"id": "456", "name": "devs", "description": ""},
        ]

    def team_with(self, **kwargs: Any) -> Team:
        data = {**self.model_data, "members": [], **kwargs}
        return Team.from_model_data(data)

    def test_load_from_model_with_identity_provider(self):
        team = self.team_with(team_sync=self.team_sync_data, external_group_id=None)

        assert [ts.id for ts in team.team_sync] == ["123", "456"]
        assert team.team_sync[0].name == "admins"
        assert team.external_group_id is None
        assert team.is_managed_by_identity_provider() is True

    def test_load_from_model_without_identity_provider(self):
        team = Team.from_model_data(self.model_data)

        assert team.team_sync == []
        assert team.external_group_id is UNSET
        assert team.is_managed_by_identity_provider() is False

    def test_load_external_group_from_provider(self):
        external_group = {"group_id": 123, "group_name": "admins", "updated_at": "2026-01-01T00:00:00Z"}

        for external_groups, expected in [([external_group], 123), ([], None)]:
            with self.subTest(external_groups=external_groups):
                team = Team.from_provider_data(self.org_id, {**self.provider_data, "external_groups": external_groups})

                assert team.external_group_id == expected

        # external groups not retrieved, e.g. not supported by the default configuration
        assert Team.from_provider_data(self.org_id, self.provider_data).external_group_id is UNSET

    async def test_to_provider_with_external_group(self):
        team = self.team_with(external_group_id=123)

        provider_data = await team.to_provider_data(self.org_id, self.provider)

        assert provider_data["external_group_id"] == 123
        assert "team_sync" not in provider_data

    def test_validate_identity_provider(self):
        context = _validation_context()

        self.team_with(team_sync=self.team_sync_data, external_group_id=None).validate(context, None)
        self.team_with(external_group_id=123).validate(context, None)

        assert context.validation_failures == []

    def test_validate_identity_provider_failures(self):
        duplicate_team_sync = [*self.team_sync_data, {"id": "123", "name": "other", "description": ""}]

        for kwargs, expected_message in [
            ({"team_sync": self.team_sync_data, "external_group_id": 123}, "only one of them is allowed"),
            ({"external_group_id": 123, "members": ["netomi"]}, "members are managed by the identity provider"),
            ({"team_sync": self.team_sync_data, "members": ["netomi"]}, "members are managed by the identity provider"),
            ({"team_sync": duplicate_team_sync}, "duplicate group id '123'"),
        ]:
            with self.subTest(kwargs=kwargs):
                context = _validation_context()

                self.team_with(**kwargs).validate(context, None)

                assert len(context.validation_failures) == 1
                failure_type, message = context.validation_failures[0]
                assert failure_type == FailureType.ERROR
                assert expected_message in message

    def test_members_ignored_for_team_managed_by_identity_provider(self):
        current = Team.from_provider_data(
            self.org_id, {**self.provider_data, "external_groups": [{"group_id": 123, "group_name": "admins"}]}
        )

        for expected in [self.team_with(external_group_id=123), self.team_with(team_sync=self.team_sync_data)]:
            with self.subTest(expected=expected):
                assert "members" not in expected.get_difference_from(current)

        # members are still managed for a team not connected to an identity provider
        assert "members" in self.team_with().get_difference_from(current)

    def test_external_group_change(self):
        current = Team.from_provider_data(self.org_id, {**self.provider_data, "external_groups": []})

        changes = self.team_with(external_group_id=123).get_difference_from(current)

        assert changes["external_group_id"].from_value is None
        assert changes["external_group_id"].to_value == 123

    def test_generate_live_patch_for_team_sync(self):
        expected = self.team_with(team_sync=[{"id": "123", "name": "admins", "description": "changed"}])
        current = Team.from_provider_data(self.org_id, {**self.provider_data, "members": []})
        current.add_team_sync(TeamSync.from_model_data({"id": "123", "name": "admins", "description": "The admins"}))
        current.add_team_sync(TeamSync.from_model_data({"id": "456", "name": "devs", "description": ""}))

        patches: list[LivePatch] = []
        Team.generate_live_patch(expected, current, None, _live_patch_context(), patches.append)

        team_sync_patches = {patch.patch_type.name: patch for patch in patches if isinstance(patch.parent_object, Team)}
        assert set(team_sync_patches) == {"CHANGE", "REMOVE"}
        assert team_sync_patches["CHANGE"].expected_object.id == "123"
        assert team_sync_patches["REMOVE"].current_object.id == "456"
        # the current team is used as parent, as it knows the slug of the team
        assert all(patch.parent_object is current for patch in team_sync_patches.values())

    def test_generate_live_patch_for_changed_team_sync_id(self):
        # same name but a different group id: the group is identified by its id
        expected = self.team_with(team_sync=[{"id": "789", "name": "admins", "description": ""}])
        current = Team.from_provider_data(self.org_id, {**self.provider_data, "members": []})
        current.add_team_sync(TeamSync.from_model_data({"id": "123", "name": "admins", "description": ""}))

        patches: list[LivePatch] = []
        Team.generate_live_patch(expected, current, None, _live_patch_context(), patches.append)

        assert sorted((patch.patch_type.name, _team_sync_id(patch)) for patch in patches) == [
            ("ADD", "789"),
            ("REMOVE", "123"),
        ]

    def _to_jsonnet(self, team: Team) -> str:
        jsonnet_config = stub(
            create_org_team=JsonnetConfig.create_org_team,
            create_org_team_sync=JsonnetConfig.create_org_team_sync,
            default_team_sync_config=_default_config(JsonnetConfig.create_org_team_sync),
        )
        default_team = Team.from_model_data(_default_config(JsonnetConfig.create_org_team))

        output = StringIO()
        team.to_jsonnet(IndentingPrinter(output), jsonnet_config, stub(), False, default_team)
        return output.getvalue()

    def test_to_jsonnet_without_team_sync(self):
        output = self._to_jsonnet(Team.from_provider_data(self.org_id, self.provider_data))

        assert output.startswith("orgs.newTeam('Test Team') {")
        assert "name:" not in output
        assert "team_sync" not in output

    def test_to_jsonnet_with_team_sync(self):
        team = Team.from_provider_data(self.org_id, {**self.provider_data, "external_groups": []})
        team.add_team_sync(TeamSync.from_model_data({"id": "123", "name": "admins", "description": "The admins"}))

        output = self._to_jsonnet(team)

        assert output.startswith("orgs.newTeam('Test Team') {")
        assert 'name: "Test Team"' not in output
        # members are provisioned by the identity provider
        assert "members" not in output
        assert "external_group_id" not in output
        assert "team_sync: [" in output
        assert "orgs.newTeamSync('123') {" in output
        assert 'name: "admins",' in output
        assert 'description: "The admins",' in output

    def test_to_jsonnet_with_external_group(self):
        team = Team.from_provider_data(
            self.org_id, {**self.provider_data, "external_groups": [{"group_id": 123, "group_name": "admins"}]}
        )

        output = self._to_jsonnet(team)

        assert "external_group_id: 123," in output
        assert "members" not in output
