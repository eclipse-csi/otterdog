#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from collections.abc import Mapping
from typing import Any

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject
from otterdog.models.branch_protection_rule import BranchProtectionRule
from otterdog.utils import UNSET, Change

from . import ModelTest


class BranchProtectionRuleTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return BranchProtectionRule.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_branch_protection_rule

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-bpr.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-bpr.json")

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
        assert bpr.bypass_force_push_allowances == ["@netomi"]
        assert bpr.bypass_pull_request_allowances == ["@netomi"]
        assert bpr.push_restrictions == ["@netomi"]
        assert bpr.require_last_push_approval is False
        assert bpr.required_approving_review_count == 2
        assert bpr.requires_pull_request is True
        assert bpr.requires_code_owner_reviews is False
        assert bpr.requires_commit_signatures is False
        assert bpr.requires_conversation_resolution is False
        assert bpr.requires_linear_history is False
        assert bpr.requires_status_checks is True
        assert bpr.requires_strict_status_checks is False
        assert bpr.restricts_review_dismissals is False
        assert bpr.review_dismissal_allowances == ["@netomi"]
        assert bpr.required_status_checks == ["eclipse-eca-validation:eclipsefdn/eca", "any:Run CI"]

    def test_load_from_provider(self):
        bpr = BranchProtectionRule.from_provider_data(self.org_id, self.provider_data)

        assert bpr.id == "BPR_kwDOI9xAhM4CC77t"
        assert bpr.pattern == "main"
        assert bpr.allows_deletions is False
        assert bpr.allows_force_pushes is False
        assert bpr.dismisses_stale_reviews is False
        assert bpr.is_admin_enforced is False
        assert bpr.lock_allows_fetch_and_merge is False
        assert bpr.lock_branch is False
        assert bpr.bypass_force_push_allowances == ["@netomi"]
        assert bpr.bypass_pull_request_allowances == ["@netomi"]
        assert bpr.push_restrictions == ["@netomi"]
        assert bpr.require_last_push_approval is False
        assert bpr.required_approving_review_count == 2
        assert bpr.requires_pull_request is True
        assert bpr.requires_code_owner_reviews is False
        assert bpr.requires_commit_signatures is False
        assert bpr.requires_conversation_resolution is False
        assert bpr.requires_linear_history is False
        assert bpr.requires_status_checks is True
        assert bpr.requires_strict_status_checks is False
        assert bpr.restricts_review_dismissals is False
        assert bpr.review_dismissal_allowances == ["@netomi"]
        assert bpr.required_status_checks == ["any:Run CI"]

    async def test_to_provider(self):
        bpr = BranchProtectionRule.from_model_data(self.model_data)

        provider_data = await bpr.to_provider_data(self.org_id, self.provider)

        assert len(provider_data) == 24
        assert provider_data["pattern"] == "main"
        assert provider_data["pushActorIds"] == ["id_netomi"]
        assert provider_data["requiredStatusChecks"] == [
            {"appId": "id_eclipse-eca-validation", "context": "eclipsefdn/eca"},
            {"appId": "any", "context": "Run CI"},
        ]

    async def test_changes_to_provider(self):
        current = BranchProtectionRule.from_model_data(self.model_data)
        other = BranchProtectionRule.from_model_data(self.model_data)

        other.requires_pull_request = False
        other.required_status_checks = ["eclipse-eca-validation:eclipsefdn/eca"]

        changes = current.get_difference_from(other)
        provider_data = await BranchProtectionRule.changes_to_provider(self.org_id, changes, self.provider)

        assert len(provider_data) == 2
        assert provider_data["requiresApprovingReviews"] is True
        assert provider_data["requiredStatusChecks"] == [
            {"appId": "id_eclipse-eca-validation", "context": "eclipsefdn/eca"},
            {"appId": "any", "context": "Run CI"},
        ]

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

        other.requires_pull_request = False
        other.required_status_checks = ["eclipse-eca-validation:eclipsefdn/eca"]

        diff = current.get_difference_from(other)

        assert len(diff) == 2
        assert diff["requires_pull_request"] == Change(other.requires_pull_request, current.requires_pull_request)
        assert diff["required_status_checks"] == Change(other.required_status_checks, current.required_status_checks)
