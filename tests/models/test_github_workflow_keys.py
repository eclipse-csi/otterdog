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


def minimal_config(default_workflows):
    return SimpleNamespace(
        default_repo_config={"workflows": default_workflows},
        default_branch_protection_rule_config=None,
        default_repo_ruleset_config=None,
        default_repo_actions_policy_config=None,
        default_org_webhook_config=None,
        default_repo_secret_config=None,
        default_repo_dependabot_secret_config=None,
        default_repo_codespaces_secret_config=None,
        default_repo_variable_config=None,
        default_environment_config=None,
        default_environment_secret_config=None,
        default_environment_variable_config=None,
    )


def expected_org_with(workflows):
    expected_repo = stub(team_permissions=None, workflows=workflows)
    return stub(get_repository_by_name_or_alias=lambda name: expected_repo)


async def requested_workflow_keys(default_workflows, expected_org=None):
    repo_data = {"id": 1, "node_id": "repo-node", "name": "backend", "private": False}
    repository = stub(unset_team_permissions=lambda: None)
    get_workflow_settings = AsyncMock(return_value={})
    provider = stub(
        rest_api=stub(
            repo=stub(get_repo_data=AsyncMock(return_value=repo_data), get_workflow_settings=get_workflow_settings)
        )
    )

    with (
        patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository),
        patch.object(RepositoryWorkflowSettings, "from_provider_data"),
    ):
        await _process_single_repo(
            provider, "org", "backend", minimal_config(default_workflows), {}, None, {}, expected_org
        )

    return get_workflow_settings.await_args.kwargs["included_keys"]


@pytest.mark.parametrize("expected_org", [None, expected_org_with(RepositoryWorkflowSettings.from_model_data({}))])
async def test_workflow_settings_of_the_default_config_are_requested(expected_org):
    keys = await requested_workflow_keys({"enabled": True, "max_cache_size_gb": 10}, expected_org)

    assert keys == {"enabled", "max_cache_size_gb"}


@pytest.mark.parametrize("expected_org", [None, expected_org_with(RepositoryWorkflowSettings.from_model_data({}))])
@pytest.mark.parametrize("default_workflows", [{"enabled": True}, {"enabled": True, "max_cache_size_gb": None}, None])
async def test_workflow_settings_missing_in_the_default_config_are_not_requested(default_workflows, expected_org):
    # also without an expected config, e.g. for import and show-live
    keys = await requested_workflow_keys(default_workflows, expected_org)

    assert "max_cache_size_gb" not in keys


async def test_workflow_settings_configured_explicitly_are_requested():
    expected_org = expected_org_with(RepositoryWorkflowSettings.from_model_data({"max_cache_size_gb": 20}))

    keys = await requested_workflow_keys({"enabled": True}, expected_org)

    assert keys == {"enabled", "max_cache_size_gb"}
