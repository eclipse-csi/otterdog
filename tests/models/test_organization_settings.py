#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.models.organization_settings import OrganizationSettings


def test_load_org_settings_from_model(otterdog_org_settings_data):
    settings = OrganizationSettings.from_model(otterdog_org_settings_data)

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


def test_load_org_settings_from_provider(github_org_settings_data):
    settings = OrganizationSettings.from_provider(github_org_settings_data)

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
