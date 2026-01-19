#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest
from pretend import stub

from otterdog.models.workflow_settings import WorkflowSettings
from otterdog.utils import UNSET


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

    @pytest.mark.asyncio
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
