#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import copy
import dataclasses
import re
from typing import TYPE_CHECKING, Any, ClassVar

from jsonbender import F, K, OptionalS  # type: ignore

from otterdog.models import (
    CostPolicy,
    FailureType,
    LivePatch,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.utils import UNSET, Change, get_logger, is_set_and_present, is_set_and_valid, unwrap

if TYPE_CHECKING:
    from collections.abc import Collection

    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


_logger = get_logger(__name__)

_FEATURE_VALUES = ("enabled", "disabled", "not_set")
_PRODUCT_VALUES = ("enabled", "disabled")
_ENFORCEMENT_VALUES = ("enforced", "unenforced")
_DEFAULT_FOR_NEW_REPOS_VALUES = ("none", "all", "private_and_internal", "public")
_RUNNER_TYPE_VALUES = ("standard", "labeled", "not_set")

# the visibilities of new repositories a configuration is the default for
_DEFAULT_VISIBILITIES = {
    "all": ["public", "private_and_internal"],
    "public": ["public"],
    "private_and_internal": ["private_and_internal"],
}

# GitHub reports the status of Code Security and Secret Protection combined in 'advanced_security'
_ADVANCED_SECURITY_TO_PRODUCTS = {
    "enabled": ("enabled", "enabled"),
    "disabled": ("disabled", "disabled"),
    "code_security": ("enabled", "disabled"),
    "secret_protection": ("disabled", "enabled"),
}

# the repository roles that can be selected as bypass reviewers, same as for the bypass actors of rulesets
_REVIEWER_ROLES = {"5": "RepositoryAdmin", "4": "Write", "2": "Maintain", "1": "OrganizationAdmin"}
_INVERTED_REVIEWER_ROLES = {v: k for k, v in _REVIEWER_ROLES.items()}
_REVIEWER_MODES = {"always": "ALWAYS", "exempt": "EXEMPT"}
_REVIEWER_PATTERN = re.compile(r"^(@[^/:\s]+/[^/:\s]+|#[\w-]+)(:(?P<mode>\w+))?$")


def _validate_reviewer(reviewer: str) -> str | None:
    """Returns the description of the problem of a bypass reviewer, if any."""
    match = _REVIEWER_PATTERN.match(reviewer)
    if match is None:
        return (
            f"an invalid bypass reviewer '{reviewer}', "
            f"only teams ('@<org>/<team-slug>') or roles ('#<role>') are supported."
        )

    mode = match.group("mode")
    if mode is not None and mode not in _REVIEWER_MODES:
        return (
            f"bypass reviewer '{reviewer}' with mode '{mode}', "
            f"while only modes ({' | '.join(repr(x) for x in _REVIEWER_MODES)}) are allowed."
        )

    actor = match.group(1)
    role = actor[1:]
    if actor.startswith("#") and role not in _INVERTED_REVIEWER_ROLES and not role.isdigit():
        return (
            f"bypass reviewer '{reviewer}' with unknown role '{role}', "
            f"only roles ({' | '.join(repr(x) for x in _INVERTED_REVIEWER_ROLES)}) "
            f"or the id of a custom role are supported."
        )

    return None


def _normalize_reviewers(reviewers: Any) -> Any:
    """
    Normalizes bypass reviewers to the representation they are read from GitHub with:
    the default mode 'always' is omitted and roles that have a name are referenced by it.
    """
    if not isinstance(reviewers, list):
        return reviewers

    def normalize(reviewer: Any) -> Any:
        match = _REVIEWER_PATTERN.match(reviewer) if isinstance(reviewer, str) else None
        if match is None or _validate_reviewer(reviewer) is not None:
            # invalid reviewers are kept as is to be reported by the validation
            return reviewer

        actor = match.group(1)
        if actor.startswith("#"):
            actor = f"#{_REVIEWER_ROLES.get(actor[1:], actor[1:])}"

        mode = match.group("mode")
        return f"{actor}:{mode}" if mode is not None and mode != "always" else actor

    return [normalize(reviewer) for reviewer in reviewers]


@dataclasses.dataclass
class OrganizationCodeSecurityConfiguration(ModelObject):
    """
    Represents a Code Security Configuration defined on organization level.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    # 'organization', 'global' for predefined configurations (e.g. GitHub recommended) or 'enterprise'
    target_type: str = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    description: str
    code_security: str
    secret_protection: str
    dependency_graph: str
    dependency_graph_autosubmit_action: str
    dependency_graph_autosubmit_action_labeled_runners: bool | None
    dependabot_alerts: str
    dependabot_security_updates: str
    dependabot_reachability: str | None
    dependabot_delegated_alert_dismissal: str | None
    code_scanning_default_setup: str
    code_scanning_default_setup_runner_type: str | None
    code_scanning_default_setup_runner_label: str | None
    code_scanning_allow_advanced: bool | None
    code_scanning_delegated_alert_dismissal: str | None
    secret_scanning: str
    secret_scanning_push_protection: str
    secret_scanning_delegated_bypass: str
    secret_scanning_delegated_bypass_reviewers: list[str] | None
    secret_scanning_validity_checks: str
    secret_scanning_non_provider_patterns: str
    secret_scanning_generic_secrets: str | None
    secret_scanning_generic_secrets_push_protection: str | None
    secret_scanning_delegated_alert_dismissal: str | None
    secret_scanning_extended_metadata: str | None
    private_vulnerability_reporting: str
    enforcement: str
    default_for_new_repos: str

    _feature_properties: ClassVar[list[str]] = [
        "dependency_graph",
        "dependency_graph_autosubmit_action",
        "dependabot_alerts",
        "dependabot_security_updates",
        "dependabot_reachability",
        "dependabot_delegated_alert_dismissal",
        "code_scanning_default_setup",
        "code_scanning_delegated_alert_dismissal",
        "secret_scanning",
        "secret_scanning_push_protection",
        "secret_scanning_delegated_bypass",
        "secret_scanning_validity_checks",
        "secret_scanning_non_provider_patterns",
        "secret_scanning_generic_secrets",
        "secret_scanning_generic_secrets_push_protection",
        "secret_scanning_delegated_alert_dismissal",
        "secret_scanning_extended_metadata",
        "private_vulnerability_reporting",
    ]

    # properties that are not managed if set to None, e.g. as they are not available to every organization
    _optional_properties: ClassVar[set[str]] = {
        "dependency_graph_autosubmit_action_labeled_runners",
        "dependabot_reachability",
        "dependabot_delegated_alert_dismissal",
        "code_scanning_default_setup_runner_type",
        "code_scanning_default_setup_runner_label",
        "code_scanning_allow_advanced",
        "code_scanning_delegated_alert_dismissal",
        "secret_scanning_delegated_bypass_reviewers",
        "secret_scanning_generic_secrets",
        "secret_scanning_generic_secrets_push_protection",
        "secret_scanning_delegated_alert_dismissal",
        "secret_scanning_extended_metadata",
    }

    # properties that only take effect if the secret scanning feature itself is not disabled
    _secret_scanning_properties: ClassVar[list[str]] = [
        "secret_scanning_push_protection",
        "secret_scanning_delegated_bypass",
        "secret_scanning_validity_checks",
        "secret_scanning_non_provider_patterns",
        "secret_scanning_generic_secrets",
        "secret_scanning_generic_secrets_push_protection",
        "secret_scanning_delegated_alert_dismissal",
        "secret_scanning_extended_metadata",
    ]

    # the settings of a repository that a feature sets once the configuration is attached to the repository
    _repository_properties: ClassVar[dict[str, list[str]]] = {
        "dependabot_alerts": ["dependabot_alerts_enabled"],
        "dependabot_security_updates": ["dependabot_security_updates_enabled"],
        "code_scanning_default_setup": [
            "code_scanning_default_setup_enabled",
            "code_scanning_default_query_suite",
            "code_scanning_default_languages",
        ],
        "secret_scanning": ["secret_scanning"],
        "secret_scanning_push_protection": ["secret_scanning_push_protection"],
        "private_vulnerability_reporting": ["private_vulnerability_reporting_enabled"],
    }

    # the settings of a repository that GitHub supports only on public repositories
    _public_repository_properties: ClassVar[set[str]] = {"private_vulnerability_reporting_enabled"}

    # Code Security and Secret Protection are licensed per active committer on private and internal repositories
    _cost_related_properties: ClassVar[list[str]] = ["code_security", "secret_protection"]

    @property
    def model_object_name(self) -> str:
        return "org_code_security_configuration"

    def is_organization_configuration(self) -> bool:
        """Configurations of the organization can be managed, as opposed to predefined or enterprise ones."""
        return not is_set_and_valid(self.target_type) or self.target_type == "organization"

    def is_default_for_new_repos(self) -> bool:
        return is_set_and_valid(self.default_for_new_repos) and self.default_for_new_repos != "none"

    def is_cost_related(self, cost_policy: CostPolicy) -> bool:
        """Enabling Code Security or Secret Protection can consume licenses."""
        return any(self.__getattribute__(prop) == "enabled" for prop in self._cost_related_properties)

    def changes_are_cost_related(self, changes: dict[str, Change]) -> bool:
        return any(prop in changes and changes[prop].to_value == "enabled" for prop in self._cost_related_properties)

    def get_default_visibilities(self) -> list[str]:
        """Returns the visibilities of new repositories this configuration is the default for."""
        return _DEFAULT_VISIBILITIES.get(self.default_for_new_repos, []) if self.is_default_for_new_repos() else []

    def overlaid_with(
        self, other: OrganizationCodeSecurityConfiguration, keys: Collection[str] | None = None
    ) -> OrganizationCodeSecurityConfiguration:
        """
        Returns a copy of this configuration with the values that the other configuration manages, restricted to
        the given keys if any, values that the other configuration does not manage, i.e. unset or None, are kept.
        """
        result = copy.copy(self)
        for field in other.model_fields():
            value = other.__getattribute__(field.name)
            if is_set_and_valid(value) and (keys is None or field.name in keys):
                setattr(result, field.name, value)

        return result

    def get_repository_settings(self, private: bool = False) -> dict[str, Any]:
        """
        Returns the values of the main settings of a repository that this configuration sets once attached to it,
        e.g. 'dependabot_alerts_enabled', the settings of features set to 'not_set' are left to the repository.
        A private repository does not get the settings that GitHub supports only on public repositories,
        e.g. 'private_vulnerability_reporting_enabled'.
        """
        settings: dict[str, Any] = {}
        for feature, keys in self._repository_properties.items():
            status = self.__getattribute__(feature)
            # the first setting is the main one, e.g. 'code_scanning_default_setup_enabled'
            key = keys[0]
            if status in ("enabled", "disabled") and not (private and key in self._public_repository_properties):
                settings[key] = status == "enabled" if key.endswith("_enabled") else status

        return settings

    def get_controlled_repository_properties(self) -> set[str]:
        """
        Returns the settings of a repository that this configuration sets once attached to it,
        the settings of features set to 'not_set' are left to the repository.
        """
        return {
            key
            for feature, keys in self._repository_properties.items()
            if self.__getattribute__(feature) in ("enabled", "disabled")
            for key in keys
        }

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        header = self.get_model_header(parent_object)

        self._validate_values(context, header)
        self._validate_code_scanning_runner(context, header)
        self._validate_bypass_reviewers(context, header)
        self._validate_ineffective_settings(context, header)

    def _validate_values(self, context: ValidationContext, header: str) -> None:
        def validate_value(key: str, allowed_values: tuple[str, ...]) -> None:
            value = self.__getattribute__(key)
            if is_set_and_valid(value) and value not in allowed_values:
                context.add_failure(
                    FailureType.ERROR,
                    f"{header} has '{key}' of value '{value}', "
                    f"while only values ({' | '.join(repr(x) for x in allowed_values)}) are allowed.",
                )

        if is_set_and_valid(self.description) and len(self.description) > 255:
            context.add_failure(
                FailureType.ERROR,
                f"{header} has a 'description' of {len(self.description)} characters, "
                f"while at most 255 characters are allowed.",
            )

        for key in self._cost_related_properties:
            validate_value(key, _PRODUCT_VALUES)

        for key in self._feature_properties:
            validate_value(key, _FEATURE_VALUES)

        validate_value("enforcement", _ENFORCEMENT_VALUES)
        validate_value("default_for_new_repos", _DEFAULT_FOR_NEW_REPOS_VALUES)
        validate_value("code_scanning_default_setup_runner_type", _RUNNER_TYPE_VALUES)

    def _validate_code_scanning_runner(self, context: ValidationContext, header: str) -> None:
        has_runner_label = is_set_and_valid(self.code_scanning_default_setup_runner_label)

        if self.code_scanning_default_setup_runner_type == "labeled" and not has_runner_label:
            context.add_failure(
                FailureType.ERROR,
                f"{header} has 'code_scanning_default_setup_runner_type' set to 'labeled', "
                f"but no 'code_scanning_default_setup_runner_label' is specified.",
            )
        elif self.code_scanning_default_setup_runner_type != "labeled" and has_runner_label:
            context.add_failure(
                FailureType.WARNING,
                f"{header} has 'code_scanning_default_setup_runner_label' specified, "
                f"which is only taken into account if 'code_scanning_default_setup_runner_type' is set to 'labeled'.",
            )

    def _validate_bypass_reviewers(self, context: ValidationContext, header: str) -> None:
        reviewers = self.secret_scanning_delegated_bypass_reviewers
        if not is_set_and_present(reviewers):
            return

        for reviewer in reviewers:
            error = _validate_reviewer(reviewer)
            if error is not None:
                context.add_failure(FailureType.ERROR, f"{header} has {error}")

        if self.secret_scanning_delegated_bypass == "enabled" and len(reviewers) == 0:
            context.add_failure(
                FailureType.WARNING,
                f"{header} has 'secret_scanning_delegated_bypass' enabled, "
                f"but no 'secret_scanning_delegated_bypass_reviewers' are specified.",
            )

    def _validate_ineffective_settings(self, context: ValidationContext, header: str) -> None:
        def warn(key: str, required_key: str) -> None:
            context.add_failure(
                FailureType.WARNING,
                f"{header} has '{key}' enabled while '{required_key}' is disabled, the setting will have no effect.",
            )

        if self.secret_scanning == "disabled":
            for key in self._secret_scanning_properties:
                if self.__getattribute__(key) == "enabled":
                    warn(key, "secret_scanning")
        elif self.secret_scanning_push_protection == "disabled" and self.secret_scanning_delegated_bypass == "enabled":
            warn("secret_scanning_delegated_bypass", "secret_scanning_push_protection")

        if self.dependabot_alerts == "disabled" and self.dependabot_security_updates == "enabled":
            warn("dependabot_security_updates", "dependabot_alerts")

    @classmethod
    def get_mapping_from_model(cls) -> dict[str, Any]:
        mapping = super().get_mapping_from_model()

        # reviewers are compared in the representation they are read from GitHub with
        mapping["secret_scanning_delegated_bypass_reviewers"] = OptionalS(
            "secret_scanning_delegated_bypass_reviewers", default=UNSET
        ) >> F(_normalize_reviewers)

        return mapping

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        # optional properties set to None are not managed
        if field.name in self._optional_properties and self.__getattribute__(field.name) is None:
            return False

        # the runner label is only sent for labeled runners
        if (
            field.name == "code_scanning_default_setup_runner_label"
            and self.code_scanning_default_setup_runner_type != "labeled"
        ):
            return False

        return True

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        code_security, secret_protection = _ADVANCED_SECURITY_TO_PRODUCTS.get(
            data.get("advanced_security", ""), (UNSET, UNSET)
        )

        def option(options_key: str, key: str) -> Any:
            # options that are not reported are not configured
            options = data.get(options_key)
            return options.get(key) if isinstance(options, dict) else None

        mapping.update(
            {
                "description": OptionalS("description", default="") >> F(lambda x: x if x is not None else ""),
                "code_security": OptionalS("code_security", default=code_security),
                "secret_protection": OptionalS("secret_protection", default=secret_protection),
                "dependency_graph_autosubmit_action_labeled_runners": K(
                    option("dependency_graph_autosubmit_action_options", "labeled_runners")
                ),
                "code_scanning_default_setup_runner_type": K(
                    option("code_scanning_default_setup_options", "runner_type")
                ),
                "code_scanning_default_setup_runner_label": K(
                    option("code_scanning_default_setup_options", "runner_label")
                ),
                "code_scanning_allow_advanced": K(option("code_scanning_options", "allow_advanced")),
                "secret_scanning_delegated_bypass_reviewers": K(
                    cls._reviewers_from_provider(data.get("secret_scanning_delegated_bypass_options"))
                ),
                "default_for_new_repos": OptionalS("default_for_new_repos", default=UNSET),
            }
        )

        return mapping

    @staticmethod
    def _reviewers_from_provider(options: Any) -> list[str]:
        reviewers = options.get("reviewers") if isinstance(options, dict) else None

        result = []
        for reviewer in reviewers or []:
            reviewer_type = reviewer.get("reviewer_type")
            reviewer_id = str(reviewer.get("reviewer_id"))

            if reviewer_type == "TEAM":
                team_slug = reviewer.get("team_slug")
                if team_slug is None:
                    _logger.warning("fail to map bypass reviewer team '%s', skipping", reviewer_id)
                    continue
                transformed_reviewer = f"@{team_slug}"
            elif reviewer_type == "ROLE":
                transformed_reviewer = f"#{_REVIEWER_ROLES.get(reviewer_id, reviewer_id)}"
            else:
                continue

            if reviewer.get("mode", "ALWAYS") == "EXEMPT":
                transformed_reviewer = f"{transformed_reviewer}:exempt"

            result.append(transformed_reviewer)

        return result

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        # optional properties set to None are not managed and thus not sent
        mapping: dict[str, Any] = {
            field.name: K(data[field.name]) for field in cls.provider_fields() if is_set_and_valid(data.get(field.name))
        }

        def pop_mapping(keys: list[str]) -> None:
            for key in keys:
                mapping.pop(key, None)

        # the default for new repositories is set with a separate request
        pop_mapping(["default_for_new_repos"])

        # 'advanced_security' is only set if it does not need a deprecated value, otherwise
        # the individual product settings are used
        products = (data.get("code_security"), data.get("secret_protection"))
        if products in (("enabled", "enabled"), ("disabled", "disabled")):
            mapping["advanced_security"] = K(products[0])

        labeled_runners = data.get("dependency_graph_autosubmit_action_labeled_runners")
        pop_mapping(["dependency_graph_autosubmit_action_labeled_runners"])
        if labeled_runners is not None:
            mapping["dependency_graph_autosubmit_action_options"] = {"labeled_runners": K(labeled_runners)}

        allow_advanced = data.get("code_scanning_allow_advanced")
        pop_mapping(["code_scanning_allow_advanced"])
        if allow_advanced is not None:
            mapping["code_scanning_options"] = {"allow_advanced": K(allow_advanced)}

        runner_type = data.get("code_scanning_default_setup_runner_type")
        runner_label = data.get("code_scanning_default_setup_runner_label")
        pop_mapping(["code_scanning_default_setup_runner_type", "code_scanning_default_setup_runner_label"])
        if runner_type is not None:
            default_setup_options = {"runner_type": K(runner_type)}
            if runner_type == "labeled":
                default_setup_options["runner_label"] = K(runner_label)
            mapping["code_scanning_default_setup_options"] = default_setup_options

        reviewers = data.get("secret_scanning_delegated_bypass_reviewers")
        pop_mapping(["secret_scanning_delegated_bypass_reviewers"])
        if reviewers is not None:
            mapping["secret_scanning_delegated_bypass_options"] = {
                "reviewers": K(await cls._reviewers_to_provider(reviewers, provider))
            }

        return mapping

    @staticmethod
    async def _reviewers_to_provider(reviewers: list[str], provider: GitHubProvider) -> list[dict[str, Any]]:
        result = []
        for reviewer in reviewers:
            if ":" in reviewer:
                actor, mode = re.split(":", reviewer, maxsplit=1)
            else:
                actor, mode = reviewer, "always"

            if actor.startswith("#"):
                role = actor[1:]
                reviewer_type = "ROLE"
                reviewer_id = int(_INVERTED_REVIEWER_ROLES.get(role, role))
            else:
                reviewer_type = "TEAM"
                reviewer_id = (await provider.rest_api.team.get_team_ids(actor[1:]))[0]

            result.append({"reviewer_id": reviewer_id, "reviewer_type": reviewer_type, "mode": _REVIEWER_MODES[mode]})

        return result

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_code_security_configuration}"

    @classmethod
    async def _update_configuration(
        cls,
        org_id: str,
        expected_object: OrganizationCodeSecurityConfiguration,
        current_object: OrganizationCodeSecurityConfiguration,
        provider: GitHubProvider,
    ) -> None:
        """
        Updates the configuration and waits until the update is applied to its repositories, as their patches
        might change settings that depend on the updated ones. The patches of the repositories the update is not
        applied to, e.g. as it failed or is still pending, are skipped.
        """
        name = current_object.name

        try:
            failed_repositories = await provider.get_org_code_security_configuration_repositories(
                org_id, current_object.id, name, status="failed"
            )

            await provider.update_org_code_security_configuration(
                org_id, current_object.id, name, await expected_object.to_provider_data(org_id, provider)
            )

            incomplete_repositories = await provider.wait_for_org_code_security_configuration_repositories(
                org_id, current_object.id, name, failed_repositories
            )
        except RuntimeError:
            await cls._skip_patches_of_attached_repositories(
                org_id, current_object, provider, f"the update of code security configuration '{name}' failed"
            )
            raise

        if len(incomplete_repositories) > 0:
            provider.skip_repository_patches(
                org_id,
                incomplete_repositories,
                f"the update of code security configuration '{name}' is not applied to the repository",
            )
            raise RuntimeError(
                f"the update of code security configuration '{name}' is not applied to repositories "
                f"{', '.join(sorted(incomplete_repositories))}, their patches are skipped"
            )

    @classmethod
    async def _delete_configuration(
        cls, org_id: str, current_object: OrganizationCodeSecurityConfiguration, provider: GitHubProvider
    ) -> None:
        name = current_object.name

        try:
            # do not leave the organization with a default configuration that is going to be deleted
            if current_object.is_default_for_new_repos():
                await provider.update_org_code_security_configuration_default(org_id, current_object.id, name, "none")

            await provider.delete_org_code_security_configuration(org_id, current_object.id, name)
        except RuntimeError:
            await cls._skip_patches_of_attached_repositories(
                org_id, current_object, provider, f"the deletion of code security configuration '{name}' failed"
            )
            raise

    @staticmethod
    async def _skip_patches_of_attached_repositories(
        org_id: str, configuration: OrganizationCodeSecurityConfiguration, provider: GitHubProvider, reason: str
    ) -> None:
        """
        Skips the patches of the repositories attached to a configuration whose patch failed, as they were planned
        with the configuration as it is once its patch is applied, and might change settings it still sets. If these
        repositories can not be retrieved, the patches of all repositories are skipped, as any might be attached.
        """
        try:
            repo_names = await provider.get_org_code_security_configuration_repositories(
                org_id, configuration.id, configuration.name
            )
        except RuntimeError as ex:
            _logger.warning(
                "failed to retrieve the repositories of code security configuration '%s', skipping the patches "
                "of all repositories: %s",
                configuration.name,
                ex,
            )
            provider.skip_all_repository_patches(
                org_id, f"{reason}, and the repositories attached to it could not be retrieved"
            )
            return

        provider.skip_repository_patches(org_id, repo_names, reason)

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[OrganizationCodeSecurityConfiguration],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                expected_object = unwrap(patch.expected_object)
                configuration_id = await provider.add_org_code_security_configuration(
                    org_id,
                    await expected_object.to_provider_data(org_id, provider),
                )

                if expected_object.is_default_for_new_repos():
                    await provider.update_org_code_security_configuration_default(
                        org_id,
                        configuration_id,
                        expected_object.name,
                        expected_object.default_for_new_repos,
                    )

            case LivePatchType.REMOVE:
                await cls._delete_configuration(org_id, unwrap(patch.current_object), provider)

            case LivePatchType.CHANGE:
                expected_object = unwrap(patch.expected_object)
                current_object = unwrap(patch.current_object)
                changes = unwrap(patch.changes)

                if any(key != "default_for_new_repos" for key in changes):
                    await cls._update_configuration(org_id, expected_object, current_object, provider)

                if "default_for_new_repos" in changes:
                    await provider.update_org_code_security_configuration_default(
                        org_id,
                        current_object.id,
                        current_object.name,
                        expected_object.default_for_new_repos,
                    )


@dataclasses.dataclass
class CodeSecurityConfigurationPlan:
    """
    The code security configurations of an organization as they are once its patches are applied,
    to plan the settings of its repositories that the configurations attached to them set.
    """

    # the configurations of the organization by name, that repositories can reference
    managed_configurations: dict[str, OrganizationCodeSecurityConfiguration] = dataclasses.field(default_factory=dict)
    # the configuration currently attached to each repository
    current_attached_configurations: dict[str, OrganizationCodeSecurityConfiguration] = dataclasses.field(
        default_factory=dict
    )
    # the configuration attached to each repository once the patches are applied, if the repository does not
    # specify one, None if the configuration is deleted
    planned_attached_configurations: dict[str, OrganizationCodeSecurityConfiguration | None] = dataclasses.field(
        default_factory=dict
    )
    # the default configuration for new repositories by visibility
    default_configurations: dict[str, OrganizationCodeSecurityConfiguration] = dataclasses.field(default_factory=dict)
    # whether the settings that the attached configuration stops setting are updated, as their current values
    # are not known, e.g. if the current organization is loaded from a file
    update_released_settings: bool = False

    def get_default_configuration(self, private: bool) -> OrganizationCodeSecurityConfiguration | None:
        return self.default_configurations.get("private_and_internal" if private else "public")

    # repositories are keyed by their name in lower case, as the names of repositories are case-insensitive on GitHub

    def get_current_attached_configuration(self, repo_name: str) -> OrganizationCodeSecurityConfiguration | None:
        return self.current_attached_configurations.get(repo_name.lower())

    def get_planned_attached_configuration(self, repo_name: str) -> OrganizationCodeSecurityConfiguration | None:
        return self.planned_attached_configurations.get(repo_name.lower())
