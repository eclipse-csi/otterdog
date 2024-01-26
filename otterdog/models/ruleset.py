#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
import re
from typing import Any, ClassVar, Optional, TypeVar, cast

from jsonbender import K, OptionalS, S, bend  # type: ignore

from otterdog.models import FailureType, ModelObject, ValidationContext
from otterdog.providers.github import GitHubProvider
from otterdog.utils import (
    UNSET,
    associate_by_key,
    is_set_and_valid,
    is_unset,
    print_warn,
)

RS = TypeVar("RS", bound="Ruleset")


@dataclasses.dataclass
class Ruleset(ModelObject, abc.ABC):
    """
    Represents a Ruleset.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    node_id: str = dataclasses.field(metadata={"external_only": True})
    enforcement: str

    bypass_actors: list[str]

    include_refs: list[str]
    exclude_refs: list[str]

    allows_creations: bool
    allows_deletions: bool
    allows_updates: bool
    allows_force_pushes: bool

    requires_commit_signatures: bool
    requires_linear_history: bool

    requires_pull_request: bool
    # the following settings are only taken into account
    # when requires_pull_request is True
    required_approving_review_count: Optional[int]
    dismisses_stale_reviews: bool
    requires_code_owner_review: bool
    requires_last_push_approval: bool
    requires_review_thread_resolution: bool

    requires_status_checks: bool
    requires_strict_status_checks: bool
    required_status_checks: list[str]

    requires_deployments: bool
    required_deployment_environments: list[str]

    _roles: ClassVar[dict[str, str]] = {"5": "RepositoryAdmin", "4": "Write", "2": "Maintain", "1": "OrganizationAdmin"}
    _inverted_roles: ClassVar[dict[str, str]] = dict((v, k) for k, v in _roles.items())

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        from .github_organization import GitHubOrganization

        org_settings = cast(GitHubOrganization, context.root_object).settings

        free_plan = org_settings.plan == "free"

        if is_set_and_valid(self.enforcement):
            if self.enforcement not in {"active", "disabled", "evaluate"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'enforcement' of value "
                    f"'{self.enforcement}', "
                    f"only values ('active' | 'disabled' | 'evaluate') are allowed.",
                )

            if free_plan is True and self.enforcement == "evaluate":
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'enforcement' of value "
                    f"'{self.enforcement}' which is not available for a 'free' plan.",
                )

        def valid_condition_pattern(pattern: str) -> bool:
            return pattern.startswith("refs/heads/") or ref == "~DEFAULT_BRANCH" or ref == "~ALL"

        if is_set_and_valid(self.include_refs):
            for ref in self.include_refs:
                if not valid_condition_pattern(ref):
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has an invalid 'include_refs' pattern "
                        f"'{ref}', only values ('refs/heads/*', '~DEFAULT_BRANCH', '~ALL') are allowed",
                    )

        if is_set_and_valid(self.exclude_refs):
            for ref in self.exclude_refs:
                if not valid_condition_pattern(ref):
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has an invalid 'exclude_refs' pattern "
                        f"'{ref}', only values ('refs/heads/*', '~DEFAULT_BRANCH', '~ALL') are allowed",
                    )

        if self.requires_pull_request is False:
            if is_set_and_valid(self.required_approving_review_count):
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has"
                    f" 'requires_pull_request' disabled but 'required_approving_review_count' "
                    f"is set to '{self.required_approving_review_count}', setting will be ignored.",
                )

            for key in {
                "dismisses_stale_reviews",
                "requires_code_owner_review",
                "requires_last_push_approval",
                "requires_review_thread_resolution",
            }:
                if self.__getattribute__(key) is True:
                    context.add_failure(
                        FailureType.INFO,
                        f"{self.get_model_header(parent_object)} has"
                        f" 'requires_pull_request' disabled but '{key}' "
                        f"is enabled, setting will be ignored.",
                    )

        # required_approving_review_count must be defined when requires_pull_request is enabled
        required_approving_review_count = self.required_approving_review_count
        if self.requires_pull_request is True and not is_unset(required_approving_review_count):
            if required_approving_review_count is None or required_approving_review_count < 0:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has"
                    f" 'requires_pull_request' enabled but 'required_approving_review_count' "
                    f"is not set (must be set to a non negative number).",
                )

        # if 'requires_status_checks' is disabled, issue a warning if required_status_checks is non-empty.
        required_status_checks = self.required_status_checks
        if (
            self.requires_status_checks is False
            and is_set_and_valid(required_status_checks)
            and len(required_status_checks) > 0
        ):
            context.add_failure(
                FailureType.INFO,
                f"{self.get_model_header(parent_object)} has"
                f" 'requires_status_checks' disabled but "
                f"'required_status_checks' is set to '{self.required_status_checks}', "
                f"setting will be ignored.",
            )

        # if 'requires_deployments' is disabled, issue a warning if required_deployment_environments is non-empty.
        if (
            self.requires_deployments is False
            and is_set_and_valid(self.required_deployment_environments)
            and len(self.required_deployment_environments) > 0
        ):
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header(parent_object)} has "
                f"'requires_deployments' disabled but "
                f"'required_deployment_environments' is set to "
                f"'{self.required_deployment_environments}', setting will be ignored.",
            )

        if self.requires_deployments is True and len(self.required_deployment_environments) > 0:
            from .repository import Repository

            environments = cast(Repository, parent_object).environments

            environments_by_name = associate_by_key(environments, lambda x: x.name)
            for env_name in self.required_deployment_environments:
                if env_name not in environments_by_name:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} requires deployment environment "
                        f"'{env_name}' which is not defined in the repository itself.",
                    )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        # disable diff computation for dependent fields of requires_pull_request,
        if self.requires_pull_request is False:
            if field.name in [
                "required_approving_review_count",
                "dismisses_stale_reviews",
                "requires_code_owner_review",
                "requires_last_push_approval",
                "requires_review_thread_resolution",
            ]:
                return False

        if self.requires_status_checks is False:
            if field.name in [
                "required_status_checks",
                "requires_strict_status_checks",
            ]:
                return False

        if self.requires_deployments is False:
            if field.name in ["required_deployment_environments"]:
                return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    @classmethod
    def from_model_data(cls, data: dict[str, Any]):
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]):
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping: dict[str, Any] = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update(
            {
                "include_refs": OptionalS("conditions", "ref_name", "include", default=[]),
                "exclude_refs": OptionalS("conditions", "ref_name", "exclude", default=[]),
            }
        )

        rules = data.get("rules", [])

        def check_simple_rule(prop_key: str, rule_type: str, value_if_rule_is_present: bool) -> None:
            if any((_ := rule) for rule in rules if rule["type"] == rule_type):
                mapping[prop_key] = K(value_if_rule_is_present)
            else:
                mapping[prop_key] = K(not value_if_rule_is_present)

        check_simple_rule("allows_deletions", "deletion", False)
        check_simple_rule("allows_creations", "creation", False)
        check_simple_rule("allows_updates", "update", False)
        check_simple_rule("allows_force_pushes", "non_fast_forward", False)

        check_simple_rule("requires_commit_signatures", "required_signatures", True)
        check_simple_rule("requires_linear_history", "required_linear_history", True)

        # bypass actors
        if "bypass_actors" in data:
            bypass_actors = data["bypass_actors"]
            transformed_actors = []
            for actor in bypass_actors:
                actor_type = actor["actor_type"]

                if actor_type == "RepositoryRole" or actor_type == "OrganizationAdmin":
                    role = cls._roles.get(str(actor["actor_id"]), None)
                    if role is None:
                        print_warn(f"fail to map repository role '{actor['actor_id']}', skipping")
                        continue
                    transformed_actor = f"#{role}"
                elif actor_type == "Team":
                    transformed_actor = f"@{actor['team_slug']}"
                elif actor_type == "Integration":
                    transformed_actor = actor["app_slug"]
                else:
                    continue

                bypass_mode = actor.get("bypass_mode", "always")
                if bypass_mode != "always":
                    transformed_actor = f"{transformed_actor}:{bypass_mode}"

                transformed_actors.append(transformed_actor)

            mapping["bypass_actors"] = K(transformed_actors)

        else:
            mapping["bypass_actors"] = K([])

        # requires pull request
        if any((found := rule) for rule in rules if rule["type"] == "pull_request"):
            mapping["requires_pull_request"] = K(True)
            parameters = found.get("parameters", {})

            mapping["required_approving_review_count"] = K(parameters.get("required_approving_review_count", None))
            mapping["dismisses_stale_reviews"] = K(parameters.get("dismiss_stale_reviews_on_push", UNSET))
            mapping["requires_code_owner_review"] = K(parameters.get("require_code_owner_review", UNSET))
            mapping["requires_last_push_approval"] = K(parameters.get("require_last_push_approval", UNSET))
            mapping["requires_review_thread_resolution"] = K(parameters.get("required_review_thread_resolution", UNSET))
        else:
            mapping["requires_pull_request"] = K(False)
            mapping["required_approving_review_count"] = K(None)
            mapping["dismisses_stale_reviews"] = K(UNSET)
            mapping["requires_code_owner_review"] = K(UNSET)
            mapping["requires_last_push_approval"] = K(UNSET)
            mapping["requires_review_thread_resolution"] = K(UNSET)

        # required status checks
        if any((found := rule) for rule in rules if rule["type"] == "required_status_checks"):
            mapping["requires_status_checks"] = K(True)
            parameters = found.get("parameters", {})

            mapping["requires_strict_status_checks"] = K(parameters.get("strict_required_status_checks_policy", UNSET))

            raw_status_checks = parameters.get("required_status_checks", [])
            status_checks = []
            for status_check in raw_status_checks:
                if "app_slug" in status_check:
                    check = status_check["app_slug"] + ":" + status_check["context"]
                else:
                    check = status_check["context"]

                status_checks.append(check)

            mapping["required_status_checks"] = K(status_checks)
        else:
            mapping["requires_status_checks"] = K(False)
            mapping["requires_strict_status_checks"] = K(UNSET)
            mapping["required_status_checks"] = K([])

        # required deployments
        if any((found := rule) for rule in rules if rule["type"] == "required_deployments"):
            mapping["requires_deployments"] = K(True)
            deployment_environments = found.get("parameters", {}).get("required_deployment_environments", [])
            mapping["required_deployment_environments"] = K(deployment_environments)
        else:
            mapping["requires_deployments"] = K(False)
            mapping["required_deployment_environments"] = K([])

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

        def pop_mapping(keys: list[str]) -> None:
            for key_to_pop in keys:
                if key_to_pop in mapping:
                    mapping.pop(key_to_pop)

        # include / excludes
        ref_names = {}
        if "include_refs" in data:
            mapping.pop("include_refs")
            ref_names["include"] = K(data["include_refs"])

        if "exclude_refs" in data:
            mapping.pop("exclude_refs")
            ref_names["exclude"] = K(data["exclude_refs"])

        if len(ref_names) > 0:
            mapping["conditions"] = {"ref_name": ref_names}

        # bypass actors
        if "bypass_actors" in data:
            bypass_actors: list[str] = data["bypass_actors"]
            transformed_actors = []

            def extract_actor_and_bypass_mode(encoded_data: str) -> tuple[str, str]:
                if ":" in encoded_data:
                    a, m = re.split(":", encoded_data, 1)
                else:
                    a = encoded_data
                    m = "always"

                return a, m

            for actor in bypass_actors:
                if actor.startswith("#"):
                    role, bypass_mode = extract_actor_and_bypass_mode(actor[1:])
                    actor_type = "RepositoryRole"
                    actor_id = cls._inverted_roles[role]
                    if actor_id == "1":
                        actor_type = "OrganizationAdmin"
                elif actor.startswith("@"):
                    team, bypass_mode = extract_actor_and_bypass_mode(actor[1:])
                    actor_type = "Team"
                    actor_id = (await provider.rest_api.org.get_team_ids(team))[0]
                else:
                    app, bypass_mode = extract_actor_and_bypass_mode(actor)
                    actor_type = "Integration"
                    actor_id = (await provider.rest_api.app.get_app_ids(app))[0]

                transformed_actors.append(
                    {"actor_id": K(int(actor_id)), "actor_type": K(actor_type), "bypass_mode": K(bypass_mode)}
                )

            mapping["bypass_actors"] = transformed_actors

        # rules
        rules: list[Any] = []

        def add_simple_rule(prop_key: str, rule_type: str, inverted: bool) -> None:
            if prop_key in data:
                mapping.pop(prop_key)
                prop_value = data[prop_key]

                if (inverted and not prop_value) or (not inverted and prop_value):
                    rules.append({"type": K(rule_type)})

        add_simple_rule("allows_deletions", "deletion", True)
        add_simple_rule("allows_creations", "creation", True)
        add_simple_rule("allows_updates", "update", True)
        add_simple_rule("allows_force_pushes", "non_fast_forward", True)

        add_simple_rule("requires_commit_signatures", "required_signatures", False)
        add_simple_rule("requires_linear_history", "required_linear_history", False)

        def add_parameter(prop_key: str, param_key: str, params: dict[str, Any]):
            if prop_key in data:
                params[param_key] = S(prop_key)

        # requires pull request
        if "requires_pull_request" in data:
            value = data["requires_pull_request"]

            if value is True:
                rule = {"type": K("pull_request")}
                pull_parameters: dict[str, Any] = {}

                add_parameter("required_approving_review_count", "required_approving_review_count", pull_parameters)
                add_parameter("dismisses_stale_reviews", "dismiss_stale_reviews_on_push", pull_parameters)
                add_parameter("requires_code_owner_review", "require_code_owner_review", pull_parameters)
                add_parameter("requires_last_push_approval", "require_last_push_approval", pull_parameters)
                add_parameter("requires_review_thread_resolution", "required_review_thread_resolution", pull_parameters)

                rule["parameters"] = pull_parameters
                rules.append(rule)

        pop_mapping(
            [
                "requires_pull_request",
                "required_approving_review_count",
                "dismisses_stale_reviews",
                "requires_code_owner_review",
                "requires_last_push_approval",
                "requires_last_push_approval",
                "requires_review_thread_resolution",
            ]
        )

        # required status checks
        if "requires_status_checks" in data:
            value = data["requires_status_checks"]
            if value is True:
                rule = {"type": K("required_status_checks")}
                status_checks_parameters: dict[str, Any] = {}
                add_parameter(
                    "requires_strict_status_checks", "strict_required_status_checks_policy", status_checks_parameters
                )

                if "required_status_checks" in data:
                    required_status_checks = data["required_status_checks"]
                    app_slugs = set()

                    for check in required_status_checks:
                        if ":" in check:
                            app_slug, context = re.split(":", check, 1)

                            if app_slug != "any":
                                app_slugs.add(app_slug)

                    app_ids = await provider.get_app_ids(app_slugs)

                    transformed_checks = []
                    for check in required_status_checks:
                        if ":" in check:
                            app_slug, context = re.split(":", check, 1)

                            if app_slug == "any":
                                app_slug = None
                        else:
                            app_slug = None
                            context = check

                        if app_slug is None:
                            transformed_checks.append({"context": context})
                        else:
                            transformed_checks.append({"integration_id": app_ids[app_slug], "context": context})

                    status_checks_parameters["required_status_checks"] = K(transformed_checks)

                rule["parameters"] = status_checks_parameters
                rules.append(rule)

        pop_mapping(["requires_status_checks", "requires_strict_status_checks", "required_status_checks"])

        # # required deployments
        if "requires_deployments" in data:
            value = data["requires_deployments"]
            if value is True:
                rule = {"type": K("required_deployments")}
                deployment_parameters: dict[str, Any] = {}
                add_parameter(
                    "required_deployment_environments", "required_deployment_environments", deployment_parameters
                )
                rule["parameters"] = deployment_parameters
                rules.append(rule)

        pop_mapping(["requires_deployments", "required_deployment_environments"])

        if len(rules) > 0:
            mapping["rules"] = rules

        return mapping
