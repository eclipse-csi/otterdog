#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pretend import stub

from otterdog.models import github_organization
from otterdog.models.github_organization import _process_single_repo, _skip_unavailable_secrets
from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.secret_client import SecretScope, SecretsNotAvailableError


def not_available(scope=SecretScope.ORGANIZATION_CODESPACES, path="/orgs/org/codespaces/secrets"):
    return SecretsNotAvailableError(scope, path, GitHubException(f"https://api.github.com{path}", 404, "Not Found"))


@pytest.fixture(autouse=True)
def reset_warnings(monkeypatch):
    monkeypatch.setattr(github_organization, "_warned_unavailable_secrets", set())


@pytest.mark.parametrize("declared", [None, []])
def test_unavailable_secrets_are_skipped_with_a_warning(declared, caplog):
    with caplog.at_level(logging.WARNING, logger="otterdog"):
        _skip_unavailable_secrets(not_available(), "org", declared)

    assert "organization_codespaces secrets of 'org' are not available" in caplog.text
    assert "/orgs/org/codespaces/secrets" in caplog.text


def test_unavailable_secrets_are_warned_about_once_per_organization_and_scope(caplog):
    error = not_available(SecretScope.REPOSITORY_CODESPACES, "/repos/org/repo/codespaces/secrets")

    with caplog.at_level(logging.WARNING, logger="otterdog"):
        for _ in range(3):
            _skip_unavailable_secrets(error, "org", None)

    assert caplog.text.count("are not available") == 1


def test_declared_secrets_that_are_not_available_are_an_error():
    with pytest.raises(RuntimeError, match="declares organization_codespaces secrets which cannot be managed"):
        _skip_unavailable_secrets(not_available(), "org", [stub(name="TOKEN")])


def minimal_config():
    return SimpleNamespace(
        default_repo_config={},
        default_branch_protection_rule_config=None,
        default_repo_ruleset_config=None,
        default_repo_actions_policy_config=None,
        default_org_webhook_config=None,
        default_repo_secret_config=None,
        default_repo_dependabot_secret_config=None,
        default_repo_codespaces_secret_config={},
        default_repo_variable_config=None,
        default_environment_config=None,
        default_environment_secret_config=None,
        default_environment_variable_config=None,
    )


def expected_org_declaring(codespaces_secrets):
    expected_repo = stub(team_permissions=None, codespaces_secrets=codespaces_secrets, workflows=stub(keys=list))
    return stub(get_repository_by_name_or_alias=lambda name: expected_repo)


async def load_repo_codespaces_secrets(expected_org=None):
    repo_data = {"id": 1, "node_id": "repo-node", "name": "backend", "private": False}
    repository = stub(codespaces_secrets=[], unset_team_permissions=lambda: None)
    repository.add_codespaces_secret = repository.codespaces_secrets.append
    provider = stub(
        rest_api=stub(
            repo=stub(get_repo_data=AsyncMock(return_value=repo_data), get_workflow_settings=AsyncMock(return_value={}))
        ),
        get_repo_codespaces_secrets=AsyncMock(
            side_effect=not_available(SecretScope.REPOSITORY_CODESPACES, "/repos/org/backend/codespaces/secrets")
        ),
    )

    with (
        patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository),
        patch.object(RepositoryWorkflowSettings, "from_provider_data"),
    ):
        await _process_single_repo(provider, "org", "backend", minimal_config(), {}, None, {}, expected_org)

    return repository.codespaces_secrets


async def test_unavailable_repo_codespaces_secrets_are_skipped(caplog):
    with caplog.at_level(logging.WARNING, logger="otterdog"):
        assert await load_repo_codespaces_secrets() == []
        assert await load_repo_codespaces_secrets(expected_org_declaring([])) == []

    assert caplog.text.count("repository_codespaces secrets of 'org' are not available") == 1


async def test_unavailable_repo_codespaces_secrets_declared_by_the_repo_are_an_error():
    with pytest.raises(RuntimeError, match="declares repository_codespaces secrets which cannot be managed"):
        await load_repo_codespaces_secrets(expected_org_declaring([stub(name="TOKEN")]))
