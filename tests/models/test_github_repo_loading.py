#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Verifies that the resources of a repository are retrieved concurrently."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pretend import stub

from otterdog.models.environment import Environment
from otterdog.models.environment_secret import EnvironmentSecret
from otterdog.models.environment_variable import EnvironmentVariable
from otterdog.models.github_organization import _process_single_repo
from otterdog.models.repo_ruleset import RepositoryRuleset
from otterdog.models.repo_variable import RepositoryVariable
from otterdog.models.repo_webhook import RepositoryWebhook
from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings


def config():
    return SimpleNamespace(
        default_repo_config={},
        default_branch_protection_rule_config=None,
        default_repo_ruleset_config={},
        default_org_webhook_config={},
        default_repo_secret_config=None,
        default_repo_dependabot_secret_config=None,
        default_repo_codespaces_secret_config=None,
        default_repo_variable_config={},
        default_environment_config={},
        default_environment_secret_config={},
        default_environment_variable_config={},
    )


def waiting_for(barrier: asyncio.Barrier, result):
    """Returns a request that only completes once all requests waiting for the barrier have been sent."""

    async def request(*_, **__):
        await barrier.wait()
        return result

    return AsyncMock(side_effect=request)


async def test_resources_of_a_repo_are_retrieved_concurrently():
    # sent one after the other, the first of these requests would wait for the others forever
    repo_requests = asyncio.Barrier(5)
    environment_requests = asyncio.Barrier(4)

    environments = [{"name": "prod"}, {"name": "staging"}]
    rest_repo = stub(
        get_repo_data=AsyncMock(return_value={"name": "backend", "private": False}),
        get_workflow_settings=waiting_for(repo_requests, {}),
        get_rulesets=waiting_for(repo_requests, [{"name": "ruleset"}]),
        get_webhooks=waiting_for(repo_requests, [{"url": "https://example.org"}]),
        get_variables=waiting_for(repo_requests, [{"name": "VARIABLE"}]),
        get_environments=waiting_for(repo_requests, environments),
        get_environment_variables=waiting_for(environment_requests, [{"name": "ENV_VARIABLE"}]),
    )
    provider = stub(
        rest_api=stub(repo=rest_repo),
        get_environment_secrets=waiting_for(environment_requests, [{"name": "ENV_SECRET"}]),
    )

    repository = SimpleNamespace(rulesets=[], webhooks=[], variables=[], environments=[])
    repository.add_ruleset = repository.rulesets.append
    repository.add_webhook = repository.webhooks.append
    repository.add_variable = repository.variables.append
    repository.add_environment = repository.environments.append
    repository.unset_team_permissions = lambda: None

    def provider_environment(_, data):
        env = SimpleNamespace(name=data["name"], repo_name=None, secrets=[], variables=[])
        env.add_secret = env.secrets.append
        env.add_variable = env.variables.append
        return env

    def by_name(_, data):
        return data.get("name", data.get("url"))

    with (
        patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository),
        patch.object(RepositoryWorkflowSettings, "from_provider_data"),
        patch.object(RepositoryRuleset, "from_provider_data", side_effect=by_name),
        patch.object(RepositoryWebhook, "from_provider_data", side_effect=by_name),
        patch.object(RepositoryVariable, "from_provider_data", side_effect=by_name),
        patch.object(Environment, "from_provider_data", side_effect=provider_environment),
        patch.object(EnvironmentSecret, "from_provider_data", side_effect=by_name),
        patch.object(EnvironmentVariable, "from_provider_data", side_effect=by_name),
    ):
        await asyncio.wait_for(
            _process_single_repo(provider, "eclipse-cbi", "backend", config(), {}, None, {}),
            timeout=5,
        )

    assert repository.rulesets == ["ruleset"]
    assert repository.webhooks == ["https://example.org"]
    assert repository.variables == ["VARIABLE"]
    assert [(env.name, env.secrets, env.variables) for env in repository.environments] == [
        ("prod", ["ENV_SECRET"], ["ENV_VARIABLE"]),
        ("staging", ["ENV_SECRET"], ["ENV_VARIABLE"]),
    ]


async def test_failure_of_a_resource_fails_the_repo_and_cancels_the_others():
    other_request = asyncio.Event()

    async def never_completed(*_, **__):
        other_request.set()
        await asyncio.Event().wait()

    async def failing(*_, **__):
        await other_request.wait()
        raise RuntimeError("failed retrieving webhooks")

    get_variables = AsyncMock(side_effect=never_completed)
    rest_repo = stub(
        get_repo_data=AsyncMock(return_value={"name": "backend", "private": False}),
        get_workflow_settings=AsyncMock(return_value={}),
        get_rulesets=AsyncMock(return_value=[]),
        get_webhooks=AsyncMock(side_effect=failing),
        get_variables=get_variables,
        get_environments=AsyncMock(return_value=[]),
    )
    provider = stub(rest_api=stub(repo=rest_repo))

    with (
        patch("otterdog.models.github_organization.Repository.from_provider_data"),
        patch.object(RepositoryWorkflowSettings, "from_provider_data"),
    ):
        loading = _process_single_repo(provider, "eclipse-cbi", "backend", config(), {}, None, {})

        # the variables are never retrieved, the repo would never fail if they were not cancelled
        with pytest.raises(RuntimeError, match="failed retrieving webhooks"):
            await asyncio.wait_for(loading, timeout=5)
