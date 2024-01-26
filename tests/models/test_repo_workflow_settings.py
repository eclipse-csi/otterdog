#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
from otterdog.utils import Change

from . import ModelTest


class RepositoryWorkflowSettingsTest(ModelTest):
    @property
    def model_data(self):
        return self.load_json_resource("otterdog-repo-workflow-settings.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-repo-workflow-settings.json")

    def test_load_from_model(self):
        workflow_settings = RepositoryWorkflowSettings.from_model_data(self.model_data)

        assert workflow_settings.enabled is True
        assert workflow_settings.allowed_actions == "all"
        assert workflow_settings.allow_github_owned_actions is True
        assert workflow_settings.allow_verified_creator_actions is True
        assert len(workflow_settings.allow_action_patterns) == 0
        assert workflow_settings.default_workflow_permissions == "read"
        assert workflow_settings.actions_can_approve_pull_request_reviews is True

    def test_load_from_provider(self):
        workflow_settings = RepositoryWorkflowSettings.from_provider_data(self.org_id, self.provider_data)

        assert workflow_settings.enabled is True
        assert workflow_settings.allowed_actions == "all"
        assert workflow_settings.allow_github_owned_actions is True
        assert workflow_settings.allow_verified_creator_actions is True
        assert len(workflow_settings.allow_action_patterns) == 0
        assert workflow_settings.default_workflow_permissions == "read"
        assert workflow_settings.actions_can_approve_pull_request_reviews is True

    async def test_to_provider(self):
        workflow_settings = RepositoryWorkflowSettings.from_model_data(self.model_data)
        provider_data = await workflow_settings.to_provider_data(self.org_id, self.provider)

        assert len(provider_data) == 7
        assert provider_data["allowed_actions"] == "all"
        assert provider_data["enabled"] is True
        assert provider_data["github_owned_allowed"] is True
        assert provider_data["verified_allowed"] is True
        assert provider_data["patterns_allowed"] == []
        assert provider_data["can_approve_pull_request_reviews"] is True

    async def test_changes_to_provider(self):
        current = RepositoryWorkflowSettings.from_model_data(self.model_data)
        other = RepositoryWorkflowSettings.from_model_data(self.model_data)

        other.enabled = False

        changes = current.get_difference_from(other)
        provider_data = await RepositoryWorkflowSettings.changes_to_provider(self.org_id, changes, self.provider)

        assert len(provider_data) == 1
        assert provider_data["enabled"] is True

    def test_patch(self):
        current = RepositoryWorkflowSettings.from_model_data(self.model_data)
        default = RepositoryWorkflowSettings.from_model_data(self.model_data)

        current.allowed_actions = ["mytest/actions@*"]

        patch = current.get_patch_to(default)

        assert len(patch) == 1
        assert patch["allowed_actions"] == current.allowed_actions

    def test_difference(self):
        current = RepositoryWorkflowSettings.from_model_data(self.model_data)
        other = RepositoryWorkflowSettings.from_model_data(self.model_data)

        other.enabled = False

        diff = current.get_difference_from(other)

        assert len(diff) == 1
        assert diff["enabled"] == Change(other.enabled, current.enabled)
