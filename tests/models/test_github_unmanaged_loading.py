#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pretend import stub

from otterdog.models.github_organization import _process_single_repo
from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings


def minimal_config(**overrides):
    values = {
        "unmanaged": frozenset(),
        "default_repo_config": {},
        "default_branch_protection_rule_config": None,
        "default_repo_ruleset_config": None,
        "default_org_webhook_config": None,
        "default_repo_webhook_config": None,
        "default_repo_secret_config": None,
        "default_repo_dependabot_secret_config": None,
        "default_repo_codespaces_secret_config": None,
        "default_repo_variable_config": None,
        "default_environment_config": None,
        "default_environment_secret_config": None,
        "default_environment_variable_config": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


async def load_repo(config):
    repo_data = {"id": 1, "node_id": "repo-node", "name": "backend", "private": False}
    repository = stub(webhooks=[], unset_team_permissions=lambda: None)
    repository.add_webhook = repository.webhooks.append
    get_repo_data = AsyncMock(return_value=repo_data)
    get_webhooks = AsyncMock(return_value=[])
    provider = stub(
        rest_api=stub(
            repo=stub(
                get_repo_data=get_repo_data,
                get_workflow_settings=AsyncMock(return_value={}),
                get_webhooks=get_webhooks,
            )
        )
    )

    with (
        patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository),
        patch.object(RepositoryWorkflowSettings, "from_provider_data"),
    ):
        await _process_single_repo(provider, "org", "backend", config, {}, None, {})

    return get_repo_data, get_webhooks


@pytest.mark.parametrize(
    "org_webhooks,repo_webhooks,expected_requests",
    [
        # repositories use the default config of repository webhooks, independent of the one of the organization
        ({}, None, 0),
        (None, {}, 1),
        ({}, {}, 1),
        (None, None, 0),
    ],
)
async def test_repository_webhooks_depend_on_the_default_config_of_repository_webhooks(
    org_webhooks, repo_webhooks, expected_requests
):
    config = minimal_config(default_org_webhook_config=org_webhooks, default_repo_webhook_config=repo_webhooks)

    _, get_webhooks = await load_repo(config)

    assert get_webhooks.await_count == expected_requests


async def test_the_unmanaged_settings_of_repositories_are_not_retrieved():
    config = minimal_config(
        unmanaged=frozenset(
            {
                "repository.topics",
                "repository.custom_properties",
                "repository.workflows.max_cache_size_gb",
                "repository.codespaces_secrets",
                "organization.settings.members_can_create_private_pages",
            }
        )
    )

    get_repo_data, _ = await load_repo(config)

    assert get_repo_data.await_args.args[2] == frozenset({"topics", "custom_properties"})


async def test_nothing_is_skipped_if_no_repository_setting_is_unmanaged():
    get_repo_data, _ = await load_repo(minimal_config())

    assert get_repo_data.await_args.args[2] == frozenset()


async def load_teams(unmanaged):
    from otterdog.models.github_organization import GitHubOrganization

    from . import ModelTest
    from .test_github_ruleset_loading import minimal_config as organization_config
    from .test_github_ruleset_loading import organization_provider

    team = ModelTest.load_json_resource("github-team.json")
    provider = organization_provider([])
    provider.get_org_teams = AsyncMock(return_value=[team])
    provider.get_org_team_members = AsyncMock(return_value=[{"login": "alice"}])
    config = organization_config(
        default_org_ruleset_config=None,
        default_team_config={"name": "default"},
        default_team_sync_config=None,
        unmanaged=frozenset(unmanaged),
        default_org_config_for_org_id=lambda project_name, org_id: {
            "project_name": project_name,
            "github_id": org_id,
            "settings": {},
        },
    )

    with patch("otterdog.models.github_organization.OrganizationSettings.from_provider_data") as settings_model:
        settings_model.return_value = SimpleNamespace(plan="free")
        organization = await GitHubOrganization.load_from_provider("project", "acme", config, provider)

    return organization, provider


async def test_the_members_of_teams_are_retrieved_unless_unmanaged():
    from otterdog.utils import UNSET

    organization, provider = await load_teams([])

    provider.get_org_team_members.assert_awaited_once()
    assert organization.teams[0].members == ["alice"]

    organization, provider = await load_teams(["team.members"])

    provider.get_org_team_members.assert_not_awaited()
    assert organization.teams[0].members is UNSET


@pytest.mark.parametrize("ruleset_config,expected_requests", [(None, 0), ({}, 1)])
async def test_the_teams_are_only_retrieved_to_resolve_the_bypass_actors_of_repository_rulesets(
    ruleset_config, expected_requests
):
    from otterdog.models.github_organization import _load_repos_from_provider

    get_org_teams = AsyncMock(return_value=[{"id": 1, "slug": "dev"}])
    provider = stub(
        get_repos=AsyncMock(return_value=[]),
        get_org_teams=get_org_teams,
        get_team_permissions=AsyncMock(return_value=[]),
    )
    config = minimal_config(default_repo_ruleset_config=ruleset_config, default_repo_config={"team_permissions": {}})

    repositories = [repo async for repo in _load_repos_from_provider("acme", provider, config, {})]

    assert repositories == []
    assert get_org_teams.await_count == expected_requests
