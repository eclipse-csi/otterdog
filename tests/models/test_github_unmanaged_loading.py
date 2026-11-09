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
