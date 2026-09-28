#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from otterdog.providers.github.exception import InsufficientPermissionsException
from otterdog.providers.github.rest.secret_client import SecretScope

if TYPE_CHECKING:
    from .conftest import GitHubProviderTestKit


@pytest.fixture(params=list(SecretScope))
def secret_endpoint(request):
    scope = request.param
    if scope is SecretScope.ENVIRONMENT:
        path = "/repos/test-org/test-repo/environments/test-env/secrets"
    elif scope.value.startswith("organization_"):
        path = f"/orgs/test-org/{scope.value.removeprefix('organization_')}/secrets"
    else:
        path = f"/repos/test-org/test-repo/{scope.value.removeprefix('repository_')}/secrets"
    return scope, path


@pytest.mark.parametrize("status", [403, 404, 500])
async def test_failed_secret_reads_never_return_empty_data(github: GitHubProviderTestKit, secret_endpoint, status):
    """Every enabled scope aborts an incomplete read instead of erasing imported secrets."""
    scope, path = secret_endpoint
    github.http.expect(
        "GET", path, request_params={"per_page": "100"}, response_status=status, response_text="read failed"
    )

    with pytest.raises(RuntimeError, match=f"failed retrieving {scope.value} secrets"):
        await github.provider.rest_api.secret.get(scope, "test-org", "test-repo", "test-env")


async def test_missing_oauth_scopes_remain_actionable(github: GitHubProviderTestKit, secret_endpoint):
    """Missing OAuth scopes retain their typed exception and permission diagnostics."""
    scope, path = secret_endpoint
    github.http.expect(
        "GET",
        path,
        request_params={"per_page": "100"},
        response_status=403,
        response_headers={"X-OAuth-Scopes": "read:org", "X-Accepted-OAuth-Scopes": "repo"},
        response_text="missing scopes",
    )

    with pytest.raises(InsufficientPermissionsException) as error:
        await github.provider.rest_api.secret.get(scope, "test-org", "test-repo", "test-env")

    assert error.value.missing_scopes == ["repo"]


async def test_successful_empty_secret_reads_are_allowed(github: GitHubProviderTestKit, secret_endpoint):
    """A scope with no secrets is valid when GitHub actually confirms it is empty."""
    scope, path = secret_endpoint
    github.http.expect("GET", path, request_params={"per_page": "100"}, response_json={"secrets": []})

    assert await github.provider.rest_api.secret.get(scope, "test-org", "test-repo", "test-env") == []
