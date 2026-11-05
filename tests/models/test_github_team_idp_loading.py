#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from pretend import stub

from otterdog.models.github_organization import _TeamIdentityProviderGroupLoader

GROUP_ADMINS = {"group_id": "123", "group_name": "admins", "group_description": "The admins"}
EXTERNAL_GROUP = {"group_id": 123, "group_name": "admins", "updated_at": "2026-01-01T00:00:00Z"}


def jsonnet_config(team_sync: bool, external_groups: bool) -> SimpleNamespace:
    default_team_config: dict[str, Any] = {"name": "default", "members": []}
    if external_groups:
        default_team_config["external_group_id"] = None

    return SimpleNamespace(
        default_team_config=default_team_config,
        default_team_sync_config={"id": "default", "name": "", "description": ""} if team_sync else None,
    )


def provider(team_sync_groups: Any = None, external_groups: Any = None):
    return stub(
        get_org_team_sync_groups=AsyncMock(return_value=team_sync_groups),
        get_org_team_external_groups=AsyncMock(return_value=external_groups),
    )


async def test_groups_not_retrieved_if_not_supported_by_default_config():
    gh_provider = provider([GROUP_ADMINS], [EXTERNAL_GROUP])
    loader = _TeamIdentityProviderGroupLoader(gh_provider, "org", jsonnet_config(False, False))
    team_data: dict[str, Any] = {}

    await loader.add_external_groups("team", team_data)

    assert team_data == {}
    assert await loader.get_team_sync_groups("team") == []
    gh_provider.get_org_team_sync_groups.assert_not_awaited()
    gh_provider.get_org_team_external_groups.assert_not_awaited()


async def test_groups_retrieved_if_supported_by_default_config():
    gh_provider = provider([GROUP_ADMINS], [EXTERNAL_GROUP])
    loader = _TeamIdentityProviderGroupLoader(gh_provider, "org", jsonnet_config(True, True))
    team_data: dict[str, Any] = {}

    await loader.add_external_groups("team", team_data)
    team_sync_groups = await loader.get_team_sync_groups("team")

    assert team_data == {"external_groups": [EXTERNAL_GROUP]}
    assert [(ts.id, ts.name, ts.description) for ts in team_sync_groups] == [("123", "admins", "The admins")]


async def test_groups_skipped_once_not_available_for_the_organization():
    gh_provider = provider(None, None)
    loader = _TeamIdentityProviderGroupLoader(gh_provider, "org", jsonnet_config(True, True))

    for team_slug in ["team-1", "team-2"]:
        team_data: dict[str, Any] = {}
        await loader.add_external_groups(team_slug, team_data)

        # the team is not connected to an external group, so that a configured one is detected as change
        assert team_data == {"external_groups": []}
        assert await loader.get_team_sync_groups(team_slug) == []

    gh_provider.get_org_team_external_groups.assert_awaited_once_with("org", "team-1")
    gh_provider.get_org_team_sync_groups.assert_awaited_once_with("org", "team-1")
