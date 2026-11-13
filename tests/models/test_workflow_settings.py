#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses

import pytest
from pretend import stub

from otterdog.models import CostPolicy, FailureType
from otterdog.models.organization_workflow_settings import OrganizationWorkflowSettings
from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
from otterdog.models.workflow_settings import WorkflowSettings
from otterdog.utils import UNSET, Change, is_unset


# Subclass to test abstract WorkflowSettings logic.
class TestWorkflowSettings(WorkflowSettings): ...


@pytest.fixture
def workflow_settings():
    """Return WorkflowSettings child instance for testing."""

    return TestWorkflowSettings(
        allowed_actions="all",
        allow_github_owned_actions=True,
        allow_verified_creator_actions=True,
        allow_action_patterns=[],
        default_workflow_permissions="read",
        actions_can_approve_pull_request_reviews=True,
        fork_pr_approval_policy="first_time_contributors",
        max_cache_size_gb=10,
        sha_pinning_required=False,
    )


class TestWorkflowSettingsValidation:
    @pytest.fixture
    def mock_validation_ctx(self):
        """Return mock validation context object, needed for error cache."""
        ctx = stub(validation_failures=[])
        ctx.add_failure = lambda e, m: ctx.validation_failures.append((e, m))
        return ctx

    @pytest.fixture
    def mock_parent(self):
        """Return mock parent object, needed for model header."""
        return stub(
            get_model_header=lambda: "Organization 'test-org'",
        )

    @pytest.mark.parametrize(
        "approval_policy",
        ["first_time_contributors_new_to_github", "first_time_contributors", "all_external_contributors", UNSET, None],
    )
    def test_valid_fork_pr_approval_policies(
        self, mock_validation_ctx, mock_parent, workflow_settings, approval_policy
    ):
        workflow_settings.fork_pr_approval_policy = approval_policy
        workflow_settings.validate(mock_validation_ctx, mock_parent)

        assert not mock_validation_ctx.validation_failures

    def test_invalid_fork_pr_approval_policy(self, mock_validation_ctx, mock_parent, workflow_settings):
        workflow_settings.fork_pr_approval_policy = "invalid"
        workflow_settings.validate(mock_validation_ctx, mock_parent)

        assert mock_validation_ctx.validation_failures
        assert "fork_pr_approval_policy" in mock_validation_ctx.validation_failures[0][1]


class TestWorkflowSettingsMapping:
    def test_mapping_from_provider_fork_pr_approval_policy(self):
        data = {}
        mapping = TestWorkflowSettings.get_mapping_from_provider("test-id", data)
        assert "fork_pr_approval_policy" in mapping

    async def test_mapping_to_provider_fork_pr_approval_policy(self):
        data = {
            "fork_pr_approval_policy": "first_time_contributors",
        }
        provider = stub()

        mapping = await TestWorkflowSettings.get_mapping_to_provider("test-id", data, provider)
        assert "fork_pr_approval_policy" not in mapping
        assert "approval_policy" in mapping

        data = {}
        mapping = await TestWorkflowSettings.get_mapping_to_provider("test-id", data, provider)
        assert "approval_policy" not in mapping

    def test_cache_size_changes_are_cost_related(self, workflow_settings):
        assert workflow_settings.changes_are_cost_related({"max_cache_size_gb": Change(10, 50)})

    def test_default_cache_size_is_not_cost_related(self, workflow_settings):
        assert not workflow_settings.is_cost_related(CostPolicy())

    def test_unset_cache_size_is_not_cost_related(self, workflow_settings):
        workflow_settings.max_cache_size_gb = UNSET
        assert not workflow_settings.is_cost_related(CostPolicy())

    def test_cache_size_above_default_is_cost_related(self, workflow_settings):
        workflow_settings.max_cache_size_gb = 50
        assert workflow_settings.is_cost_related(CostPolicy())

    def test_cache_size_uses_configured_free_limit(self, workflow_settings):
        workflow_settings.max_cache_size_gb = 50
        assert not workflow_settings.is_cost_related(CostPolicy(free_max_cache_size_gb=50))
        assert workflow_settings.is_cost_related(CostPolicy(free_max_cache_size_gb=5))


class TestWorkflowSettingsShaPinning:
    def test_mapping_from_provider_reads_sha_pinning_required(self):
        settings = TestWorkflowSettings.from_provider_data("test-id", {"sha_pinning_required": True})

        assert settings.sha_pinning_required is True

    def test_mapping_from_provider_without_sha_pinning_required(self):
        # e.g. a GitHub Enterprise Server that does not report the setting, it is then not compared
        settings = TestWorkflowSettings.from_provider_data("test-id", {})

        assert is_unset(settings.sha_pinning_required)

    async def test_mapping_to_provider_sends_sha_pinning_required(self):
        data = await TestWorkflowSettings.dict_to_provider_data("test-id", {"sha_pinning_required": True}, stub())

        assert data == {"sha_pinning_required": True}

    @pytest.mark.parametrize("allowed_actions", ["all", "local_only", "selected"])
    def test_change_is_detected_whatever_the_allowed_actions(self, workflow_settings, allowed_actions):
        workflow_settings.allowed_actions = allowed_actions
        expected = dataclasses.replace(workflow_settings, sha_pinning_required=True)

        diff = expected.get_difference_from(workflow_settings)

        assert diff is not None
        changed_keys = {key for key, value in diff.to_value.items() if diff.from_value[key] != value}
        assert changed_keys == {"sha_pinning_required"}
        assert diff.from_value["sha_pinning_required"] is False
        assert diff.to_value["sha_pinning_required"] is True

    def test_org_setting_is_not_compared_when_actions_are_disabled(self):
        current = OrganizationWorkflowSettings.from_model_data(
            {"enabled_repositories": "none", "sha_pinning_required": False}
        )
        expected = OrganizationWorkflowSettings.from_model_data(
            {"enabled_repositories": "none", "sha_pinning_required": True}
        )

        assert expected.get_difference_from(current) is None

    def test_repo_setting_is_not_compared_when_actions_are_disabled(self):
        current = RepositoryWorkflowSettings.from_model_data({"enabled": False, "sha_pinning_required": False})
        expected = RepositoryWorkflowSettings.from_model_data({"enabled": False, "sha_pinning_required": True})

        assert expected.get_difference_from(current) is None


class TestRepositoryWorkflowSettingsShaPinning:
    @pytest.fixture
    def repo(self):
        return stub(
            name="my-repo",
            code_scanning_default_setup_enabled=False,
            get_model_header=lambda: 'repository[name="my-repo"]',
        )

    @staticmethod
    def org_settings(sha_pinning_required: bool) -> OrganizationWorkflowSettings:
        return OrganizationWorkflowSettings.from_model_data(
            {"enabled_repositories": "all", "allowed_actions": "all", "sha_pinning_required": sha_pinning_required}
        )

    @staticmethod
    def repo_settings(sha_pinning_required: bool) -> RepositoryWorkflowSettings:
        return RepositoryWorkflowSettings.from_model_data(
            {
                "enabled": True,
                "allowed_actions": "all",
                "allow_action_patterns": [],
                "sha_pinning_required": sha_pinning_required,
            }
        )

    @staticmethod
    def validation_context(org_settings: OrganizationWorkflowSettings):
        ctx = stub(validation_failures=[], root_object=stub(settings=stub(workflows=org_settings)))
        ctx.add_failure = lambda e, m: ctx.validation_failures.append((e, m))
        return ctx

    @pytest.mark.parametrize("repo_value", [False, True])
    def test_repo_setting_is_ignored_when_the_org_requires_sha_pinning(self, repo, repo_value):
        settings = self.repo_settings(repo_value)

        coerced = settings.coerce_from_org_settings(repo, self.org_settings(True))

        assert is_unset(coerced.sha_pinning_required)
        assert settings.sha_pinning_required is repo_value

    @pytest.mark.parametrize("repo_value", [False, True])
    def test_repo_setting_is_kept_when_the_org_does_not_require_sha_pinning(self, repo, repo_value):
        coerced = self.repo_settings(repo_value).coerce_from_org_settings(repo, self.org_settings(False))

        assert coerced.sha_pinning_required is repo_value

    def test_validation_reports_a_repo_setting_ignored_due_to_the_org(self, repo):
        ctx = self.validation_context(self.org_settings(True))

        self.repo_settings(False).validate(ctx, repo)

        assert len(ctx.validation_failures) == 1
        failure_type, message = ctx.validation_failures[0]
        assert failure_type == FailureType.INFO
        assert "'sha_pinning_required' disabled" in message

    @pytest.mark.parametrize(("org_value", "repo_value"), [(True, True), (False, True), (False, False)])
    def test_validation_accepts_consistent_settings(self, repo, org_value, repo_value):
        ctx = self.validation_context(self.org_settings(org_value))

        self.repo_settings(repo_value).validate(ctx, repo)

        assert ctx.validation_failures == []
