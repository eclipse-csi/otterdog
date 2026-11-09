#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Parts of the default configuration that are not managed by otterdog for an organization.

The default configuration decides what otterdog reads from GitHub and compares: a setting is only retrieved if its
key is present in it, and a resource, e.g. the secrets of repositories, is only managed if the template defines
the function that creates it. An organization that cannot use a feature, e.g. because of its plan, lists the
paths of the settings and resources it does not use in the 'unmanaged' list of the otterdog configuration:

* ``organization.settings.<setting>`` and ``organization.settings.workflows.<setting>``
* ``repository.<setting>`` and ``repository.workflows.<setting>``
* ``team.<setting>``
* ``organization.<resources>``, ``repository.<resources>`` and ``team.team_sync``, e.g. ``repository.codespaces_secrets``
"""

from __future__ import annotations

import dataclasses
import difflib
from typing import TYPE_CHECKING, Any

from otterdog.utils import UNSET, is_set_and_present

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from otterdog.models.github_organization import GitHubOrganization

# resources: the path, and the functions of the template that provide the default configuration of the resource
# and of the resources nested in it. A resource without default configuration is neither read nor compared.
RESOURCES: dict[str, tuple[str, ...]] = {
    "organization.roles": ("default_org_role_config",),
    "organization.teams": ("default_team_config", "default_team_sync_config"),
    "organization.webhooks": ("default_org_webhook_config",),
    "organization.secrets": ("default_org_secret_config",),
    "organization.dependabot_secrets": ("default_org_dependabot_secret_config",),
    "organization.codespaces_secrets": ("default_org_codespaces_secret_config",),
    "organization.variables": ("default_org_variable_config",),
    "organization.rulesets": ("default_org_ruleset_config",),
    "organization.code_security_configurations": ("default_org_code_security_configuration_config",),
    "repository.webhooks": ("default_repo_webhook_config",),
    "repository.secrets": ("default_repo_secret_config",),
    "repository.dependabot_secrets": ("default_repo_dependabot_secret_config",),
    "repository.codespaces_secrets": ("default_repo_codespaces_secret_config",),
    "repository.variables": ("default_repo_variable_config",),
    "repository.branch_protection_rules": ("default_branch_protection_rule_config",),
    "repository.rulesets": ("default_repo_ruleset_config",),
    "repository.environments": (
        "default_environment_config",
        "default_environment_secret_config",
        "default_environment_variable_config",
    ),
    "team.team_sync": ("default_team_sync_config",),
}

# settings that cannot be unmanaged as other parts of the configuration depend on their value
DEPENDENCIES: dict[str, str] = {
    "organization.settings.custom_properties": "repositories are checked against the custom properties of the organization",
    "organization.settings.workflows.selected_repositories": "the workflow settings of repositories depend on it",
    "organization.settings.has_discussions": "the discussion source repository depends on it",
    # decides how a repository is created, an unmanaged value would not be sent: GitHub creates a public repository
    "repository.private": "it decides how a repository is created and which of its settings are compared",
    "repository.archived": "the settings of an archived repository are not compared, GitHub rejects their changes",
    "repository.gh_pages_build_type": "the other GitHub Pages settings depend on it",
    "repository.code_scanning_default_setup_enabled": "the other code scanning settings depend on it",
    "repository.gh_pages_cname": "whether the HTTPS enforcement of GitHub Pages can be changed depends on it",
    "repository.workflows.enabled": "the other workflow settings of a repository are only compared if they are enabled",
    "repository.workflows.allowed_actions": "the selected actions of a repository are only compared if it is 'selected'",
    "organization.settings.discussion_source_repository": "the repository of the discussions depends on it",
    # the workflow settings of the organization restrict the ones of its repositories, which are compared with them
    "organization.settings.workflows.enabled_repositories": "the workflow settings of repositories depend on it",
    "organization.settings.workflows.allowed_actions": "the workflow settings of repositories depend on it",
    "organization.settings.workflows.default_workflow_permissions": "the workflow settings of repositories depend on it",
    "organization.settings.workflows.actions_can_approve_pull_request_reviews": (
        "the workflow settings of repositories depend on it"
    ),
    # changing the enforcement to 'selected' without the selection would clear the selection
    "organization.settings.immutable_releases_enforced_repositories": "the selected repositories depend on it",
    "organization.settings.immutable_releases_selected_repositories": "changing the enforcement would clear the selection",
}

_ORGANIZATION_SETTINGS = "organization.settings"
_REPOSITORY = "repository"
_TEAM = "team"


def _setting_scopes() -> dict[str, type]:
    # imported here, the models depend on the configuration
    from otterdog.models.organization_settings import OrganizationSettings
    from otterdog.models.organization_workflow_settings import OrganizationWorkflowSettings
    from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
    from otterdog.models.repository import Repository
    from otterdog.models.team import Team

    return {
        _ORGANIZATION_SETTINGS: OrganizationSettings,
        f"{_ORGANIZATION_SETTINGS}.workflows": OrganizationWorkflowSettings,
        _REPOSITORY: Repository,
        f"{_REPOSITORY}.workflows": RepositoryWorkflowSettings,
        _TEAM: Team,
    }


def _setting_names(model_class: type, scope: str) -> list[str]:
    """The settings of a model class, i.e. its fields that are neither resources nor key of the model."""
    resources = {path.removeprefix(f"{scope}.") for path in RESOURCES if path.startswith(f"{scope}.")}
    # nested models are listed with their own scope
    nested = {"workflows"}

    names = []
    for field in dataclasses.fields(model_class):
        if field.name.startswith("_") or field.name in resources or field.name in nested:
            continue
        # not part of the configuration of the template
        if any(field.metadata.get(flag, False) is True for flag in ("key", "model_only", "read_only", "external_only")):
            continue
        names.append(field.name)

    return names


def valid_paths() -> list[str]:
    """All valid paths of the 'unmanaged' list."""
    paths = list(RESOURCES)
    for scope, model_class in _setting_scopes().items():
        paths.extend(f"{scope}.{name}" for name in _setting_names(model_class, scope))

    return sorted(path for path in paths if path not in DEPENDENCIES)


def validate_paths(paths: Iterable[Any], source: str) -> frozenset[str]:
    """Validates the paths of an 'unmanaged' list, raises a RuntimeError describing the invalid ones."""
    valid = valid_paths()
    errors = []

    result = set()
    for path in paths:
        if not isinstance(path, str):
            errors.append(f"'{path}' is not a string")
        elif path in DEPENDENCIES:
            errors.append(f"'{path}' cannot be unmanaged, {DEPENDENCIES[path]}")
        elif path not in valid:
            suggestions = difflib.get_close_matches(path, valid, n=3, cutoff=0.6)
            hint = f", did you mean {' or '.join(repr(s) for s in suggestions)}?" if suggestions else ""
            errors.append(f"'{path}' is not a setting or resource that can be unmanaged{hint}")
        else:
            result.add(path)

    if errors:
        raise RuntimeError(
            f"invalid 'unmanaged' of {source}: {'; '.join(errors)}. "
            f"Valid paths are the settings 'organization.settings.<setting>', 'organization.settings.workflows.<setting>', "
            f"'repository.<setting>', 'repository.workflows.<setting>' and 'team.<setting>', and the resources "
            f"{', '.join(RESOURCES)}."
        )

    return frozenset(result)


def parse_lists(sources: Iterable[tuple[str, Any]]) -> tuple[frozenset[str], str | None]:
    """
    Combines the lists of paths of the given sources, e.g. the otterdog configuration and the organization.

    Returns the paths, or the description of the invalid ones, so that an invalid list can be reported when the
    organization is used, instead of failing the loading of the configuration of all organizations.
    """
    paths: set[str] = set()
    errors = []
    for source, value in sources:
        if value is None:
            continue

        if not isinstance(value, list):
            errors.append(f"invalid 'unmanaged' of {source}: it must be a list of paths, not '{value}'")
            continue

        try:
            paths.update(validate_paths(value, source))
        except RuntimeError as ex:
            errors.append(str(ex))

    if errors:
        return frozenset(), "\n".join(errors)

    return frozenset(paths), None


def unavailable_default_configs(unmanaged: Collection[str]) -> set[str]:
    """The names of the default configurations of the unmanaged resources, which are not available."""
    return {name for path in unmanaged for name in RESOURCES.get(path, ())}


def remove_unmanaged_settings(config: dict[str, Any] | None, unmanaged: Collection[str], scope: str) -> None:
    """Removes the unmanaged settings of the given scope from a default configuration, in place."""
    if config is None:
        return

    prefix = f"{scope}."
    for path in unmanaged:
        if path in RESOURCES or not path.startswith(prefix):
            continue

        name = path.removeprefix(prefix)
        nested, _, key = name.partition(".")
        if key:
            nested_config = config.get(nested)
            if isinstance(nested_config, dict):
                nested_config.pop(key, None)
        else:
            config.pop(name, None)


def remove_unmanaged_settings_of_org_config(config: dict[str, Any], unmanaged: Collection[str]) -> None:
    """Removes the unmanaged settings of the organization from its default configuration, in place."""
    settings = config.get("settings")
    if isinstance(settings, dict):
        remove_unmanaged_settings(settings, unmanaged, _ORGANIZATION_SETTINGS)


def remove_unmanaged_settings_of_repo_config(config: dict[str, Any] | None, unmanaged: Collection[str]) -> None:
    remove_unmanaged_settings(config, unmanaged, _REPOSITORY)


def remove_unmanaged_settings_of_team_config(config: dict[str, Any] | None, unmanaged: Collection[str]) -> None:
    remove_unmanaged_settings(config, unmanaged, _TEAM)


def _unset(model_object: Any, scope: str, unmanaged: Collection[str]) -> None:
    prefix = f"{scope}."
    for path in unmanaged:
        if path in RESOURCES or not path.startswith(prefix):
            continue

        name = path.removeprefix(prefix)
        if "." in name:
            nested_name, _, key = name.partition(".")
            nested_object = getattr(model_object, nested_name, UNSET)
            if nested_object is not UNSET and hasattr(nested_object, key):
                setattr(nested_object, key, UNSET)
        elif hasattr(model_object, name):
            setattr(model_object, name, UNSET)


def unset_unmanaged_settings(organization: GitHubOrganization, unmanaged: Collection[str]) -> None:
    """
    Unsets the unmanaged settings of an organization, as not all of them are retrieved based on the default
    configuration, e.g. the settings of a repository. A setting that is unset is neither compared nor imported.
    """
    if not unmanaged:
        return

    _unset(organization.settings, _ORGANIZATION_SETTINGS, unmanaged)

    for repository in organization.repositories:
        _unset(repository, _REPOSITORY, unmanaged)

    for team in organization.teams:
        _unset(team, _TEAM, unmanaged)


def _objects_of(organization: GitHubOrganization, scope: str) -> list[Any]:
    if scope == "organization":
        return [organization]
    if scope == _REPOSITORY:
        return list(organization.repositories)
    return list(organization.teams)


def clear_unmanaged_resources(organization: GitHubOrganization, unmanaged: Collection[str]) -> None:
    """
    Removes the unmanaged resources of an organization, e.g. the ones of a configuration loaded from a file:
    a resource that is not removed would be compared with a state that does not contain it.
    """
    for path in sorted(p for p in unmanaged if p in RESOURCES):
        scope, _, name = path.partition(".")
        for model_object in _objects_of(organization, scope):
            if isinstance(getattr(model_object, name, None), list):
                setattr(model_object, name, [])


def drop_unmanaged(organization: GitHubOrganization, unmanaged: Collection[str]) -> None:
    """Removes everything that is unmanaged from an organization, it is then neither compared nor imported."""
    unset_unmanaged_settings(organization, unmanaged)
    clear_unmanaged_resources(organization, unmanaged)


def unmanaged_repository_settings(unmanaged: Collection[str]) -> frozenset[str]:
    """The names of the unmanaged settings of repositories, some of them are retrieved with dedicated requests."""
    prefix = f"{_REPOSITORY}."
    return frozenset(
        path.removeprefix(prefix)
        for path in unmanaged
        if path.startswith(prefix) and path not in RESOURCES and "." not in path.removeprefix(prefix)
    )


def declared_unmanaged_settings(organization: GitHubOrganization, unmanaged: Collection[str]) -> dict[str, int]:
    """
    The number of declarations of settings that are unmanaged, but change how others are handled: the members of a
    team connected to an external group are provisioned by the identity provider and not compared.
    """
    declared: dict[str, int] = {}

    if "team.external_group_id" in unmanaged:
        count = sum(1 for team in organization.teams if is_set_and_present(team.external_group_id))
        if count > 0:
            declared["team.external_group_id"] = count

    return declared


def declared_unmanaged_resources(organization: GitHubOrganization, unmanaged: Collection[str]) -> dict[str, int]:
    """The number of resources that the configuration of the organization declares although they are unmanaged."""
    declared: dict[str, int] = {}

    for path in sorted(p for p in unmanaged if p in RESOURCES):
        scope, _, name = path.partition(".")
        objects = _objects_of(organization, scope)

        count = sum(len(items) for items in (getattr(o, name, None) for o in objects) if isinstance(items, list))
        if count > 0:
            declared[path] = count

    return declared
