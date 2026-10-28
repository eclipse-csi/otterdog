#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pretend import stub

from otterdog.models.environment import Environment
from otterdog.models.environment_secret import EnvironmentSecret
from otterdog.models.environment_variable import EnvironmentVariable
from otterdog.models.github_organization import _process_single_repo
from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
from otterdog.utils import ExclusionPatterns

EXCLUDE_ENVIRONMENTS = ExclusionPatterns(["^external-.*"])
LIVE_ENVIRONMENTS = [{"name": "external-prod"}, {"name": "staging"}]


def minimal_config():
    return SimpleNamespace(
        default_repo_config={},
        default_branch_protection_rule_config=None,
        default_repo_ruleset_config=None,
        default_org_webhook_config=None,
        default_repo_secret_config=None,
        default_repo_dependabot_secret_config=None,
        default_repo_codespaces_secret_config=None,
        default_repo_variable_config=None,
        default_environment_config={},
        default_environment_secret_config={},
        default_environment_variable_config={},
    )


def expected_org_declaring(env_names):
    expected_repo = stub(
        team_permissions=None,
        environments=[stub(name=n) for n in env_names],
        workflows=stub(keys=list),
    )
    return stub(get_repository_by_name_or_alias=lambda name: expected_repo)


async def load_environments(exclude_environments, expected_org=None):
    repo_data = {"id": 1, "node_id": "repo-node", "name": "backend", "private": False}
    repository = stub(environments=[], unset_team_permissions=lambda: None)
    repository.add_environment = repository.environments.append
    get_secrets = AsyncMock(return_value=[{"name": "secret"}])
    get_variables = AsyncMock(return_value=[{"name": "variable"}])
    rest_repo = stub(
        get_repo_data=AsyncMock(return_value=repo_data),
        get_workflow_settings=AsyncMock(return_value={}),
        get_environments=AsyncMock(return_value=LIVE_ENVIRONMENTS),
        get_environment_variables=get_variables,
    )
    provider = stub(rest_api=stub(repo=rest_repo), get_environment_secrets=get_secrets)

    def provider_environment(_, data):
        env = SimpleNamespace(name=data["name"], repo_name=None, secrets=[], variables=[])
        env.add_secret = env.secrets.append
        env.add_variable = env.variables.append
        return env

    with (
        patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository),
        patch.object(RepositoryWorkflowSettings, "from_provider_data"),
        patch.object(Environment, "from_provider_data", side_effect=provider_environment),
        patch.object(EnvironmentSecret, "from_provider_data", side_effect=lambda _, data: data["name"]),
        patch.object(EnvironmentVariable, "from_provider_data", side_effect=lambda _, data: data["name"]),
    ):
        await _process_single_repo(
            provider,
            "eclipse-cbi",
            "backend",
            minimal_config(),
            {},
            None,
            {},
            expected_org,
            None,
            exclude_environments,
        )

    fetched = {
        "secrets": [c.args[2] for c in get_secrets.await_args_list],
        "variables": [c.args[2] for c in get_variables.await_args_list],
    }
    return repository.environments, fetched


async def test_excluded_environments_are_ignored():
    environments, _ = await load_environments(EXCLUDE_ENVIRONMENTS)

    assert [env.name for env in environments] == ["staging"]


async def test_environments_are_kept_without_exclusion():
    environments, _ = await load_environments(None)

    assert [env.name for env in environments] == ["external-prod", "staging"]


async def test_declared_excluded_environment_is_kept():
    environments, _ = await load_environments(EXCLUDE_ENVIRONMENTS, expected_org_declaring(["external-prod"]))

    assert [env.name for env in environments] == ["external-prod", "staging"]


async def test_children_of_excluded_environments_are_not_fetched():
    environments, fetched = await load_environments(EXCLUDE_ENVIRONMENTS)

    assert fetched == {"secrets": ["staging"], "variables": ["staging"]}
    assert environments[0].secrets == ["secret"]
    assert environments[0].variables == ["variable"]


async def test_children_of_declared_excluded_environments_are_managed():
    environments, fetched = await load_environments(EXCLUDE_ENVIRONMENTS, expected_org_declaring(["external-prod"]))

    assert fetched == {"secrets": ["external-prod", "staging"], "variables": ["external-prod", "staging"]}
    assert all(env.secrets == ["secret"] and env.variables == ["variable"] for env in environments)
