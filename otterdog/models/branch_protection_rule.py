# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import re
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Union

from jsonbender import bend, S, OptionalS, Forall, K

from otterdog.providers.github import Github
from otterdog.utils import UNSET, is_unset, is_set_and_valid

from . import ModelObject, ValidationContext, FailureType


@dataclass
class BranchProtectionRule(ModelObject):
    id: str = dataclass_field(metadata={"external_only": True})
    pattern: str = dataclass_field(metadata={"key": True})
    allowsDeletions: bool
    allowsForcePushes: bool
    dismissesStaleReviews: bool
    isAdminEnforced: bool
    lockAllowsFetchAndMerge: bool
    lockBranch: bool
    bypassForcePushAllowances: list[str]
    bypassPullRequestAllowances: list[str]
    pushRestrictions: list[str]
    requireLastPushApproval: bool
    requiredApprovingReviewCount: int
    requiresApprovingReviews: bool
    requiresCodeOwnerReviews: bool
    requiresCommitSignatures: bool
    requiresConversationResolution: bool
    requiresLinearHistory: bool
    requiresStatusChecks: bool
    requiresStrictStatusChecks: bool
    restrictsReviewDismissals: bool
    reviewDismissalAllowances: list[str]
    requiredStatusChecks: list[str]

    def validate(self, context: ValidationContext, parent_object: object) -> None:
        repo_name: str = parent_object.name

        requiresApprovingReviews = self.requiresApprovingReviews is True
        requiredApprovingReviewCount = self.requiredApprovingReviewCount

        if requiresApprovingReviews and not is_unset(requiredApprovingReviewCount):
            if requiredApprovingReviewCount is None or requiredApprovingReviewCount < 0:
                context.add_failure(FailureType.ERROR,
                                    f"branch_protection_rule[repo=\"{repo_name}\",pattern=\"{self.pattern}\"] has"
                                    f" 'requiredApprovingReviews' enabled but 'requiredApprovingReviewCount' "
                                    f"is not set.")

        permitsReviewDismissals = self.restrictsReviewDismissals is False
        reviewDismissalAllowances = self.reviewDismissalAllowances

        if permitsReviewDismissals and \
                is_set_and_valid(reviewDismissalAllowances) and \
                len(reviewDismissalAllowances) > 0:
            context.add_failure(FailureType.ERROR,
                                f"branch_protection_rule[repo=\"{repo_name}\",pattern=\"{self.pattern}\"] has"
                                f" 'restrictsReviewDismissals' disabled but 'reviewDismissalAllowances' is set.")

        allowsForcePushes = self.allowsForcePushes is True
        bypassForcePushAllowances = self.bypassForcePushAllowances

        if allowsForcePushes and \
                is_set_and_valid(bypassForcePushAllowances) and \
                len(bypassForcePushAllowances) > 0:
            context.add_failure(FailureType.ERROR,
                                f"branch_protection_rule[repo=\"{repo_name}\",pattern=\"{self.pattern}\"] has"
                                f" 'allowsForcePushes' enabled but 'bypassForcePushAllowances' is not empty.")

        ignoresStatusChecks = self.requiresStatusChecks is False
        requiredStatusChecks = self.requiredStatusChecks

        if ignoresStatusChecks and \
                is_set_and_valid(requiredStatusChecks) and \
                len(requiredStatusChecks) > 0:
            context.add_failure(FailureType.ERROR,
                                f"branch_protection_rule[repo=\"{repo_name}\",pattern=\"{self.pattern}\"] has"
                                f" 'requiresStatusChecks' disabled but 'requiredStatusChecks' is not empty.")

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "BranchProtectionRule":
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]) -> "BranchProtectionRule":
        mapping = {k: S(k) for k in map(lambda x: x.name, cls.all_fields())}

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

        mapping.update({"requiredStatusChecks": S("requiredStatusChecks") >> Forall(lambda x: transform_app(x))})

        return cls(**bend(mapping, data))

    @classmethod
    def _to_provider(cls, data: dict[str, Any], provider: Union[Github, None] = None) -> dict[str, Any]:
        mapping = {field.name: S(field.name) for field in cls.provider_fields() if
                   not is_unset(data.get(field.name, UNSET))}

        if "pushRestrictions" in data:
            mapping.pop("pushRestrictions")
            restricts_pushes = data["pushRestrictions"]
            if is_set_and_valid(restricts_pushes):
                assert provider is not None
                actor_ids = provider.get_actor_ids(restricts_pushes)
                mapping["pushActorIds"] = K(actor_ids)
                mapping["restrictsPushes"] = K(True if len(actor_ids) > 0 else False)

        if "reviewDismissalAllowances" in data:
            mapping.pop("reviewDismissalAllowances")
            review_dismissal_allowances = data["reviewDismissalAllowances"]
            if is_set_and_valid(review_dismissal_allowances):
                assert provider is not None
                actor_ids = provider.get_actor_ids(review_dismissal_allowances)
                mapping["reviewDismissalActorIds"] = K(actor_ids)

        if "bypassPullRequestAllowances" in data:
            mapping.pop("bypassPullRequestAllowances")
            bypass_pull_request_allowances = data["bypassPullRequestAllowances"]
            if is_set_and_valid(bypass_pull_request_allowances):
                assert provider is not None
                actor_ids = provider.get_actor_ids(bypass_pull_request_allowances)
                mapping["bypassPullRequestActorIds"] = K(actor_ids)

        if "bypassForcePushAllowances" in data:
            mapping.pop("bypassForcePushAllowances")
            bypass_force_push_allowances = data["bypassForcePushAllowances"]
            if is_set_and_valid(bypass_force_push_allowances):
                assert provider is not None
                actor_ids = provider.get_actor_ids(bypass_force_push_allowances)
                mapping["bypassForcePushActorIds"] = K(actor_ids)

        if "requiredStatusChecks" in data:
            mapping.pop("requiredStatusChecks")
            required_status_checks = data["requiredStatusChecks"]
            if is_set_and_valid(required_status_checks):
                assert provider is not None

                app_slugs = set()

                for check in required_status_checks:
                    if ":" in check:
                        app_slug, context = re.split(":", check, 1)

                        if app_slug != "any":
                            app_slugs.add(app_slug)
                    else:
                        app_slugs.add("github-actions")

                app_ids = provider.get_app_ids(app_slugs)

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
