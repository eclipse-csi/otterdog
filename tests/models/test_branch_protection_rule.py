#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.utils import UNSET
from otterdog.models.branch_protection_rule import BranchProtectionRule


def test_load_repo_from_model(otterdog_bpr_data):
    bpr = BranchProtectionRule.from_model(otterdog_bpr_data)

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
    assert bpr.requiredStatusChecks == ["any:Run CI"]


def test_load_repo_from_provider(github_bpr_data):
    bpr = BranchProtectionRule.from_provider(github_bpr_data)

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
