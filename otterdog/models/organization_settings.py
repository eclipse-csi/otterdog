# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field as dataclass_field
from typing import Any

from jsonbender import bend, S, OptionalS

from otterdog.utils import UNSET, is_unset

from . import ModelObject, ValidationContext, FailureType


@dataclass
class OrganizationSettings(ModelObject):
    name: str
    plan: str = dataclass_field(metadata={"readonly": True})
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
    two_factor_requirement: bool = dataclass_field(metadata={"readonly": True})
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

    def validate(self, context: ValidationContext, parent_object: object) -> None:
        # enabling dependabot implicitly enables the dependency graph,
        # disabling the dependency graph in the configuration will result in inconsistencies after
        # applying the configuration, warn the user about it.
        dependabot_alerts_enabled = self.dependabot_alerts_enabled_for_new_repositories is True
        dependabot_security_updates_enabled = self.dependabot_security_updates_enabled_for_new_repositories is True
        dependency_graph_disabled = self.dependency_graph_enabled_for_new_repositories is False

        if (dependabot_alerts_enabled or dependabot_security_updates_enabled) and dependency_graph_disabled:
            context.add_failure(FailureType.ERROR,
                                f"enabling dependabot_alerts or dependabot_security_updates implicitly"
                                f" enables dependency_graph_enabled_for_new_repositories")

        if dependabot_security_updates_enabled and not dependabot_alerts_enabled:
            context.add_failure(FailureType.ERROR,
                                f"enabling dependabot_security_updates implicitly enables dependabot_alerts")

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "OrganizationSettings":
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]) -> "OrganizationSettings":
        mapping = {k: S(k) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update({"plan": OptionalS("plan", "name", default=UNSET)})
        return cls(**bend(mapping, data))

    def to_provider(self) -> dict[str, Any]:
        data = self.to_model_dict()

        mapping = {}

        for field in self.model_fields():
            if self.is_read_only(field):
                continue

            key = field.name
            value = self.__getattribute__(key)
            if not is_unset(value):
                mapping[key] = S(key)

        return bend(mapping, data)
