#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest

from .conftest import GitHubProviderTestKit

ORG_ID = "test-org"
REPO_NAME = "test-repo"
CODE_SCANNING_URL = f"/repos/{ORG_ID}/{REPO_NAME}/code-scanning/default-setup"


async def test_update_repo_code_scanning_config(github: GitHubProviderTestKit):
    """A supported repository receives the requested default code scanning configuration."""
    github.http.expect(
        "PATCH",
        CODE_SCANNING_URL,
        request_json={"state": "configured"},
        response_json={"state": "configured"},
    )

    await github.provider.update_repo(
        ORG_ID,
        REPO_NAME,
        {"code_scanning_default_config": {"state": "configured"}},
    )


async def test_update_repo_ignores_unavailable_code_scanning_when_disabled(github: GitHubProviderTestKit):
    """Disabling unavailable code scanning is an effective no-op for private repositories."""
    github.http.expect(
        "PATCH",
        CODE_SCANNING_URL,
        request_json={"state": "not-configured"},
        response_status=403,
        response_json={"message": "Code Security must be enabled for this repository to use code scanning."},
    )

    await github.provider.update_repo(
        ORG_ID,
        REPO_NAME,
        {"code_scanning_default_config": {"state": "not-configured"}},
    )


async def test_update_repo_propagates_unavailable_code_scanning_when_enabled(github: GitHubProviderTestKit):
    """Enabling unavailable code scanning remains a hard failure because the desired state is unsatisfiable."""
    github.http.expect(
        "PATCH",
        CODE_SCANNING_URL,
        request_json={"state": "configured"},
        response_status=403,
        response_json={"message": "Code Security must be enabled for this repository to use code scanning."},
    )

    with pytest.raises(RuntimeError, match="failed to update code scanning config"):
        await github.provider.update_repo(
            ORG_ID,
            REPO_NAME,
            {"code_scanning_default_config": {"state": "configured"}},
        )


async def test_update_repo_propagates_unrelated_code_scanning_errors(github: GitHubProviderTestKit):
    """A 403 unrelated to unavailable Code Security must still fail the repository update."""
    github.http.expect(
        "PATCH",
        CODE_SCANNING_URL,
        request_json={"state": "not-configured"},
        response_status=403,
        response_json={"message": "Resource access denied"},
    )

    with pytest.raises(RuntimeError, match="failed to update code scanning config"):
        await github.provider.update_repo(
            ORG_ID,
            REPO_NAME,
            {"code_scanning_default_config": {"state": "not-configured"}},
        )
