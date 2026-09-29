#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest.mock import AsyncMock

import pytest

from otterdog.providers.github.rest import repo_client

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


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch):
    """Skip the arbitrary wait performed after creating a repository."""
    monkeypatch.setattr(repo_client.asyncio, "sleep", AsyncMock())


def expect_repo_creation(github: GitHubProviderTestKit, private: bool) -> None:
    github.http.expect(
        "POST",
        f"/orgs/{ORG_ID}/repos",
        request_json={"name": REPO_NAME, "private": private, "auto_init": False},
        response_json={"name": REPO_NAME, "private": private},
    )


async def add_repo(github: GitHubProviderTestKit, private: bool, state: str) -> None:
    await github.provider.add_repo(
        ORG_ID,
        {"name": REPO_NAME, "private": private, "code_scanning_default_config": {"state": state}},
        None,
        [],
        None,
        False,
        False,
    )


async def test_add_repo_skips_disabling_unavailable_code_scanning(github: GitHubProviderTestKit, no_sleep):
    """Code scanning unavailable for a new repository (e.g. private without Code Security) is already disabled."""
    expect_repo_creation(github, private=True)
    github.http.expect(
        "GET",
        CODE_SCANNING_URL,
        response_status=403,
        response_json={"message": "Code Security must be enabled for this repository to use code scanning."},
    )

    await add_repo(github, private=True, state="not-configured")


async def test_add_repo_skips_disabling_not_configured_code_scanning(github: GitHubProviderTestKit, no_sleep):
    """A new repository without code scanning default setup does not need to be updated."""
    expect_repo_creation(github, private=False)
    github.http.expect("GET", CODE_SCANNING_URL, response_json={"state": "not-configured"})

    await add_repo(github, private=False, state="not-configured")


async def test_add_repo_disables_code_scanning_configured_by_org(github: GitHubProviderTestKit, no_sleep):
    """Code scanning enabled on a new repository, e.g. by an org code security configuration, gets disabled."""
    expect_repo_creation(github, private=False)
    github.http.expect("GET", CODE_SCANNING_URL, response_json={"state": "configured", "languages": ["python"]})
    github.http.expect(
        "PATCH",
        CODE_SCANNING_URL,
        request_json={"state": "not-configured"},
        response_json={"state": "not-configured"},
    )

    await add_repo(github, private=False, state="not-configured")


async def test_add_repo_configures_enabled_code_scanning(github: GitHubProviderTestKit, no_sleep):
    """Enabling code scanning on a new repository is applied after its creation."""
    expect_repo_creation(github, private=False)
    github.http.expect(
        "PATCH",
        CODE_SCANNING_URL,
        request_json={"state": "configured"},
        response_json={"state": "configured"},
    )

    await add_repo(github, private=False, state="configured")


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
