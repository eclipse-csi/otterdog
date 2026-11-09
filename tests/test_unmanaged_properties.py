#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Unmanaging a setting must only affect that setting.

Other parts of the configuration read the value of settings: to coerce the settings of repositories with the ones of
the organization, to decide which other settings are compared, to validate. A setting that is read this way cannot be
unmanaged, as its value is no longer set. These tests unmanage every valid path of a setting in states that exercise
such dependencies, and assert that the differences found when comparing organizations are the same, apart from the
setting itself, and that the validation neither fails nor finds new errors. A path that violates this must be listed
in ``otterdog.unmanaged.DEPENDENCIES``.
"""

import copy
import functools
import json
from pathlib import Path
from types import SimpleNamespace

import pretend
import pytest

from otterdog.models import FailureType, LivePatchContext
from otterdog.models.github_organization import GitHubOrganization
from otterdog.unmanaged import DEPENDENCIES, RESOURCES, drop_unmanaged, valid_paths

_RESOURCE = Path(__file__).parent / "models" / "resources" / "otterdogtest.json"

_CUSTOM_PROPERTY = {
    "name": "tier",
    "value_type": "string",
    "required": False,
    "default_value": None,
    "description": None,
    "allowed_values": [],
    "values_editable_by": "org_actors",
}


def _workflows(organization: dict, **overrides) -> dict:
    return {
        "enabled_repositories": "all",
        "allowed_actions": "all",
        "default_workflow_permissions": "read",
        "actions_can_approve_pull_request_reviews": False,
        **organization,
        **overrides,
    }


def _repository_workflows(**overrides) -> dict:
    return {
        "enabled": True,
        "allowed_actions": "all",
        "default_workflow_permissions": "read",
        "actions_can_approve_pull_request_reviews": False,
        "max_cache_size_gb": 10,
        **overrides,
    }


# every scenario is a pair of an expected and a current organization, the repository and the settings of the
# organization differ in the way that exposes a dependency
_SCENARIOS = {
    "organization restricts the workflows of repositories": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {
            "workflows": _repository_workflows(
                default_workflow_permissions="write", actions_can_approve_pull_request_reviews=True
            )
        },
        {"workflows": _repository_workflows()},
    ),
    "organization enables workflows for no repository": (
        {"workflows": _workflows({"enabled_repositories": "none"})},
        {"workflows": _workflows({"enabled_repositories": "none"})},
        {"workflows": _repository_workflows()},
        {"workflows": _repository_workflows(enabled=False)},
    ),
    "organization and repository select actions": (
        {
            "workflows": _workflows(
                {
                    "allowed_actions": "selected",
                    "allow_github_owned_actions": True,
                    "allow_verified_creator_actions": True,
                    "allow_action_patterns": ["a/*"],
                }
            )
        },
        {
            "workflows": _workflows(
                {
                    "allowed_actions": "selected",
                    "allow_github_owned_actions": False,
                    "allow_verified_creator_actions": False,
                    "allow_action_patterns": ["b/*"],
                }
            )
        },
        {
            "workflows": _repository_workflows(
                allowed_actions="selected",
                allow_github_owned_actions=True,
                allow_verified_creator_actions=True,
                allow_action_patterns=["x/*"],
            )
        },
        {
            "workflows": _repository_workflows(
                allowed_actions="selected",
                allow_github_owned_actions=False,
                allow_verified_creator_actions=False,
                allow_action_patterns=["y/*"],
            )
        },
    ),
    "repository selects actions while the organization allows all": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {
            "workflows": _repository_workflows(
                allowed_actions="selected",
                allow_github_owned_actions=True,
                allow_verified_creator_actions=True,
                allow_action_patterns=["x/*"],
            )
        },
        {
            "workflows": _repository_workflows(
                allowed_actions="selected",
                allow_github_owned_actions=False,
                allow_verified_creator_actions=False,
                allow_action_patterns=["y/*"],
            )
        },
    ),
    "repository changes its cache size": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {"workflows": _repository_workflows(max_cache_size_gb=20)},
        {"workflows": _repository_workflows()},
    ),
    "immutable releases of selected repositories": (
        {
            "immutable_releases_enforced_repositories": "selected",
            "immutable_releases_selected_repositories": ["web", "api"],
            "workflows": _workflows({}),
        },
        {
            "immutable_releases_enforced_repositories": "selected",
            "immutable_releases_selected_repositories": ["web"],
            "workflows": _workflows({}),
        },
        {},
        {},
    ),
    "immutable releases change from all to none": (
        {"immutable_releases_enforced_repositories": "all", "workflows": _workflows({})},
        {
            "immutable_releases_enforced_repositories": "none",
            "immutable_releases_selected_repositories": [],
            "workflows": _workflows({}),
        },
        {},
        {},
    ),
    "discussions of the organization": (
        {"has_discussions": True, "discussion_source_repository": "OtterdogTest/web", "workflows": _workflows({})},
        {"has_discussions": True, "discussion_source_repository": "OtterdogTest/web", "workflows": _workflows({})},
        {},
        {},
    ),
    "archived repository": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {"archived": True, "description": "new", "workflows": _repository_workflows(max_cache_size_gb=20)},
        {"archived": True, "description": "old", "workflows": _repository_workflows()},
    ),
    "private repository": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {"private": True, "secret_scanning_push_protection": "enabled", "dependabot_security_updates_enabled": True},
        {"private": True, "secret_scanning_push_protection": "disabled", "dependabot_security_updates_enabled": False},
    ),
    "github pages are disabled": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {"gh_pages_build_type": "disabled", "gh_pages_source_branch": "main", "gh_pages_source_path": "/"},
        {"gh_pages_build_type": "disabled", "gh_pages_source_branch": "gh-pages", "gh_pages_source_path": "/docs"},
    ),
    "code scanning is not set up": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {"code_scanning_default_setup_enabled": False, "code_scanning_default_query_suite": "default"},
        {"code_scanning_default_setup_enabled": False, "code_scanning_default_query_suite": "extended"},
    ),
    "discussions of the organization are disabled": (
        {"has_discussions": False, "discussion_source_repository": "OtterdogTest/a", "workflows": _workflows({})},
        {"has_discussions": False, "discussion_source_repository": "OtterdogTest/b", "workflows": _workflows({})},
        {},
        {},
    ),
    "custom properties of the organization and its repositories": (
        {"custom_properties": [_CUSTOM_PROPERTY], "workflows": _workflows({})},
        {"custom_properties": [_CUSTOM_PROPERTY], "workflows": _workflows({})},
        {"custom_properties": {"tier": "gold"}},
        {"custom_properties": {"tier": "silver"}},
    ),
    "organization enables workflows for selected repositories": (
        {"workflows": _workflows({"enabled_repositories": "selected", "selected_repositories": ["web"]})},
        {"workflows": _workflows({"enabled_repositories": "selected", "selected_repositories": ["api"]})},
        {"workflows": _repository_workflows()},
        {"workflows": _repository_workflows(enabled=False)},
    ),
    "https of github pages without a custom domain": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {"gh_pages_cname": None, "gh_pages_https_enforced": True},
        {"gh_pages_cname": None, "gh_pages_https_enforced": False},
    ),
    "https of github pages with a custom domain": (
        {"workflows": _workflows({})},
        {"workflows": _workflows({})},
        {"gh_pages_cname": "docs.example.org", "gh_pages_https_enforced": True},
        {"gh_pages_cname": "docs.example.org", "gh_pages_https_enforced": False},
    ),
}


def _organization(settings: dict, repository: dict) -> GitHubOrganization:
    data = json.loads(_RESOURCE.read_text())
    data["project_name"] = "otterdog"
    data["github_id"] = "OtterdogTest"
    data["settings"].update({"plan": "free", "has_discussions": False, **settings})
    data["repositories"] = [
        {
            "name": "web",
            "description": "d",
            "private": False,
            "archived": False,
            "gh_pages_build_type": "legacy",
            "gh_pages_source_branch": "main",
            "gh_pages_source_path": "/docs",
            "workflows": _repository_workflows(),
            **repository,
        }
    ]
    return GitHubOrganization.from_model_data(data)


def _differences(expected: GitHubOrganization, current: GitHubOrganization) -> set[tuple[str, str]]:
    """The (type of object, setting) pairs that differ, also the ones of nested objects like the workflow settings."""
    context = LivePatchContext("OtterdogTest", "*", False, False, "*", current.settings, expected.settings)
    patches: list = []
    expected.generate_live_patch(current, context, patches.append)

    differences = set()
    for patch in patches:
        kind = type(patch.expected_object or patch.current_object).__name__
        for key, change in (patch.changes or {}).items():
            if isinstance(change.to_value, dict) and isinstance(change.from_value, dict):
                names = set(change.to_value) | set(change.from_value)
                differences.update(
                    (kind, f"{key}.{name}")
                    for name in names
                    if change.to_value.get(name) != change.from_value.get(name)
                )
            else:
                differences.add((kind, key))

    return differences


_SETTING_PATHS = [p for p in valid_paths() if p not in RESOURCES and p.count(".") >= 1 and not p.startswith("team.")]


def _scope(path: str) -> str:
    return "Repository" if path.startswith("repository.") else "OrganizationSettings"


@functools.cache
def _built_scenario(scenario: str):
    """The organizations of a scenario, parsing and validating them is expensive, and their differences."""
    expected_settings, current_settings, expected_repository, current_repository = _SCENARIOS[scenario]
    expected = _organization(expected_settings, expected_repository)
    current = _organization(current_settings, current_repository)
    return expected, current, _differences(copy.deepcopy(expected), copy.deepcopy(current))


def _comparison_problems(path: str) -> list[str]:
    """What unmanaging a path changes in the comparison of organizations, apart from the setting itself."""
    name = path.rsplit(".", 1)[1]

    def of_the_setting(kind: str, difference: str) -> bool:
        # a difference of the setting itself, or of a value nested in it like the key of a custom property
        return kind == _scope(path) and (
            difference == name or difference.startswith(f"{name}.") or difference.endswith(f".{name}")
        )

    problems = []
    for scenario in _SCENARIOS:
        built_expected, built_current, baseline = _built_scenario(scenario)
        expected, current = copy.deepcopy(built_expected), copy.deepcopy(built_current)

        for organization in (expected, current):
            drop_unmanaged(organization, [path])

        try:
            unmanaged = _differences(expected, current)
        except Exception as ex:
            problems.append(f"fails in '{scenario}': {ex!r}")
            continue

        added = sorted(d for d in unmanaged - baseline if not of_the_setting(*d))
        removed = sorted(d for d in baseline - unmanaged if not of_the_setting(*d))
        if added:
            problems.append(f"adds differences in '{scenario}': {added}")
        if removed:
            problems.append(f"removes differences in '{scenario}': {removed}")

    return problems


@pytest.mark.parametrize("path", _SETTING_PATHS)
def test_unmanaging_a_setting_only_affects_that_setting(path):
    assert _comparison_problems(path) == [], f"'{path}' cannot be unmanaged"


def _validation_errors(organization: GitHubOrganization, unmanaged: list[str]) -> set[str]:
    import asyncio

    jsonnet_config = SimpleNamespace(
        template_dir="",
        unmanaged=frozenset(unmanaged),
        default_org_config_for_org_id=lambda project, org_id: {
            "project_name": project,
            "github_id": org_id,
            "settings": {},
        },
    )
    secret_resolver = pretend.stub(is_supported_secret_provider=lambda _: False, get_secret=lambda value: value)
    context = asyncio.run(
        organization.validate(SimpleNamespace(exclude_teams_pattern=None), jsonnet_config, secret_resolver, None)
    )
    return {message for failure_type, message in context.validation_failures if failure_type == FailureType.ERROR}


def _valid_organization(**repository) -> GitHubOrganization:
    return _organization(
        {
            "has_discussions": True,
            "discussion_source_repository": "OtterdogTest/web",
            "immutable_releases_enforced_repositories": "none",
            "workflows": _workflows({"selected_repositories": [], "allow_action_patterns": []}),
        },
        {
            "gh_pages_cname": "docs.example.org",
            "gh_pages_https_enforced": True,
            "workflows": _repository_workflows(allow_action_patterns=[]),
            **repository,
        },
    )


@functools.cache
def _built_valid_organization() -> GitHubOrganization:
    return _valid_organization()


def _validation_problems(path: str) -> list[str]:
    baseline = _validation_errors(copy.deepcopy(_built_valid_organization()), [])
    assert baseline == set()

    try:
        errors = _validation_errors(copy.deepcopy(_built_valid_organization()), [path])
    except Exception as ex:
        return [f"makes the validation fail: {ex!r}"]

    return [f"adds the validation error '{error}'" for error in sorted(errors - baseline)]


@pytest.mark.parametrize("path", _SETTING_PATHS)
def test_unmanaging_a_setting_does_not_break_the_validation(path):
    assert _validation_problems(path) == [], f"'{path}' cannot be unmanaged"


# the dependencies that these properties cannot find: they are found by reading how the setting is used
_FOUND_BY_READING_THE_CODE = {
    # changing the enforcement of immutable releases to 'selected' without the selection clears the selection
    "organization.settings.immutable_releases_selected_repositories",
}


@pytest.mark.parametrize("path", sorted(DEPENDENCIES))
def test_a_dependency_is_one_because_unmanaging_it_affects_others(path):
    """Keeps the list minimal: a setting that can be unmanaged safely must not be rejected."""
    if path in _FOUND_BY_READING_THE_CODE:
        pytest.skip("not found by comparing organizations or validating them")

    assert _comparison_problems(path) + _validation_problems(path), f"'{path}' can be unmanaged"
