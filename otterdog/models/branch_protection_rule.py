# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field
from typing import Any

from jsonbender import bend, S, OptionalS, K, Forall

from . import ModelObject, UNSET


@dataclass
class BranchProtectionRule(ModelObject):
    id: str = field(metadata={"external_only": True})
    pattern: str = field(metadata={"key": True})
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

    @classmethod
    def from_model(cls, data: dict[str, Any]):
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]):
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
