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
    declared_unmanaged_settings,
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


_ABSENT = object()


def _two_organizations(tmp_path, global_unmanaged=_ABSENT, org_unmanaged=_ABSENT) -> OtterdogConfig:
    github = {} if global_unmanaged is _ABSENT else {"unmanaged": global_unmanaged}
    second = {"name": "b", "github_id": "b", "credentials": {"provider": "plain"}}
    if org_unmanaged is not _ABSENT:
        second["unmanaged"] = org_unmanaged

    return OtterdogConfig.from_dict(
        {
            "defaults": {"github": github, "jsonnet": {"base_template": str(_DEFAULTS)}},
            "organizations": [{"name": "a", "github_id": "a", "credentials": {"provider": "plain"}}, second],
        },
        False,
        str(tmp_path),
    )


async def test_an_invalid_entry_fails_only_the_organization_using_it(tmp_path):
    config = _two_organizations(tmp_path, org_unmanaged=["repository.workflows.max_cache"])

    # the configuration of all organizations is loaded, the other organization works
    first, second = (config.get_organization_config(name).jsonnet_config for name in "ab")
    await first.init_template()
    assert first.unmanaged_error is None

    with pytest.raises(RuntimeError, match=r"invalid 'unmanaged' of organization 'b'.*max_cache_size_gb"):
        await second.init_template()
    assert second.unmanaged == frozenset()


async def test_an_invalid_entry_of_the_defaults_is_reported_as_such(tmp_path):
    config = _two_organizations(tmp_path, global_unmanaged=["repository.nope"])

    for name in "ab":
        jsonnet_config = config.get_organization_config(name).jsonnet_config
        with pytest.raises(RuntimeError, match=r"invalid 'unmanaged' of defaults\.github: 'repository\.nope'"):
            await jsonnet_config.init_template()


@pytest.mark.parametrize("value", ["repository.topics", {"repository.topics": False}, 42, [["repository.topics"]]])
def test_a_list_of_paths_is_required(tmp_path, value):
    for config in (
        _two_organizations(tmp_path, org_unmanaged=value),
        _two_organizations(tmp_path, global_unmanaged=value),
    ):
        errors = [config.get_organization_config(name).jsonnet_config.unmanaged_error for name in "ab"]

        assert any(error is not None for error in errors)
        # an entry is never split into its characters or taken from the keys of a dict
        assert all("'r' is not" not in (error or "") for error in errors)


@pytest.mark.parametrize("global_unmanaged,org_unmanaged", [(None, _ABSENT), (_ABSENT, None), (None, None)])
def test_a_null_list_is_empty(tmp_path, global_unmanaged, org_unmanaged):
    config = _two_organizations(tmp_path, global_unmanaged, org_unmanaged)

    for name in "ab":
        jsonnet_config = config.get_organization_config(name).jsonnet_config
        assert jsonnet_config.unmanaged == frozenset()
        assert jsonnet_config.unmanaged_error is None


def test_the_organization_config_of_the_webapp_gets_the_unmanaged_paths(tmp_path):
    from otterdog.config import OrganizationConfig

    org_config = OrganizationConfig.of(
        "p", "o", ".otterdog", str(_DEFAULTS), {}, str(tmp_path), str(tmp_path), ["team.team_sync"], "an error"
    )

    assert org_config.jsonnet_config.unmanaged == frozenset({"team.team_sync"})
    assert org_config.jsonnet_config.unmanaged_error == "an error"


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


# unmanaging a setting may only remove changes from a plan, never add one: a setting that gates how others are
# compared or sent must not be unmanageable, these tests unmanage every valid path in the states that gate others

_REPOSITORY_STATES = {
    "archived": [False, True],
    "private": [False, True],
    "gh_pages_build_type": ["disabled", "legacy", "workflow"],
    "code_scanning_default_setup_enabled": [False, True],
}
_REPOSITORY_BASE = {
    "name": "r",
    "description": "d",
    "homepage": "",
    "has_wiki": False,
    "has_projects": False,
    "gh_pages_source_branch": "main",
    "gh_pages_source_path": "/",
    "gh_pages_cname": None,
    "code_scanning_default_query_suite": "default",
    "secret_scanning_push_protection": "disabled",
    "dependabot_security_updates_enabled": False,
    "topics": [],
    "allow_merge_commit": True,
}
_REPOSITORY_DIFFERENCES = {
    "description": "x",
    "homepage": "http://x",
    "has_wiki": True,
    "has_projects": True,
    "gh_pages_source_branch": "gh-pages",
    "gh_pages_source_path": "/docs",
    "gh_pages_cname": "x.org",
    "code_scanning_default_query_suite": "extended",
    "secret_scanning_push_protection": "enabled",
    "dependabot_security_updates_enabled": True,
    "topics": ["t"],
    "allow_merge_commit": False,
}


def _changed_fields_of_repository(expected, current, unmanaged):
    import dataclasses

    from otterdog.models import LivePatchContext

    expected, current = dataclasses.replace(expected), dataclasses.replace(current)
    for repository in (expected, current):
        unset_unmanaged_settings(stub(settings=None, repositories=[repository], teams=[]), unmanaged)

    context = LivePatchContext("o", "*", False, False, "*", None, OrganizationSettings.from_model_data({}))
    patches: list = []
    Repository.generate_live_patch(expected, current, None, context, patches.append)
    return {field for patch in patches for field in patch.changes}


@pytest.mark.parametrize(
    "path",
    [p for p in valid_paths() if p.startswith("repository.") and p not in RESOURCES and p.count(".") == 1],
)
def test_unmanaging_a_repository_setting_never_adds_a_change(path):
    import itertools

    name = path.removeprefix("repository.")
    for values in itertools.product(*_REPOSITORY_STATES.values()):
        data = {**_REPOSITORY_BASE, **dict(zip(_REPOSITORY_STATES, values, strict=True))}
        expected = Repository.from_model_data(data)
        current = Repository.from_model_data({**data, **_REPOSITORY_DIFFERENCES})

        added = _changed_fields_of_repository(expected, current, [path]) - _changed_fields_of_repository(
            expected, current, []
        )

        assert added <= {name}, f"{values}: unmanaging '{path}' adds changes of {sorted(added - {name})}"


@pytest.mark.parametrize(
    "path",
    [p for p in valid_paths() if p.startswith("organization.settings.") and p not in RESOURCES and p.count(".") == 2],
)
def test_unmanaging_an_organization_setting_never_adds_a_change(path):
    import itertools

    states = {
        "has_discussions": [False, True],
        "immutable_releases_enforced_repositories": ["all", "none", "selected"],
        "plan": ["free", "enterprise"],
    }
    differences = {
        "discussion_source_repository": "o/x",
        "immutable_releases_selected_repositories": ["x"],
        "description": "x",
        "billing_email": "x@x",
        "default_repository_permission": "write",
        "web_commit_signoff_required": True,
    }
    base = {
        "description": "d",
        "billing_email": "a@a",
        "default_repository_permission": "read",
        "web_commit_signoff_required": False,
        "discussion_source_repository": "o/y",
        "immutable_releases_selected_repositories": [],
    }

    def changed(expected, current, unmanaged):
        import dataclasses

        expected, current = dataclasses.replace(expected), dataclasses.replace(current)
        for settings in (expected, current):
            unset_unmanaged_settings(stub(settings=settings, repositories=[], teams=[]), unmanaged)
        difference = expected.get_difference_from(current)
        return set(difference) if difference else set()

    name = path.rsplit(".", 1)[1]
    for values in itertools.product(*states.values()):
        data = {**base, **dict(zip(states, values, strict=True))}
        expected = OrganizationSettings.from_model_data(data)
        current = OrganizationSettings.from_model_data({**data, **differences})

        added = changed(expected, current, [path]) - changed(expected, current, [])

        assert added <= {name}, f"{values}: unmanaging '{path}' adds changes of {sorted(added - {name})}"


# the members of a team connected to an identity provider are not compared, which depends on its external group:
# the setting is meant to skip reading the external groups of organizations that cannot use them
_TEAM_SETTINGS_THAT_ENABLE_OTHERS = {"team.external_group_id": {"members"}}


@pytest.mark.parametrize("path", [p for p in valid_paths() if p.startswith("team.") and p not in RESOURCES])
def test_unmanaging_a_team_setting_adds_no_change_unless_known(path):
    import dataclasses
    import itertools

    from otterdog.models.team import Team

    name = path.removeprefix("team.")
    allowed = {name} | _TEAM_SETTINGS_THAT_ENABLE_OTHERS.get(path, set())

    def changed(expected, current, unmanaged):
        expected, current = dataclasses.replace(expected), dataclasses.replace(current)
        for team in (expected, current):
            unset_unmanaged_settings(stub(settings=None, repositories=[], teams=[team]), unmanaged)
        difference = expected.get_difference_from(current)
        return set(difference) if difference else set()

    for skip_members, external_group_id in itertools.product([False, True], [None, 42]):
        data = {
            "name": "t",
            "privacy": "closed",
            "members": ["a"],
            "description": "d",
            "notifications": False,
            "skip_members": skip_members,
            "external_group_id": external_group_id,
        }
        expected = Team.from_model_data(data)
        current = Team.from_model_data(
            {**data, "members": ["a", "b"], "description": "x", "privacy": "secret", "notifications": True}
        )

        added = changed(expected, current, [path]) - changed(expected, current, [])

        assert added <= allowed, f"unmanaging '{path}' adds changes of {sorted(added - allowed)}"


def test_declared_external_groups_of_teams_are_reported_if_unmanaged():
    organization = _organization()
    organization.teams.extend([stub(external_group_id=42), stub(external_group_id=None), stub(external_group_id=UNSET)])

    assert declared_unmanaged_settings(organization, ["team.external_group_id"]) == {"team.external_group_id": 1}
    # nothing is reported if they are managed
    assert declared_unmanaged_settings(organization, ["team.description"]) == {}
    assert declared_unmanaged_settings(organization, []) == {}
