#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

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
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


_logger = get_logger(__name__)

_FEATURE_VALUES = ("enabled", "disabled", "not_set")
_PRODUCT_VALUES = ("enabled", "disabled")
_ENFORCEMENT_VALUES = ("enforced", "unenforced")
_DEFAULT_FOR_NEW_REPOS_VALUES = ("none", "all", "private_and_internal", "public")
_RUNNER_TYPE_VALUES = ("standard", "labeled", "not_set")

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


@dataclasses.dataclass
class OrganizationCodeSecurityConfiguration(ModelObject):
    """
    Represents a Code Security Configuration defined on organization level.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
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

    # Code Security and Secret Protection are licensed per active committer on private and internal repositories
    _cost_related_properties: ClassVar[list[str]] = ["code_security", "secret_protection"]

    @property
    def model_object_name(self) -> str:
        return "org_code_security_configuration"

    def is_default_for_new_repos(self) -> bool:
        return is_set_and_valid(self.default_for_new_repos) and self.default_for_new_repos != "none"

    def is_cost_related(self, cost_policy: CostPolicy) -> bool:
        """Enabling Code Security or Secret Protection can consume licenses."""
        return any(self.__getattribute__(prop) == "enabled" for prop in self._cost_related_properties)

    def changes_are_cost_related(self, changes: dict[str, Change]) -> bool:
        return any(prop in changes and changes[prop].to_value == "enabled" for prop in self._cost_related_properties)

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        header = self.get_model_header(parent_object)

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

        if self.code_scanning_default_setup_runner_type == "labeled":
            if not is_set_and_valid(self.code_scanning_default_setup_runner_label):
                context.add_failure(
                    FailureType.ERROR,
                    f"{header} has 'code_scanning_default_setup_runner_type' set to 'labeled', "
                    f"but no 'code_scanning_default_setup_runner_label' is specified.",
                )
        elif is_set_and_valid(self.code_scanning_default_setup_runner_label):
            context.add_failure(
                FailureType.WARNING,
                f"{header} has 'code_scanning_default_setup_runner_label' specified, "
                f"which is only taken into account if 'code_scanning_default_setup_runner_type' is set to 'labeled'.",
            )

        reviewers = self.secret_scanning_delegated_bypass_reviewers
        if is_set_and_present(reviewers):
            for reviewer in reviewers:
                match = _REVIEWER_PATTERN.match(reviewer)
                if match is None:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{header} has an invalid bypass reviewer '{reviewer}', "
                        f"only teams ('@<org>/<team-slug>') or roles ('#<role>') are supported.",
                    )
                    continue

                if (mode := match.group("mode")) is not None and mode not in _REVIEWER_MODES:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{header} has bypass reviewer '{reviewer}' with mode '{mode}', "
                        f"while only modes ({' | '.join(repr(x) for x in _REVIEWER_MODES)}) are allowed.",
                    )

                role = match.group(1)[1:]
                if match.group(1).startswith("#") and role not in _INVERTED_REVIEWER_ROLES and not role.isdigit():
                    context.add_failure(
                        FailureType.ERROR,
                        f"{header} has bypass reviewer '{reviewer}' with unknown role '{role}', "
                        f"only roles ({' | '.join(repr(x) for x in _INVERTED_REVIEWER_ROLES)}) "
                        f"or the id of a custom role are supported.",
                    )

            if self.secret_scanning_delegated_bypass == "enabled" and len(reviewers) == 0:
                context.add_failure(
                    FailureType.WARNING,
                    f"{header} has 'secret_scanning_delegated_bypass' enabled, "
                    f"but no 'secret_scanning_delegated_bypass_reviewers' are specified.",
                )

        if self.secret_scanning == "disabled":
            for key in self._secret_scanning_properties:
                if self.__getattribute__(key) == "enabled":
                    context.add_failure(
                        FailureType.WARNING,
                        f"{header} has '{key}' enabled while 'secret_scanning' is disabled, "
                        f"the setting will have no effect.",
                    )
        elif self.secret_scanning_push_protection == "disabled" and self.secret_scanning_delegated_bypass == "enabled":
            context.add_failure(
                FailureType.WARNING,
                f"{header} has 'secret_scanning_delegated_bypass' enabled while 'secret_scanning_push_protection' "
                f"is disabled, the setting will have no effect.",
            )

        if self.dependabot_alerts == "disabled" and self.dependabot_security_updates == "enabled":
            context.add_failure(
                FailureType.WARNING,
                f"{header} has 'dependabot_security_updates' enabled while 'dependabot_alerts' is disabled, "
                f"the setting will have no effect.",
            )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        # optional properties set to None are not managed
        if field.name in self._optional_properties and self.__getattribute__(field.name) is None:
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
                current_object = unwrap(patch.current_object)

                # do not leave the organization with a default configuration that is going to be deleted
                if current_object.is_default_for_new_repos():
                    await provider.update_org_code_security_configuration_default(
                        org_id,
                        current_object.id,
                        current_object.name,
                        "none",
                    )

                await provider.delete_org_code_security_configuration(
                    org_id,
                    current_object.id,
                    current_object.name,
                )

            case LivePatchType.CHANGE:
                expected_object = unwrap(patch.expected_object)
                current_object = unwrap(patch.current_object)
                changes = unwrap(patch.changes)

                if any(key != "default_for_new_repos" for key in changes):
                    await provider.update_org_code_security_configuration(
                        org_id,
                        current_object.id,
                        current_object.name,
                        await expected_object.to_provider_data(org_id, provider),
                    )

                if "default_for_new_repos" in changes:
                    await provider.update_org_code_security_configuration_default(
                        org_id,
                        current_object.id,
                        current_object.name,
                        expected_object.default_for_new_repos,
                    )
