#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest.mock import AsyncMock

import pretend
import pytest

from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.secret_client import SecretClient, SecretScope, SecretsNotAvailableError


def test_environment_secret_path_url_encodes_environment_name() -> None:
    """A slash in an environment name must stay inside its URL path segment."""
    path = SecretClient._path(SecretScope.ENVIRONMENT, "org", "repo", "release/candidate")

    assert path == "/repos/org/repo/environments/release%2Fcandidate/secrets"


def _client_failing_with(status: int) -> SecretClient:
    requester = pretend.stub(
        request_paged_json=AsyncMock(side_effect=GitHubException("https://api.github.com/x", status, "Not Found"))
    )
    return SecretClient(pretend.stub(requester=requester))


@pytest.mark.parametrize(
    "scope,repo_name,path",
    [
        (SecretScope.ORGANIZATION_CODESPACES, None, "/orgs/org/codespaces/secrets"),
        (SecretScope.REPOSITORY_CODESPACES, "repo", "/repos/org/repo/codespaces/secrets"),
    ],
)
async def test_codespaces_secrets_not_found_are_reported_as_not_available(scope, repo_name, path) -> None:
    with pytest.raises(SecretsNotAvailableError) as exc_info:
        await _client_failing_with(404).get(scope, "org", repo_name)

    assert exc_info.value.scope is scope
    assert exc_info.value.path == path
    assert "might not be available" in str(exc_info.value)


@pytest.mark.parametrize(
    "scope,repo_name",
    [
        (SecretScope.ORGANIZATION_ACTIONS, None),
        (SecretScope.ORGANIZATION_DEPENDABOT, None),
        (SecretScope.REPOSITORY_DEPENDABOT, "repo"),
    ],
)
async def test_secrets_not_found_of_other_scopes_still_fail(scope, repo_name) -> None:
    with pytest.raises(RuntimeError) as exc_info:
        await _client_failing_with(404).get(scope, "org", repo_name)

    assert not isinstance(exc_info.value, SecretsNotAvailableError)


@pytest.mark.parametrize("status", [401, 403, 500])
async def test_other_errors_of_codespaces_secrets_still_fail(status) -> None:
    with pytest.raises(RuntimeError) as exc_info:
        await _client_failing_with(status).get(SecretScope.ORGANIZATION_CODESPACES, "org")

    assert not isinstance(exc_info.value, SecretsNotAvailableError)
