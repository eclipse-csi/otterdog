#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from pathlib import Path

import pytest
from pretend import stub

from otterdog.config import OtterdogConfig
from otterdog.jsonnet import JsonnetConfig
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.repository import Repository
from otterdog.unmanaged import (
    DEPENDENCIES,
    RESOURCES,
    clear_unmanaged_resources,
    declared_unmanaged_resources,
    drop_unmanaged,
    unmanaged_repository_settings,
    unset_unmanaged_settings,
    valid_paths,
    validate_paths,
)
from otterdog.utils import UNSET

_DEFAULTS = Path(__file__).parent.parent / "otterdog" / "resources" / "defaults" / "otterdog-defaults.libsonnet"

# the cases of a free organization
_FREE_ORGANIZATION = [
    "organization.settings.workflows.max_cache_size_gb",
    "repository.workflows.max_cache_size_gb",
    "organization.codespaces_secrets",
    "repository.codespaces_secrets",
    "team.external_group_id",
    "team.team_sync",
]


def test_the_settings_and_resources_that_can_be_unmanaged():
    paths = valid_paths()

    assert set(_FREE_ORGANIZATION) <= set(paths)
    assert "organization.settings.members_can_create_private_pages" in paths
    assert set(RESOURCES) <= set(paths)
    # keys of a resource and nested models are not settings
    assert "team.name" not in paths
    assert "repository.name" not in paths
    assert "repository.workflows" not in paths
    assert "repository.secrets" in paths


def test_valid_paths_are_accepted():
    assert validate_paths(_FREE_ORGANIZATION, "test") == frozenset(_FREE_ORGANIZATION)
    assert validate_paths([], "test") == frozenset()


@pytest.mark.parametrize(
    "path,hint",
    [
        ("repository.workflows.max_cache_size", "repository.workflows.max_cache_size_gb"),
        ("repository.codespace_secrets", "repository.codespaces_secrets"),
        ("codespaces_secrets", None),
        ("repository.name", None),
        (42, None),
    ],
)
def test_invalid_paths_are_reported_with_a_hint(path, hint):
    with pytest.raises(RuntimeError) as exc_info:
        validate_paths([path], "organization 'my-org'")

    message = str(exc_info.value)
    assert "invalid 'unmanaged' of organization 'my-org'" in message
    assert "repository.codespaces_secrets" in message  # the valid resources are listed
    if hint is not None:
        assert f"did you mean '{hint}'" in message or f"or '{hint}'" in message


def _otterdog_config(tmp_path, global_unmanaged, org_unmanaged=None) -> OtterdogConfig:
    organization = {"name": "my-org", "github_id": "my-org", "credentials": {"provider": "plain"}}
    if org_unmanaged is not None:
        organization["unmanaged"] = org_unmanaged

    return OtterdogConfig.from_dict(
        {
            "defaults": {"github": {"unmanaged": global_unmanaged}, "jsonnet": {"base_template": str(_DEFAULTS)}},
            "organizations": [organization],
        },
        False,
        str(tmp_path),
    )


def test_the_global_and_the_organization_list_are_combined(tmp_path):
    config = _otterdog_config(tmp_path, ["repository.codespaces_secrets"], ["team.team_sync"])

    assert config.get_organization_config("my-org").jsonnet_config.unmanaged == frozenset(
        {"repository.codespaces_secrets", "team.team_sync"}
    )


def test_an_invalid_entry_fails_the_loading_of_the_configuration(tmp_path):
    with pytest.raises(RuntimeError, match="invalid 'unmanaged' of organization 'my-org'"):
        _otterdog_config(tmp_path, [], ["repository.workflows.max_cache"])


def test_nothing_is_unmanaged_by_default(tmp_path):
    config = _otterdog_config(tmp_path, [])

    assert config.get_organization_config("my-org").jsonnet_config.unmanaged == frozenset()


async def _default_configs(tmp_path, unmanaged):
    jsonnet_config = JsonnetConfig("my-org", str(tmp_path / "orgs"), str(_DEFAULTS), True, unmanaged=unmanaged)
    await jsonnet_config.init_template()
    return jsonnet_config


async def test_the_default_config_defines_everything_that_is_not_unmanaged(tmp_path):
    config = await _default_configs(tmp_path, [])

    assert config.default_org_codespaces_secret_config is not None
    assert config.default_repo_codespaces_secret_config is not None
    assert "max_cache_size_gb" in config.default_repo_config["workflows"]
    assert "max_cache_size_gb" in config.default_org_config["settings"]["workflows"]
    assert "external_group_id" in config.default_team_config
    assert config.default_team_sync_config is not None


async def test_unmanaged_settings_and_resources_are_removed_from_the_default_config(tmp_path):
    config = await _default_configs(tmp_path, _FREE_ORGANIZATION)

    assert config.default_org_codespaces_secret_config is None
    assert config.default_repo_codespaces_secret_config is None
    assert "max_cache_size_gb" not in config.default_repo_config["workflows"]
    assert "max_cache_size_gb" not in config.default_org_config["settings"]["workflows"]
    assert "external_group_id" not in config.default_team_config
    assert config.default_team_sync_config is None

    # everything else is untouched
    assert config.default_org_secret_config is not None
    assert config.default_repo_secret_config is not None
    assert config.default_repo_config["workflows"]["allowed_actions"] == "all"
    assert "description" in config.default_team_config


async def test_unmanaged_organization_settings_are_removed_from_the_default_config(tmp_path):
    config = await _default_configs(tmp_path, ["organization.settings.members_can_create_private_pages"])

    assert "members_can_create_private_pages" not in config.default_org_config["settings"]
    assert "members_can_create_public_pages" in config.default_org_config["settings"]
    # the default config of an organization is available for any project
    assert "members_can_create_private_pages" not in config.default_org_config_for_org_id("p", "o")["settings"]


async def test_unmanaged_repository_settings_are_removed_from_the_default_config(tmp_path):
    config = await _default_configs(tmp_path, ["repository.has_discussions", "repository.workflows.allowed_actions"])

    assert "has_discussions" not in config.default_repo_config
    assert "has_issues" in config.default_repo_config
    assert "allowed_actions" not in config.default_repo_config["workflows"]


def _organization(**attributes):
    settings = OrganizationSettings.from_model_data(
        {
            "plan": "free",
            "members_can_create_private_pages": True,
            "workflows": {"max_cache_size_gb": 10, "allowed_actions": "all"},
        }
    )
    repositories = [
        Repository.from_model_data(
            {
                "name": name,
                "has_discussions": True,
                "workflows": {"max_cache_size_gb": 10, "enabled": True},
            }
        )
        for name in ("repo-1", "repo-2")
    ]
    return stub(settings=settings, repositories=repositories, teams=[], **attributes)


def test_unmanaged_settings_of_a_loaded_organization_are_unset():
    organization = _organization()

    unset_unmanaged_settings(
        organization,
        [
            "organization.settings.members_can_create_private_pages",
            "organization.settings.workflows.max_cache_size_gb",
            "repository.has_discussions",
            "repository.workflows.max_cache_size_gb",
        ],
    )

    assert organization.settings.members_can_create_private_pages is UNSET
    assert organization.settings.workflows.max_cache_size_gb is UNSET
    assert organization.settings.workflows.allowed_actions == "all"
    for repository in organization.repositories:
        assert repository.has_discussions is UNSET
        assert repository.workflows.max_cache_size_gb is UNSET
        assert repository.workflows.enabled is True


def test_a_loaded_organization_is_not_changed_without_unmanaged_settings():
    organization = _organization()

    unset_unmanaged_settings(organization, [])
    # resources are not unset, they are not loaded in the first place
    unset_unmanaged_settings(organization, ["repository.codespaces_secrets"])

    assert organization.settings.members_can_create_private_pages is True
    assert all(r.has_discussions is True for r in organization.repositories)


def test_declared_resources_that_are_unmanaged_are_reported():
    organization = _organization(codespaces_secrets=[1, 2])
    organization.repositories[0].codespaces_secrets = [1]
    organization.repositories[1].codespaces_secrets = [1, 2, 3]
    organization.teams.append(stub(team_sync=[1]))

    declared = declared_unmanaged_resources(
        organization,
        ["organization.codespaces_secrets", "repository.codespaces_secrets", "team.team_sync", "repository.secrets"],
    )

    assert declared == {
        "organization.codespaces_secrets": 2,
        "repository.codespaces_secrets": 4,
        "team.team_sync": 1,
    }


def test_no_declared_resources_are_reported_if_none_is_declared():
    organization = _organization(codespaces_secrets=[])

    assert declared_unmanaged_resources(organization, ["organization.codespaces_secrets"]) == {}


@pytest.mark.parametrize("path", sorted(DEPENDENCIES))
def test_settings_that_others_depend_on_cannot_be_unmanaged(path):
    assert path not in valid_paths()

    with pytest.raises(RuntimeError, match=f"'{path}' cannot be unmanaged, "):
        validate_paths([path], "test")


def test_unmanaged_resources_are_removed_from_an_organization():
    organization = _organization(codespaces_secrets=[1, 2], secrets=[1])
    organization.repositories[0].codespaces_secrets = [1]
    organization.repositories[1].secrets = [1, 2]
    organization.teams.append(stub(team_sync=[1]))

    clear_unmanaged_resources(
        organization, ["organization.codespaces_secrets", "repository.codespaces_secrets", "team.team_sync"]
    )

    assert organization.codespaces_secrets == []
    assert organization.repositories[0].codespaces_secrets == []
    assert organization.teams[0].team_sync == []
    # the resources that are managed are untouched
    assert organization.secrets == [1]
    assert organization.repositories[1].secrets == [1, 2]


def test_everything_unmanaged_is_dropped_from_an_organization():
    organization = _organization(codespaces_secrets=[1])

    drop_unmanaged(organization, ["organization.codespaces_secrets", "repository.has_discussions"])

    assert organization.codespaces_secrets == []
    assert all(r.has_discussions is UNSET for r in organization.repositories)


def test_the_unmanaged_settings_of_repositories():
    assert unmanaged_repository_settings(
        [
            "repository.topics",
            "repository.custom_properties",
            "repository.workflows.max_cache_size_gb",
            "repository.codespaces_secrets",
            "organization.settings.plan",
            "team.description",
        ]
    ) == frozenset({"topics", "custom_properties"})


def _populated_organization():
    """An organization with everything other models of the configuration depend on."""
    from otterdog.models.github_organization import GitHubOrganization

    data = json.loads(Path(__file__).parent.joinpath("models", "resources", "otterdogtest.json").read_text())
    data["project_name"] = "otterdog"
    data["github_id"] = "OtterdogTest"
    data["settings"]["custom_properties"] = [
        {
            "name": "tier",
            "value_type": "string",
            "required": False,
            "default_value": None,
            "description": None,
            "allowed_values": [],
            "values_editable_by": "org_actors",
        }
    ]
    data["settings"]["workflows"] = {
        "enabled_repositories": "selected",
        "selected_repositories": ["other-repo"],
        "allowed_actions": "selected",
        "default_workflow_permissions": "read",
        "actions_can_approve_pull_request_reviews": False,
        "max_cache_size_gb": 10,
    }
    for repository in data["repositories"]:
        repository["custom_properties"] = {"tier": "gold"}
        repository["workflows"] = {
            "enabled": True,
            "allowed_actions": "all",
            "default_workflow_permissions": "write",
            "actions_can_approve_pull_request_reviews": True,
            "max_cache_size_gb": 10,
        }

    return GitHubOrganization.from_model_data(data)


def _patches(expected, current):
    from otterdog.models import LivePatchContext

    context = LivePatchContext("OtterdogTest", "*", False, False, "*", current.settings, expected.settings)
    patches: list = []
    expected.generate_live_patch(current, context, patches.append)
    return patches


@pytest.mark.parametrize("path", valid_paths())
def test_unmanaging_any_path_does_not_break_the_comparison(path):
    """
    Other models read settings of the organization, e.g. to coerce the settings of its repositories. A setting that
    is read must not be unmanageable: its value is no longer set when comparing, which would raise.
    """
    expected, current = _populated_organization(), _populated_organization()

    drop_unmanaged(expected, [path])
    drop_unmanaged(current, [path])

    assert _patches(expected, current) == []
