#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.models.branch_protection_rule import BranchProtectionRule
from otterdog.utils import UNSET, Change

from . import ModelTest


class BranchProtectionRuleTest(ModelTest):
    @property
    def model_data(self):
        return self.load_json_resource("otterdog-bpr.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-bpr.json")

    def test_load_from_model(self):
        bpr = BranchProtectionRule.from_model(self.model_data)

        assert bpr.id is UNSET
        assert bpr.pattern == "main"
        assert bpr.allowsDeletions is False
        assert bpr.allowsForcePushes is False
        assert bpr.dismissesStaleReviews is False
        assert bpr.isAdminEnforced is False
        assert bpr.lockAllowsFetchAndMerge is False
        assert bpr.lockBranch is False
        assert bpr.bypassForcePushAllowances == ["/netomi"]
        assert bpr.bypassPullRequestAllowances == ["/netomi"]
        assert bpr.pushRestrictions == ["/netomi"]
        assert bpr.requireLastPushApproval is False
        assert bpr.requiredApprovingReviewCount == 2
        assert bpr.requiresApprovingReviews is True
        assert bpr.requiresCodeOwnerReviews is False
        assert bpr.requiresCommitSignatures is False
        assert bpr.requiresConversationResolution is False
        assert bpr.requiresLinearHistory is False
        assert bpr.requiresStatusChecks is True
        assert bpr.requiresStrictStatusChecks is False
        assert bpr.restrictsReviewDismissals is False
        assert bpr.reviewDismissalAllowances == ["/netomi"]
        assert bpr.requiredStatusChecks == ["eclipse-eca-validation:eclipsefdn/eca","any:Run CI"]

    def test_load_from_provider(self):
        bpr = BranchProtectionRule.from_provider(self.provider_data)

        assert bpr.id == "BPR_kwDOI9xAhM4CC77t"
        assert bpr.pattern == "main"
        assert bpr.allowsDeletions is False
        assert bpr.allowsForcePushes is False
        assert bpr.dismissesStaleReviews is False
        assert bpr.isAdminEnforced is False
        assert bpr.lockAllowsFetchAndMerge is False
        assert bpr.lockBranch is False
        assert bpr.bypassForcePushAllowances == ["/netomi"]
        assert bpr.bypassPullRequestAllowances == ["/netomi"]
        assert bpr.pushRestrictions == ["/netomi"]
        assert bpr.requireLastPushApproval is False
        assert bpr.requiredApprovingReviewCount == 2
        assert bpr.requiresApprovingReviews is True
        assert bpr.requiresCodeOwnerReviews is False
        assert bpr.requiresCommitSignatures is False
        assert bpr.requiresConversationResolution is False
        assert bpr.requiresLinearHistory is False
        assert bpr.requiresStatusChecks is True
        assert bpr.requiresStrictStatusChecks is False
        assert bpr.restrictsReviewDismissals is False
        assert bpr.reviewDismissalAllowances == ["/netomi"]
        assert bpr.requiredStatusChecks == ["any:Run CI"]

    def test_patch(self):
        current = BranchProtectionRule.from_model(self.model_data)

        default = BranchProtectionRule.from_model(self.model_data)

        default.pattern = None
        default.requiresStatusChecks = False
        default.requiredStatusChecks = ["eclipse-eca-validation:eclipsefdn/eca"]

        patch = current.get_patch_to(default)

        assert len(patch) == 3
        assert patch["pattern"] == current.pattern
        assert patch["requiresStatusChecks"] is current.requiresStatusChecks
        assert patch["requiredStatusChecks"] == ["any:Run CI"]

    def test_difference(self):
        current = BranchProtectionRule.from_model(self.model_data)
        other = BranchProtectionRule.from_model(self.model_data)

        other.requiresApprovingReviews = False
        other.requiredStatusChecks = ["eclipse-eca-validation:eclipsefdn/eca"]

        diff = current.get_difference_from(other)

        assert len(diff) == 2
        assert diff["requiresApprovingReviews"] == Change(other.requiresApprovingReviews,
                                                          current.requiresApprovingReviews)
        assert diff["requiredStatusChecks"] == Change(other.requiredStatusChecks,
                                                      current.requiredStatusChecks)
