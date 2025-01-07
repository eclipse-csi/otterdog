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
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.utils import UNSET, Change

from . import ModelTest


class OrganizationSettingsTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return OrganizationSettings.from_model_data(data["settings"])

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-org-settings.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-org-settings.json")

    def test_load_from_model(self):
        settings = OrganizationSettings.from_model_data(self.model_data)

        assert settings.name is None
        assert settings.plan == "free"
        assert settings.description is None
        assert settings.email is None
        assert settings.location is None
        assert settings.company is None
        assert settings.billing_email == "thomas.neidhart@eclipse-foundation.org"
        assert settings.twitter_username is None
        assert settings.blog is None
        assert settings.has_organization_projects is True
        assert settings.default_branch_name == "main"
        assert settings.default_repository_permission == "read"
        assert settings.two_factor_requirement is False
        assert settings.web_commit_signoff_required is False
        assert settings.members_can_create_private_repositories is False
        assert settings.members_can_create_public_repositories is True
        assert settings.members_can_fork_private_repositories is True
        assert settings.members_can_create_public_pages is True
        assert settings.members_can_change_repo_visibility is False
        assert settings.members_can_delete_repositories is True
        assert settings.members_can_delete_issues is False
        assert settings.members_can_create_teams is True
        assert settings.readers_can_create_discussions is False
        assert settings.packages_containers_public is False
        assert settings.packages_containers_internal is False
        assert settings.members_can_change_project_visibility is False

    def test_load_from_provider(self):
        settings = OrganizationSettings.from_provider_data(self.org_id, self.provider_data)

        assert settings.name is None
        assert settings.plan == "free"
        assert settings.description is None
        assert settings.email is None
        assert settings.location is None
        assert settings.company is None
        assert settings.billing_email == "thomas.neidhart@eclipse-foundation.org"
        assert settings.twitter_username is None
        assert settings.blog is None
        assert settings.has_organization_projects is True
        assert settings.default_branch_name == "main"
        assert settings.two_factor_requirement is False
        assert settings.web_commit_signoff_required is False
        assert settings.members_can_create_private_repositories is False
        assert settings.members_can_create_public_repositories is True
        assert settings.members_can_fork_private_repositories is True
        assert settings.members_can_create_public_pages is True
        assert settings.members_can_change_repo_visibility is False
        assert settings.members_can_delete_repositories is True
        assert settings.members_can_delete_issues is False
        assert settings.members_can_create_teams is True
        assert settings.readers_can_create_discussions is False
        assert settings.packages_containers_public is False
        assert settings.packages_containers_internal is False
        assert settings.members_can_change_project_visibility is False

    async def test_to_provider(self):
        settings = OrganizationSettings.from_model_data(self.model_data)

        settings.description = UNSET

        provider_data = await settings.to_provider_data(self.org_id, self.provider)

        assert len(provider_data) == 23
        assert provider_data["billing_email"] == settings.billing_email

    async def test_changes_to_provider(self):
        current = OrganizationSettings.from_model_data(self.model_data)
        other = OrganizationSettings.from_model_data(self.model_data)

        other.billing_email = "mikael_barbero@eclipse-foundation.org"
        other.default_repository_permission = "none"

        changes = current.get_difference_from(other)
        provider_data = await OrganizationSettings.changes_to_provider(self.org_id, changes, self.provider)

        assert len(provider_data) == 2
        assert provider_data["billing_email"] == current.billing_email
        assert provider_data["default_repository_permission"] == current.default_repository_permission

    def test_patch(self):
        current = OrganizationSettings.from_model_data(self.model_data)

        default = OrganizationSettings.from_model_data(self.model_data)

        default.billing_email = None
        default.web_commit_signoff_required = True

        patch = current.get_patch_to(default)

        assert len(patch) == 2
        assert patch["billing_email"] == current.billing_email
        assert patch["web_commit_signoff_required"] is current.web_commit_signoff_required

    def test_difference(self):
        current = OrganizationSettings.from_model_data(self.model_data)
        other = OrganizationSettings.from_model_data(self.model_data)

        other.billing_email = "mikael_barbero@eclipse-foundation.org"
        other.default_repository_permission = "none"

        diff = current.get_difference_from(other)

        assert len(diff) == 2
        assert diff["billing_email"] == Change(other.billing_email, current.billing_email)
        assert diff["default_repository_permission"] == Change(
            other.default_repository_permission, current.default_repository_permission
        )
