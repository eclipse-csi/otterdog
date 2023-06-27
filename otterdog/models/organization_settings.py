# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Any, Optional

from jsonbender import bend, S, OptionalS  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject, ValidationContext, FailureType
from otterdog.providers.github import Github
from otterdog.utils import UNSET, is_unset, IndentingPrinter, write_patch_object_as_json


@dataclasses.dataclass
class OrganizationSettings(ModelObject):
    """
    Represents settings of a GitHub Organization.
    """

    name: Optional[str]
    plan: str = dataclasses.field(metadata={"read_only": True})
    description: Optional[str]
    email: Optional[str]
    location: Optional[str]
    company: Optional[str]
    billing_email: str
    twitter_username: Optional[str]
    blog: Optional[str]
    has_organization_projects: bool
    has_repository_projects: bool
    default_branch_name: str
    default_repository_permission: str
    two_factor_requirement: bool = dataclasses.field(metadata={"read_only": True})
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
    packages_containers_public: bool
    packages_containers_internal: bool
    organization_projects_enabled: bool
    members_can_change_project_visibility: bool
    default_workflow_permissions: str
    security_managers: list[str]

    @property
    def model_object_name(self) -> str:
        return "settings"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        # enabling dependabot implicitly enables the dependency graph,
        # disabling the dependency graph in the configuration will result in inconsistencies after
        # applying the configuration, warn the user about it.
        dependabot_alerts_enabled = self.dependabot_alerts_enabled_for_new_repositories is True
        dependabot_security_updates_enabled = self.dependabot_security_updates_enabled_for_new_repositories is True
        dependency_graph_disabled = self.dependency_graph_enabled_for_new_repositories is False

        if (dependabot_alerts_enabled or dependabot_security_updates_enabled) and dependency_graph_disabled:
            context.add_failure(
                FailureType.ERROR,
                "enabling dependabot_alerts or dependabot_security_updates implicitly"
                " enables dependency_graph_enabled_for_new_repositories",
            )

        if dependabot_security_updates_enabled and not dependabot_alerts_enabled:
            context.add_failure(
                FailureType.ERROR,
                "enabling dependabot_security_updates implicitly enables dependabot_alerts",
            )

    @classmethod
    def from_model_data(cls, data: dict[str, Any]) -> OrganizationSettings:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]) -> OrganizationSettings:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update({"plan": OptionalS("plan", "name", default=UNSET)})
        return cls(**bend(mapping, data))

    @classmethod
    def _to_provider_data(cls, org_id: str, data: dict[str, Any], provider: Github) -> dict[str, Any]:
        mapping = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }
        return bend(mapping, data)

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        write_patch_object_as_json(patch, printer, False)
        printer.level_down()
        printer.println("},")
