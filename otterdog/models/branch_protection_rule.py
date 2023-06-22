# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses
import re
from typing import Any, Optional, cast

from jsonbender import bend, S, OptionalS, Forall, K  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject, ValidationContext, FailureType
from otterdog.providers.github import Github
from otterdog.utils import UNSET, is_unset, is_set_and_valid, snake_to_camel_case, IndentingPrinter, \
    write_patch_object_as_json, associate_by_key


@dataclasses.dataclass
class BranchProtectionRule(ModelObject):
    """
    Represents a Branch Protection Rule within a Repository.
    """

    id: str = dataclasses.field(metadata={"external_only": True})
    pattern: str = dataclasses.field(metadata={"key": True})

    allows_deletions: bool
    allows_force_pushes: bool
    is_admin_enforced: bool
    lock_allows_fetch_and_merge: bool
    lock_branch: bool

    # the following settings are only taken into account
    # when requires_approving_reviews is True
    requires_approving_reviews: bool
    required_approving_review_count: Optional[int]
    dismisses_stale_reviews: bool
    requires_code_owner_reviews: bool
    require_last_push_approval: bool
    bypass_pull_request_allowances: list[str]
    restricts_review_dismissals: bool
    review_dismissal_allowances: list[str]

    bypass_force_push_allowances: list[str]
    push_restrictions: list[str]

    requires_commit_signatures: bool
    requires_conversation_resolution: bool
    requires_linear_history: bool

    requires_status_checks: bool
    requires_strict_status_checks: bool
    required_status_checks: list[str]

    requires_deployments: bool
    required_deployment_environments: list[str]

    @property
    def model_object_name(self) -> str:
        return "branch_protection_rule"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        # when requires_approving_reviews is false, issue a warning if dependent settings
        # are still set to non default values.

        if self.requires_approving_reviews is False:
            if is_set_and_valid(self.required_approving_review_count):
                context.add_failure(FailureType.WARNING,
                                    f"{self.get_model_header(parent_object)} has"
                                    f" 'requires_approving_reviews' disabled but 'required_approving_review_count' "
                                    f"is set to '{self.required_approving_review_count}', setting will be ignored.")

            for key in ["dismisses_stale_reviews",
                        "requires_code_owner_reviews",
                        "require_last_push_approval",
                        "restricts_review_dismissals"]:
                if self.__getattribute__(key) is True:
                    context.add_failure(FailureType.WARNING,
                                        f"{self.get_model_header(parent_object)} has"
                                        f" 'requires_approving_reviews' disabled but '{key}' "
                                        f"is enabled, setting will be ignored.")

            for key in ["bypass_pull_request_allowances", "review_dismissal_allowances"]:
                value = self.__getattribute__(key)
                if not is_unset(value) and len(value) > 0:
                    context.add_failure(FailureType.WARNING,
                                        f"{self.get_model_header(parent_object)} has"
                                        f" 'requires_approving_reviews' disabled but '{key}' "
                                        f"is set to '{value}', setting will be ignored.")

        # required_approving_review_count must be defined when requires_approving_reviews is enabled
        required_approving_review_count = self.required_approving_review_count
        if self.requires_approving_reviews is True and not is_unset(required_approving_review_count):
            if required_approving_review_count is None or required_approving_review_count < 0:
                context.add_failure(FailureType.ERROR,
                                    f"{self.get_model_header(parent_object)} has"
                                    f" 'requires_approving_reviews' enabled but 'required_approving_review_count' "
                                    f"is not set (must be null or a non negative number).")

        # if 'review_dismissal_allowances' is disabled, issue a warning if review_dismissal_allowances is non-empty.
        review_dismissal_allowances = self.review_dismissal_allowances
        if self.restricts_review_dismissals is False and \
                is_set_and_valid(review_dismissal_allowances) and \
                len(review_dismissal_allowances) > 0:
            context.add_failure(FailureType.WARNING,
                                f"{self.get_model_header(parent_object)} has"
                                f" 'restricts_review_dismissals' disabled but "
                                f"'review_dismissal_allowances' is set to '{self.review_dismissal_allowances}', "
                                f"setting will be ignored.")

        # if 'allows_force_pushes' is enabled, issue a warning if bypass_force_push_allowances is non-empty.
        bypass_force_push_allowances = self.bypass_force_push_allowances
        if self.allows_force_pushes is True and \
                is_set_and_valid(bypass_force_push_allowances) and \
                len(bypass_force_push_allowances) > 0:
            context.add_failure(FailureType.WARNING,
                                f"{self.get_model_header(parent_object)} has"
                                f" 'allows_force_pushes' enabled but "
                                f"'bypass_force_push_allowances' is set to '{self.bypass_force_push_allowances}', "
                                f"setting will be ignored.")

        # if 'requires_status_checks' is disabled, issue a warning if required_status_checks is non-empty.
        required_status_checks = self.required_status_checks
        if self.requires_status_checks is False and \
                is_set_and_valid(required_status_checks) and \
                len(required_status_checks) > 0:
            context.add_failure(FailureType.INFO,
                                f"{self.get_model_header(parent_object)} has"
                                f" 'requires_status_checks' disabled but "
                                f"'required_status_checks' is set to '{self.required_status_checks}', "
                                f"setting will be ignored.")

        # if 'requires_deployments' is disabled, issue a warning if required_deployment_environments is non-empty.
        if self.requires_deployments is False and \
                is_set_and_valid(self.required_deployment_environments) and \
                len(self.required_deployment_environments) > 0:
            context.add_failure(FailureType.WARNING,
                                f"{self.get_model_header(parent_object)} has "
                                f"'requires_deployments' disabled but "
                                f"'required_deployment_environments' is set to "
                                f"'{self.required_deployment_environments}', setting will be ignored.")

        if self.requires_deployments is True and len(self.required_deployment_environments) > 0:
            from .repository import Repository
            environments = cast(Repository, parent_object).environments

            environments_by_name = associate_by_key(environments, lambda x: x.name)
            for env_name in self.required_deployment_environments:
                if env_name not in environments_by_name:
                    context.add_failure(FailureType.ERROR,
                                        f"{self.get_model_header(parent_object)} requires deployment environment "
                                        f"'{env_name}' which is not defined in the repository itself.")

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        # disable diff computation for dependent fields of requires_approving_reviews,
        if self.requires_approving_reviews is False:
            if field.name in ["required_approving_review_count",
                              "dismisses_stale_reviews",
                              "requires_code_owner_reviews",
                              "require_last_push_approval",
                              "bypass_pull_request_allowances",
                              "restricts_review_dismissals",
                              "review_dismissal_allowances"]:
                return False

        if self.restricts_review_dismissals is False:
            if field.name in ["review_dismissal_allowances"]:
                return False

        if self.allows_force_pushes is True:
            if field.name in ["bypass_force_push_allowances"]:
                return False

        if self.requires_status_checks is False:
            if field.name in ["required_status_checks", "requires_strict_status_checks"]:
                return False

        if self.requires_deployments is False:
            if field.name in ["required_deployment_environments"]:
                return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    @classmethod
    def from_model_data(cls, data: dict[str, Any]) -> BranchProtectionRule:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]) -> BranchProtectionRule:
        mapping = {k: OptionalS(snake_to_camel_case(k), default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        def transform_app(x):
            app = x["app"]
            context = x["context"]

            if app is None:
                app_prefix = "any:"
            else:
                app_slug = app["slug"]
                if app_slug == "github-actions":
                    app_prefix = ""
                else:
                    app_prefix = f"{app_slug}:"

            return f"{app_prefix}{context}"

        mapping["required_status_checks"] = \
            OptionalS("requiredStatusChecks", default=[]) >> Forall(lambda x: transform_app(x))

        return cls(**bend(mapping, data))

    @classmethod
    def _to_provider_data(cls, data: dict[str, Any], provider: Optional[Github] = None) -> dict[str, Any]:
        assert provider is not None

        mapping = {snake_to_camel_case(field.name): S(field.name) for field in cls.provider_fields() if
                   not is_unset(data.get(field.name, UNSET))}

        if "push_restrictions" in data:
            mapping.pop("pushRestrictions")
            restricts_pushes = data["push_restrictions"]
            if is_set_and_valid(restricts_pushes):
                actor_ids = provider.get_actor_node_ids(restricts_pushes)
                mapping["pushActorIds"] = K(actor_ids)
                mapping["restrictsPushes"] = K(True if len(actor_ids) > 0 else False)

        if "review_dismissal_allowances" in data:
            mapping.pop("reviewDismissalAllowances")
            review_dismissal_allowances = data["review_dismissal_allowances"]
            if is_set_and_valid(review_dismissal_allowances):
                actor_ids = provider.get_actor_node_ids(review_dismissal_allowances)
                mapping["reviewDismissalActorIds"] = K(actor_ids)

        if "bypass_pull_request_allowances" in data:
            mapping.pop("bypassPullRequestAllowances")
            bypass_pull_request_allowances = data["bypass_pull_request_allowances"]
            if is_set_and_valid(bypass_pull_request_allowances):
                actor_ids = provider.get_actor_node_ids(bypass_pull_request_allowances)
                mapping["bypassPullRequestActorIds"] = K(actor_ids)

        if "bypass_force_push_allowances" in data:
            mapping.pop("bypassForcePushAllowances")
            bypass_force_push_allowances = data["bypass_force_push_allowances"]
            if is_set_and_valid(bypass_force_push_allowances):
                actor_ids = provider.get_actor_node_ids(bypass_force_push_allowances)
                mapping["bypassForcePushActorIds"] = K(actor_ids)

        if "required_status_checks" in data:
            mapping.pop("requiredStatusChecks")
            required_status_checks = data["required_status_checks"]
            if is_set_and_valid(required_status_checks):
                app_slugs = set()

                for check in required_status_checks:
                    if ":" in check:
                        app_slug, context = re.split(":", check, 1)

                        if app_slug != "any":
                            app_slugs.add(app_slug)
                    else:
                        app_slugs.add("github-actions")

                app_ids = provider.get_app_node_ids(app_slugs)

                transformed_checks = []
                for check in required_status_checks:
                    if ":" in check:
                        app_slug, context = re.split(":", check, 1)
                    else:
                        app_slug = "github-actions"
                        context = check

                    if app_slug == "any":
                        transformed_checks.append({"appId": "any", "context": context})
                    else:
                        transformed_checks.append({"appId": app_ids[app_slug], "context": context})

                mapping["requiredStatusChecks"] = K(transformed_checks)

        return bend(mapping, data)

    def to_jsonnet(self,
                   printer: IndentingPrinter,
                   jsonnet_config: JsonnetConfig,
                   extend: bool,
                   default_object: ModelObject) -> None:
        patch = self.get_patch_to(default_object)
        patch.pop("pattern")
        printer.print(f"orgs.{jsonnet_config.create_branch_protection_rule}('{self.pattern}')")
        write_patch_object_as_json(patch, printer)
