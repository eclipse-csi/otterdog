#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
import re
from typing import TYPE_CHECKING, Any, cast

from jsonbender import Forall, K, OptionalS, S  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.utils import (
    UNSET,
    associate_by_key,
    expect_type,
    is_set_and_valid,
    is_unset,
    snake_to_camel_case,
    unwrap,
)

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


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

    requires_pull_request: bool
    # the following settings are only taken into account
    # when requires_pull_request is True
    required_approving_review_count: int | None
    dismisses_stale_reviews: bool
    requires_code_owner_reviews: bool
    require_last_push_approval: bool
    bypass_pull_request_allowances: list[str]
    restricts_review_dismissals: bool
    review_dismissal_allowances: list[str]

    bypass_force_push_allowances: list[str]

    restricts_pushes: bool
    blocks_creations: bool
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

        if self.requires_pull_request is False:
            if is_set_and_valid(self.required_approving_review_count):
                context.add_failure(
                    FailureType.INFO,
                    f"{self.get_model_header(parent_object)} has 'requires_pull_request' disabled, "
                    f"but 'required_approving_review_count' is set to "
                    f"'{self.required_approving_review_count}', setting will be ignored.",
                )

            for key in [
                "dismisses_stale_reviews",
                "requires_code_owner_reviews",
                "require_last_push_approval",
                "restricts_review_dismissals",
            ]:
                if self.__getattribute__(key) is True:
                    context.add_failure(
                        FailureType.WARNING,
                        f"{self.get_model_header(parent_object)} has 'requires_pull_request' disabled, "
                        f"but '{key}' is enabled, setting will be ignored.",
                    )

            for key in [
                "bypass_pull_request_allowances",
                "review_dismissal_allowances",
            ]:
                value = self.__getattribute__(key)
                if not is_unset(value) and len(value) > 0:
                    context.add_failure(
                        FailureType.WARNING,
                        f"{self.get_model_header(parent_object)} has 'requires_pull_request' disabled, "
                        f"but '{key}' is set to '{value}', setting will be ignored.",
                    )

        # required_approving_review_count must be defined when requires_pull_request is enabled
        required_approving_review_count = self.required_approving_review_count
        if self.requires_pull_request is True and not is_unset(required_approving_review_count):
            if required_approving_review_count is None or required_approving_review_count < 0:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'requires_pull_request' enabled, "
                    f"but 'required_approving_review_count' is not set (must be set to a non negative number).",
                )

        # if 'review_dismissal_allowances' is disabled, issue a warning if review_dismissal_allowances is non-empty.
        review_dismissal_allowances = self.review_dismissal_allowances
        if (
            self.restricts_review_dismissals is False
            and is_set_and_valid(review_dismissal_allowances)
            and len(review_dismissal_allowances) > 0
        ):
            context.add_failure(
                FailureType.INFO,
                f"{self.get_model_header(parent_object)} has 'restricts_review_dismissals' disabled, "
                f"but 'review_dismissal_allowances' is set to '{self.review_dismissal_allowances}', "
                f"setting will be ignored.",
            )

        # if 'allows_force_pushes' is enabled, issue an error if bypass_force_push_allowances is non-empty.
        if (
            self.allows_force_pushes is True
            and is_set_and_valid(self.bypass_force_push_allowances)
            and len(self.bypass_force_push_allowances) > 0
        ):
            context.add_failure(
                FailureType.INFO,
                f"{self.get_model_header(parent_object)} has 'allows_force_pushes' enabled, "
                f"but 'bypass_force_push_allowances' is set to '{self.bypass_force_push_allowances}', "
                f"setting will be ignored.",
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
                f"{self.get_model_header(parent_object)} has 'requires_status_checks' disabled, "
                f"but 'required_status_checks' is set to '{self.required_status_checks}', setting will be ignored.",
            )

        # if 'requires_deployments' is disabled, issue a warning if required_deployment_environments is non-empty.
        if (
            self.requires_deployments is False
            and is_set_and_valid(self.required_deployment_environments)
            and len(self.required_deployment_environments) > 0
        ):
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header(parent_object)} has 'requires_deployments' disabled, "
                f"but 'required_deployment_environments' is set to '{self.required_deployment_environments}', "
                f"setting will be ignored.",
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

        # if 'restricts_pushes' is disabled, issue a warning if push_restrictions is non-empty.
        if (
            self.restricts_pushes is False
            and is_set_and_valid(self.push_restrictions)
            and len(self.push_restrictions) > 0
        ):
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header(parent_object)} has "
                f"'restricts_pushes' disabled but 'push_restrictions' is set to '{self.push_restrictions}', "
                f"setting will be ignored.",
            )

        # if 'restricts_pushes' is disabled, issue a warning if blocks_creations is enabled.
        if self.restricts_pushes is False and self.blocks_creations is True:
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header(parent_object)} has "
                f"'restricts_pushes' disabled but 'blocks_creations' is set to '{self.blocks_creations}', "
                f"setting will be ignored.",
            )

        # if 'lock_branch' is disabled, issue a warning if lock_allows_fetch_and_merge is enabled.
        if self.lock_branch is False and self.lock_allows_fetch_and_merge is True:
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header(parent_object)} has 'lock_branch' disabled but "
                f"'lock_allows_fetch_and_merge' enabled, setting will be ignored.",
            )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        # disable diff computation for dependent fields of requires_pull_request,
        if self.requires_pull_request is False:
            if field.name in [
                "required_approving_review_count",
                "dismisses_stale_reviews",
                "requires_code_owner_reviews",
                "require_last_push_approval",
                "bypass_pull_request_allowances",
                "restricts_review_dismissals",
                "review_dismissal_allowances",
            ]:
                return False

        if self.restricts_review_dismissals is False and field.name in ["review_dismissal_allowances"]:
            return False

        if self.allows_force_pushes is True and field.name in ["bypass_force_push_allowances"]:
            return False

        if self.requires_status_checks is False and field.name in [
            "required_status_checks",
            "requires_strict_status_checks",
        ]:
            return False

        if self.requires_deployments is False and field.name in ["required_deployment_environments"]:
            return False

        if self.restricts_pushes is False:
            if field.name in ["push_restrictions"]:
                return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = {k: OptionalS(snake_to_camel_case(k), default=UNSET) for k in (x.name for x in cls.all_fields())}
        mapping["requires_pull_request"] = OptionalS("requiresApprovingReviews", default=UNSET)

        def transform_app(x):
            app = x["app"]
            context = x["context"]

            if app is None:
                app_prefix = "any:"
            else:
                app_slug = app["slug"]
                app_prefix = "" if app_slug == "github-actions" else f"{app_slug}:"

            return f"{app_prefix}{context}"

        mapping["required_status_checks"] = OptionalS("requiredStatusChecks", default=[]) >> Forall(
            lambda x: transform_app(x)
        )
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            snake_to_camel_case(field.name): S(field.name)
            for field in cls.provider_fields()
            if not is_unset(data.get(field.name, UNSET))
        }

        if "requires_pull_request" in data:
            mapping.pop("requiresPullRequest")
            mapping["requiresApprovingReviews"] = K(data["requires_pull_request"])

        if "push_restrictions" in data:
            mapping.pop("pushRestrictions")
            push_restrictions = data["push_restrictions"]
            if is_set_and_valid(push_restrictions):
                actor_ids = await provider.get_actor_node_ids(push_restrictions)
                mapping["pushActorIds"] = K(actor_ids)

        if "review_dismissal_allowances" in data:
            mapping.pop("reviewDismissalAllowances")
            review_dismissal_allowances = data["review_dismissal_allowances"]
            if is_set_and_valid(review_dismissal_allowances):
                actor_ids = await provider.get_actor_node_ids(review_dismissal_allowances)
                mapping["reviewDismissalActorIds"] = K(actor_ids)

        if "bypass_pull_request_allowances" in data:
            mapping.pop("bypassPullRequestAllowances")
            bypass_pull_request_allowances = data["bypass_pull_request_allowances"]
            if is_set_and_valid(bypass_pull_request_allowances):
                actor_ids = await provider.get_actor_node_ids(bypass_pull_request_allowances)
                mapping["bypassPullRequestActorIds"] = K(actor_ids)

        if "bypass_force_push_allowances" in data:
            mapping.pop("bypassForcePushAllowances")
            bypass_force_push_allowances = data["bypass_force_push_allowances"]
            if is_set_and_valid(bypass_force_push_allowances):
                actor_ids = await provider.get_actor_node_ids(bypass_force_push_allowances)
                mapping["bypassForcePushActorIds"] = K(actor_ids)

        if "required_status_checks" in data:
            mapping.pop("requiredStatusChecks")
            required_status_checks = data["required_status_checks"]
            if is_set_and_valid(required_status_checks):
                app_slugs = set()

                for check in required_status_checks:
                    if ":" in check:
                        app_slug, context = re.split(":", check, maxsplit=1)

                        if app_slug != "any":
                            app_slugs.add(app_slug)
                    else:
                        app_slugs.add("github-actions")

                app_ids = await provider.get_app_node_ids(app_slugs)

                transformed_checks = []
                for check in required_status_checks:
                    if ":" in check:
                        app_slug, context = re.split(":", check, maxsplit=1)
                    else:
                        app_slug = "github-actions"
                        context = check

                    if app_slug == "any":
                        transformed_checks.append({"appId": "any", "context": context})
                    else:
                        transformed_checks.append({"appId": app_ids[app_slug], "context": context})

                mapping["requiredStatusChecks"] = K(transformed_checks)

        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_branch_protection_rule}"

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[BranchProtectionRule],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        from .repository import Repository

        match patch.patch_type:
            case LivePatchType.ADD:
                repository = expect_type(patch.parent_object, Repository)
                await provider.add_branch_protection_rule(
                    org_id,
                    repository.name,
                    repository.node_id,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                current_object = unwrap(patch.current_object)
                repository = expect_type(patch.parent_object, Repository)
                await provider.delete_branch_protection_rule(
                    org_id,
                    repository.name,
                    current_object.id,
                    current_object.pattern,
                )

            case LivePatchType.CHANGE:
                current_object = unwrap(patch.current_object)
                repository = expect_type(patch.parent_object, Repository)
                await provider.update_branch_protection_rule(
                    org_id,
                    repository.name,
                    current_object.id,
                    current_object.pattern,
                    await cls.changes_to_provider(org_id, unwrap(patch.changes), provider),
                )
