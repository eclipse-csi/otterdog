# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field
from typing import Any

from jsonbender import bend, S, OptionalS, K

from . import ModelObject, UNSET


@dataclass
class OrganizationSettings(ModelObject):
    name: str
    plan: str = field(metadata={"readonly": True})
    description: str
    email: str
    location: str
    company: str
    billing_email: str
    twitter_username: str
    blog: str
    has_organization_projects: bool
    has_repository_projects: bool
    default_branch_name: str
    default_repository_permission: str
    two_factor_requirement: bool = field(metadata={"readonly": True})
    web_commit_signoff_required: bool
    dependabot_alerts_enabled_for_new_repositories: bool
    dependabot_security_updates_enabled_for_new_repositories: bool
    dependency_graph_enabled_for_new_repositories: bool
    members_can_create_private_repositories: bool
    members_can_create_public_repositories: bool
    members_can_fork_private_repositories: bool
    members_can_create_pages: bool
    members_can_create_public_pages: bool
    members_can_change_repo_visibility: bool
    members_can_delete_repositories: bool
    members_can_delete_issues: bool
    members_can_create_teams: bool
    readers_can_create_discussions: bool
    team_discussions_allowed: bool
    packages_containers_public: bool
    packages_containers_internal: bool
    organization_organization_projects_enabled: bool
    organization_members_can_change_project_visibility: bool

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "OrganizationSettings":
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]) -> "OrganizationSettings":
        mapping = {k: S(k) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update({"plan": OptionalS("plan", "name", default=UNSET)})
        return cls(**bend(mapping, data))
