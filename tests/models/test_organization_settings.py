#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import jq

from otterdog.models.organization_settings import OrganizationSettings
from otterdog.utils import Change, UNSET

from . import ModelTest


class OrganizationSettingsTest(ModelTest):
    @property
    def model_data(self):
        return self.load_json_resource("otterdog-org-settings.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-org-settings.json")

    def test_load_from_model(self):
        settings = OrganizationSettings.from_model(self.model_data)

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
        assert settings.has_repository_projects is True
        assert settings.default_branch_name == "main"
        assert settings.default_repository_permission == "read"
        assert settings.two_factor_requirement is False
        assert settings.web_commit_signoff_required is False
        assert settings.dependabot_alerts_enabled_for_new_repositories is True
        assert settings.dependabot_security_updates_enabled_for_new_repositories is True
        assert settings.dependency_graph_enabled_for_new_repositories is True
        assert settings.members_can_create_private_repositories is False
        assert settings.members_can_create_public_repositories is True
        assert settings.members_can_fork_private_repositories is True
        assert settings.members_can_create_pages is True
        assert settings.members_can_create_public_pages is True
        assert settings.members_can_change_repo_visibility is False
        assert settings.members_can_delete_repositories is True
        assert settings.members_can_delete_issues is False
        assert settings.members_can_create_teams is True
        assert settings.readers_can_create_discussions is False
        assert settings.team_discussions_allowed is True
        assert settings.packages_containers_public is False
        assert settings.packages_containers_internal is False
        assert settings.organization_organization_projects_enabled is True
        assert settings.organization_members_can_change_project_visibility is False

    def test_load_from_provider(self):
        settings = OrganizationSettings.from_provider(self.provider_data)

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
        assert settings.has_repository_projects is True
        assert settings.default_branch_name == "main"
        assert settings.default_repository_permission == "read"
        assert settings.two_factor_requirement is False
        assert settings.web_commit_signoff_required is False
        assert settings.dependabot_alerts_enabled_for_new_repositories is True
        assert settings.dependabot_security_updates_enabled_for_new_repositories is True
        assert settings.dependency_graph_enabled_for_new_repositories is True
        assert settings.members_can_create_private_repositories is False
        assert settings.members_can_create_public_repositories is True
        assert settings.members_can_fork_private_repositories is True
        assert settings.members_can_create_pages is True
        assert settings.members_can_create_public_pages is True
        assert settings.members_can_change_repo_visibility is False
        assert settings.members_can_delete_repositories is True
        assert settings.members_can_delete_issues is False
        assert settings.members_can_create_teams is True
        assert settings.readers_can_create_discussions is False
        assert settings.team_discussions_allowed is True
        assert settings.packages_containers_public is False
        assert settings.packages_containers_internal is False
        assert settings.organization_organization_projects_enabled is True
        assert settings.organization_members_can_change_project_visibility is False

    def test_to_provider(self):
        settings = OrganizationSettings.from_model(self.model_data)

        settings.description = UNSET

        provider_data = settings.to_provider()

        assert len(provider_data) == 30
        assert provider_data["billing_email"] == settings.billing_email

    def test_changes_to_provider(self):
        current = OrganizationSettings.from_model(self.model_data)
        other = OrganizationSettings.from_model(self.model_data)

        other.billing_email = "mikael_barbero@eclipse-foundation.org"
        other.default_repository_permission = "none"

        changes = current.get_difference_from(other)
        provider_data = current.changes_to_provider(changes)

        assert len(provider_data) == 2
        assert provider_data["billing_email"] == current.billing_email
        assert provider_data["default_repository_permission"] == current.default_repository_permission

    def test_patch(self):
        current = OrganizationSettings.from_model(self.model_data)

        default = OrganizationSettings.from_model(self.model_data)

        default.billing_email = None
        default.web_commit_signoff_required = True

        patch = current.get_patch_to(default)

        assert len(patch) == 2
        assert patch["billing_email"] == current.billing_email
        assert patch["web_commit_signoff_required"] is current.web_commit_signoff_required

    def test_difference(self):
        current = OrganizationSettings.from_model(self.model_data)
        other = OrganizationSettings.from_model(self.model_data)

        other.billing_email = "mikael_barbero@eclipse-foundation.org"
        other.default_repository_permission = "none"

        diff = current.get_difference_from(other)

        assert len(diff) == 2
        assert diff["billing_email"] == Change(other.billing_email, current.billing_email)
        assert diff["default_repository_permission"] == Change(other.default_repository_permission,
                                                               current.default_repository_permission)
