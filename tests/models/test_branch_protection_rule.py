#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from unittest.mock import MagicMock

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

    @property
    def provider(self):
        def get_actor_ids(actors):
            return [f"id_{actor}" for actor in actors]

        def get_app_ids(app_names):
            return {app: f"id_{app}" for app in app_names}

        provider = MagicMock()
        provider.get_actor_ids = MagicMock(side_effect=get_actor_ids)
        provider.get_app_ids = MagicMock(side_effect=get_app_ids)
        return provider

    def test_load_from_model(self):
        bpr = BranchProtectionRule.from_model_data(self.model_data)

        assert bpr.id is UNSET
        assert bpr.pattern == "main"
        assert bpr.allows_deletions is False
        assert bpr.allows_force_pushes is False
        assert bpr.dismisses_stale_reviews is False
        assert bpr.is_admin_enforced is False
        assert bpr.lock_allows_fetch_and_merge is False
        assert bpr.lock_branch is False
        assert bpr.bypass_force_push_allowances == ["/netomi"]
        assert bpr.bypass_pull_request_allowances == ["/netomi"]
        assert bpr.push_restrictions == ["/netomi"]
        assert bpr.require_last_push_approval is False
        assert bpr.required_approving_review_count == 2
        assert bpr.requires_approving_reviews is True
        assert bpr.requires_code_owner_reviews is False
        assert bpr.requires_commit_signatures is False
        assert bpr.requires_conversation_resolution is False
        assert bpr.requires_linear_history is False
        assert bpr.requires_status_checks is True
        assert bpr.requires_strict_status_checks is False
        assert bpr.restricts_review_dismissals is False
        assert bpr.review_dismissal_allowances == ["/netomi"]
        assert bpr.required_status_checks == ["eclipse-eca-validation:eclipsefdn/eca", "any:Run CI"]

    def test_load_from_provider(self):
        bpr = BranchProtectionRule.from_provider_data(self.provider_data)

        assert bpr.id == "BPR_kwDOI9xAhM4CC77t"
        assert bpr.pattern == "main"
        assert bpr.allows_deletions is False
        assert bpr.allows_force_pushes is False
        assert bpr.dismisses_stale_reviews is False
        assert bpr.is_admin_enforced is False
        assert bpr.lock_allows_fetch_and_merge is False
        assert bpr.lock_branch is False
        assert bpr.bypass_force_push_allowances == ["/netomi"]
        assert bpr.bypass_pull_request_allowances == ["/netomi"]
        assert bpr.push_restrictions == ["/netomi"]
        assert bpr.require_last_push_approval is False
        assert bpr.required_approving_review_count == 2
        assert bpr.requires_approving_reviews is True
        assert bpr.requires_code_owner_reviews is False
        assert bpr.requires_commit_signatures is False
        assert bpr.requires_conversation_resolution is False
        assert bpr.requires_linear_history is False
        assert bpr.requires_status_checks is True
        assert bpr.requires_strict_status_checks is False
        assert bpr.restricts_review_dismissals is False
        assert bpr.review_dismissal_allowances == ["/netomi"]
        assert bpr.required_status_checks == ["any:Run CI"]

    def test_to_provider(self):
        bpr = BranchProtectionRule.from_model_data(self.model_data)

        provider_data = bpr.to_provider_data(self.provider)

        assert len(provider_data) == 23
        assert provider_data["pattern"] == "main"
        assert provider_data["pushActorIds"] == ["id_/netomi"]
        assert provider_data["requiredStatusChecks"] == [
            {'appId': 'id_eclipse-eca-validation', 'context': 'eclipsefdn/eca'}, {'appId': 'any', 'context': 'Run CI'}]

    def test_changes_to_provider(self):
        current = BranchProtectionRule.from_model_data(self.model_data)
        other = BranchProtectionRule.from_model_data(self.model_data)

        other.requires_approving_reviews = False
        other.required_status_checks = ["eclipse-eca-validation:eclipsefdn/eca"]

        changes = current.get_difference_from(other)
        provider_data = BranchProtectionRule.changes_to_provider(changes, self.provider)

        assert len(provider_data) == 2
        assert provider_data["requiresApprovingReviews"] is True
        assert provider_data["requiredStatusChecks"] == [
            {'appId': 'id_eclipse-eca-validation', 'context': 'eclipsefdn/eca'}, {'appId': 'any', 'context': 'Run CI'}]

    def test_patch(self):
        current = BranchProtectionRule.from_model_data(self.model_data)
        default = BranchProtectionRule.from_model_data(self.model_data)

        default.pattern = None
        default.requires_status_checks = False
        default.required_status_checks = ["eclipse-eca-validation:eclipsefdn/eca"]

        patch = current.get_patch_to(default)

        assert len(patch) == 3
        assert patch["pattern"] == current.pattern
        assert patch["requires_status_checks"] is current.requires_status_checks
        assert patch["required_status_checks"] == ["any:Run CI"]

    def test_difference(self):
        current = BranchProtectionRule.from_model_data(self.model_data)
        other = BranchProtectionRule.from_model_data(self.model_data)

        other.requires_approving_reviews = False
        other.required_status_checks = ["eclipse-eca-validation:eclipsefdn/eca"]

        diff = current.get_difference_from(other)

        assert len(diff) == 2
        assert diff["requires_approving_reviews"] == Change(other.requires_approving_reviews,
                                                            current.requires_approving_reviews)
        assert diff["required_status_checks"] == Change(other.required_status_checks,
                                                        current.required_status_checks)
