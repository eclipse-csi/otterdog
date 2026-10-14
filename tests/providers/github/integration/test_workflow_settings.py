#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest

from otterdog.models.organization_workflow_settings import OrganizationWorkflowSettings
from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
from otterdog.utils import is_set_and_present

from .conftest import GitHubProviderTestKit

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"


async def test_read_org_workflow_settings(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/permissions",
        response_json={"enabled_repositories": "none", "allowed_actions": "none"},
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/permissions/fork-pr-contributor-approval",
        response_json={"approval_policy": "first_time_contributors"},
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/cache/storage-limit",
        response_json={"max_cache_size_gb": 50},
    )

    provider_data = await github.provider.get_org_workflow_settings(ORG_ID)
    settings = OrganizationWorkflowSettings.from_provider_data(ORG_ID, provider_data)

    assert settings.max_cache_size_gb == 50


async def test_read_org_workflow_settings_ignores_unavailable_cache_limit(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/permissions",
        response_json={"enabled_repositories": "none", "allowed_actions": "none"},
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/permissions/fork-pr-contributor-approval",
        response_json={"approval_policy": "first_time_contributors"},
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/cache/storage-limit",
        response_status=403,
        response_text="cache limit unavailable",
    )

    provider_data = await github.provider.get_org_workflow_settings(ORG_ID)
    settings = OrganizationWorkflowSettings.from_provider_data(ORG_ID, provider_data)

    assert not is_set_and_present(settings.max_cache_size_gb)


async def test_read_org_workflow_settings_propagates_cache_limit_errors(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/permissions",
        response_json={"enabled_repositories": "none", "allowed_actions": "none"},
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/permissions/fork-pr-contributor-approval",
        response_json={"approval_policy": "first_time_contributors"},
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/cache/storage-limit",
        response_status=500,
        response_text="cache limit unavailable",
    )

    with pytest.raises(RuntimeError):
        await github.provider.get_org_workflow_settings(ORG_ID)


async def test_read_org_workflow_settings_rejects_incomplete_cache_limit_response(
    github: GitHubProviderTestKit,
):
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/permissions",
        response_json={"enabled_repositories": "none", "allowed_actions": "none"},
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/permissions/fork-pr-contributor-approval",
        response_json={"approval_policy": "first_time_contributors"},
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/cache/storage-limit",
        response_json={},
    )

    with pytest.raises(RuntimeError, match="max_cache_size_gb"):
        await github.provider.get_org_workflow_settings(ORG_ID)


async def test_update_org_workflow_settings(github: GitHubProviderTestKit):
    github.http.expect(
        "PUT",
        f"/orgs/{ORG_ID}/actions/cache/storage-limit",
        request_json={"max_cache_size_gb": 50},
        response_status=204,
    )

    provider_data = await OrganizationWorkflowSettings.dict_to_provider_data(
        ORG_ID, {"max_cache_size_gb": 50}, github.provider
    )
    await github.provider.update_org_workflow_settings(ORG_ID, provider_data)


async def test_read_repo_workflow_settings(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/permissions",
        response_json={"enabled": False, "allowed_actions": "none"},
    )
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/cache/storage-limit",
        response_json={"max_cache_size_gb": 50},
    )

    provider_data = await github.provider.get_repo_workflow_settings(ORG_ID, REPO_NAME, is_private=True)
    settings = RepositoryWorkflowSettings.from_provider_data(ORG_ID, provider_data)

    assert settings.max_cache_size_gb == 50


async def test_read_repo_workflow_settings_ignores_unavailable_cache_limit(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/permissions",
        response_json={"enabled": False, "allowed_actions": "none"},
    )
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/cache/storage-limit",
        response_status=403,
        response_text="cache limit unavailable",
    )

    provider_data = await github.provider.get_repo_workflow_settings(ORG_ID, REPO_NAME, is_private=True)
    settings = RepositoryWorkflowSettings.from_provider_data(ORG_ID, provider_data)

    assert not is_set_and_present(settings.max_cache_size_gb)


async def test_read_repo_workflow_settings_propagates_cache_limit_errors(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/permissions",
        response_json={"enabled": False, "allowed_actions": "none"},
    )
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/cache/storage-limit",
        response_status=500,
        response_text="cache limit unavailable",
    )

    with pytest.raises(RuntimeError):
        await github.provider.get_repo_workflow_settings(ORG_ID, REPO_NAME, is_private=True)


async def test_read_repo_workflow_settings_rejects_incomplete_cache_limit_response(
    github: GitHubProviderTestKit,
):
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/permissions",
        response_json={"enabled": False, "allowed_actions": "none"},
    )
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/cache/storage-limit",
        response_json={},
    )

    with pytest.raises(RuntimeError, match="max_cache_size_gb"):
        await github.provider.get_repo_workflow_settings(ORG_ID, REPO_NAME, is_private=True)


async def test_update_repo_workflow_settings(github: GitHubProviderTestKit):
    github.http.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/cache/storage-limit",
        request_json={"max_cache_size_gb": 50},
        response_status=204,
    )

    provider_data = await RepositoryWorkflowSettings.dict_to_provider_data(
        ORG_ID, {"max_cache_size_gb": 50}, github.provider
    )
    await github.provider.update_repo_workflow_settings(ORG_ID, REPO_NAME, provider_data, is_private=True)
