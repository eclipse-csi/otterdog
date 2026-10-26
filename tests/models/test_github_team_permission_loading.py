#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pretend import stub

from otterdog.models.github_organization import GitHubOrganization, _process_single_repo
from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
from otterdog.models.repository import Repository

LIVE_PERMISSIONS = {
    "backend": [
        {"name": "eclipsefdn-releng", "permission": "WRITE"},
        {"name": "technology-cbi-committers", "permission": "WRITE"},
        {"name": "technology-cbi-project-leads", "permission": "MAINTAIN"},
    ]
}

EXCLUDE_TEAMS = re.compile(".*-project-leads|.*-committers")


def minimal_config(default_repo_config=None):
    return SimpleNamespace(
        default_repo_config=default_repo_config or {},
        default_branch_protection_rule_config=None,
        default_repo_ruleset_config=None,
        default_org_webhook_config=None,
        default_repo_secret_config=None,
        default_repo_variable_config=None,
        default_environment_config=None,
        default_environment_secret_config=None,
        default_environment_variable_config=None,
    )


def expected_org_declaring(team_permissions):
    expected_repo = stub(team_permissions=team_permissions, workflows=stub(keys=list))
    return stub(get_repository_by_name_or_alias=lambda name: expected_repo)


def repository_provider():
    repo_data = {"id": 1, "node_id": "repo-node", "name": "backend", "private": False}
    repository = stub(team_permissions=None)
    repository.set_team_permissions = lambda permissions: setattr(repository, "team_permissions", permissions)
    rest_repo = stub(
        get_repo_data=AsyncMock(return_value=repo_data),
        get_workflow_settings=AsyncMock(return_value={}),
    )
    return stub(rest_api=stub(repo=rest_repo)), repository


async def load_team_permissions(exclude_teams, expected_org=None, config=None):
    provider, repository = repository_provider()
    with (
        patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository),
        patch("otterdog.models.github_organization.RepositoryWorkflowSettings.from_provider_data"),
    ):
        await _process_single_repo(
            provider,
            "eclipse-cbi",
            "backend",
            config or minimal_config(),
            {},
            LIVE_PERMISSIONS,
            {},
            expected_org,
            exclude_teams,
        )
    return repository.team_permissions


@pytest.mark.parametrize("expected_org", [None, stub(get_repository_by_name_or_alias=lambda name: None)])
async def test_permissions_of_excluded_teams_are_ignored(expected_org):
    assert await load_team_permissions(EXCLUDE_TEAMS, expected_org) == {"eclipsefdn-releng": "WRITE"}


async def test_permissions_are_kept_without_exclusion_pattern():
    assert await load_team_permissions(None) == {
        "eclipsefdn-releng": "WRITE",
        "technology-cbi-committers": "WRITE",
        "technology-cbi-project-leads": "MAINTAIN",
    }


async def test_permissions_of_excluded_teams_declared_by_the_repo_are_kept():
    expected_org = expected_org_declaring({"technology-cbi-committers": "push"})

    assert await load_team_permissions(EXCLUDE_TEAMS, expected_org) == {
        "eclipsefdn-releng": "WRITE",
        "technology-cbi-committers": "WRITE",
    }


async def test_excluded_team_removal_is_not_planned(repository_test):
    expected_repo = Repository.from_model_data(repository_test.model_data)
    expected_repo.set_team_permissions({"eclipsefdn-releng": "push"})
    current_repo = Repository.from_model_data(repository_test.model_data)
    current_repo.set_team_permissions(
        await load_team_permissions(EXCLUDE_TEAMS, expected_org_declaring(expected_repo.team_permissions))
    )

    assert "team_permissions" not in expected_repo.get_difference_from(current_repo)


async def test_excluded_team_permissions_declared_by_a_renamed_repo_are_kept(repository_test):
    expected_repo = Repository.from_model_data(repository_test.model_data)
    expected_repo.name = "backend-renamed"
    expected_repo.aliases = ["backend"]
    expected_repo.workflows = RepositoryWorkflowSettings.from_model_data({})
    expected_repo.set_team_permissions({"eclipsefdn-releng": "push", "technology-cbi-committers": "push"})
    expected_org = GitHubOrganization("technology.cbi", "eclipse-cbi", stub(), repositories=[expected_repo])

    current_repo = Repository.from_model_data(repository_test.model_data)
    current_repo.set_team_permissions(await load_team_permissions(EXCLUDE_TEAMS, expected_org))

    assert "team_permissions" not in expected_repo.get_difference_from(current_repo)


async def test_import_keeps_permission_overrides_of_excluded_teams_declared_by_defaults(repository_test):
    default_permissions = {"technology-cbi-project-leads": "push"}
    default_repo = Repository.from_model_data(repository_test.model_data)
    default_repo.set_team_permissions(default_permissions)

    imported_repo = Repository.from_model_data(repository_test.model_data)
    imported_repo.set_team_permissions(
        await load_team_permissions(EXCLUDE_TEAMS, config=minimal_config({"team_permissions": default_permissions}))
    )

    # the imported configuration overrides the default permission with the live one
    assert imported_repo.get_patch_to(default_repo)["team_permissions"] == {
        "eclipsefdn-releng": "push",
        "technology-cbi-project-leads": "maintain",
    }
