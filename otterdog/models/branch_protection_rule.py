# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field as dataclass_field
from typing import Any

from jsonbender import bend, S, OptionalS, Forall

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

    def to_provider(self) -> dict[str, Any]:
        # FIXME: implement correct mapping
        data = self.to_model_dict()

        mapping = {}

        for field in self.model_fields():
            if self.is_read_only(field):
                continue

            key = field.name
            value = self.__getattribute__(key)
            if not is_unset(value):
                mapping[key] = S(key)

        return bend(mapping, data)
