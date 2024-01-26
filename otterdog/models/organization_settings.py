#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Any, Iterator, Optional, cast

from jsonbender import F, If, K, OptionalS, S, bend  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    LivePatchType,
    ModelObject,
    PatchContext,
    ValidationContext,
)
from otterdog.providers.github import GitHubProvider
from otterdog.utils import (
    UNSET,
    Change,
    IndentingPrinter,
    is_set_and_present,
    is_set_and_valid,
    is_unset,
    write_patch_object_as_json,
)

from .organization_workflow_settings import OrganizationWorkflowSettings


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
    has_discussions: bool
    discussion_source_repository: Optional[str]
    has_organization_projects: bool
    # setting does not seem to be taken into account as the name might suggest,
    # instead has_organization_projects is used to control whether repo can have projects
    # deprecate and schedule for removal
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
    members_can_create_public_pages: bool
    members_can_change_repo_visibility: bool
    members_can_delete_repositories: bool
    members_can_delete_issues: bool
    members_can_create_teams: bool
    readers_can_create_discussions: bool
    packages_containers_public: bool
    packages_containers_internal: bool
    members_can_change_project_visibility: bool
    security_managers: list[str]

    # nested model fields
    workflows: OrganizationWorkflowSettings = dataclasses.field(metadata={"nested_model": True})

    @property
    def model_object_name(self) -> str:
        return "settings"

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if self.has_discussions is False and field.name == "discussion_source_repository":
            return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        # execute custom validation rules if present
        self.execute_custom_validation_if_present(context, "validate-org-settings.py")

        # enabling dependabot implicitly enables the dependency graph,
        # disabling the dependency graph in the configuration will result in inconsistencies after
        # applying the configuration, warn the user about it.
        dependabot_alerts_enabled = self.dependabot_alerts_enabled_for_new_repositories is True
        dependabot_security_updates_enabled = self.dependabot_security_updates_enabled_for_new_repositories is True
        dependency_graph_disabled = self.dependency_graph_enabled_for_new_repositories is False

        if is_set_and_present(self.description) and len(self.description) > 160:
            context.add_failure(
                FailureType.ERROR,
                "setting 'description' exceeds maximum allowed length of 160 chars.",
            )

        if (dependabot_alerts_enabled or dependabot_security_updates_enabled) and dependency_graph_disabled:
            context.add_failure(
                FailureType.ERROR,
                "enabling 'dependabot_alerts' or 'dependabot_security_updates' implicitly"
                " enables 'dependency_graph_enabled_for_new_repositories'.",
            )

        if dependabot_security_updates_enabled and not dependabot_alerts_enabled:
            context.add_failure(
                FailureType.ERROR,
                "enabling 'dependabot_security_updates' implicitly enables dependabot_alerts.",
            )

        if self.has_discussions is True and not is_set_and_valid(self.discussion_source_repository):
            context.add_failure(
                FailureType.ERROR,
                "enabling 'has_discussions' requires setting a valid repository in 'discussion_source_repository'.",
            )

        if is_set_and_present(self.discussion_source_repository) and "/" not in self.discussion_source_repository:
            context.add_failure(
                FailureType.ERROR,
                "setting 'discussion_source_repository' requires a repository in '<owner>/<repo-name>' format.",
            )

        if is_set_and_valid(self.default_repository_permission):
            if self.default_repository_permission not in {"none", "read", "write", "admin"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"'default_repository_permission' has value '{self.default_repository_permission}', "
                    f"only values ('none' | 'read' | 'write' | 'admin') are allowed.",
                )

        if is_set_and_present(self.workflows):
            self.workflows.validate(context, self)

    def get_model_objects(self) -> Iterator[tuple[ModelObject, ModelObject]]:
        if is_set_and_present(self.workflows):
            yield self.workflows, self
            yield from self.workflows.get_model_objects()

    @classmethod
    def from_model_data(cls, data: dict[str, Any]) -> OrganizationSettings:
        mapping: dict[str, Any] = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update(
            {
                "workflows": If(
                    OptionalS("workflows", default=None) == K(None),
                    K(UNSET),
                    S("workflows") >> F(lambda x: OrganizationWorkflowSettings.from_model_data(x)),
                ),
            }
        )

        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]) -> OrganizationSettings:
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update({"plan": OptionalS("plan", "name", default=UNSET)})
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }
        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> Optional[str]:
        return None

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        write_patch_object_as_json(patch, printer, False)

        if is_set_and_present(self.workflows):
            default_workflow_settings = cast(OrganizationSettings, default_object).workflows

            patch = self.workflows.get_patch_to(default_workflow_settings)
            if len(patch) > 0:
                printer.print("workflows+:")
                self.workflows.to_jsonnet(printer, jsonnet_config, context, False, default_workflow_settings)

        printer.level_down()
        printer.println("},")

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: Optional[ModelObject],
        current_object: Optional[ModelObject],
        parent_object: Optional[ModelObject],
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        assert isinstance(expected_object, OrganizationSettings)
        assert isinstance(current_object, OrganizationSettings)

        modified_settings: dict[str, Change[Any]] = expected_object.get_difference_from(current_object)
        if len(modified_settings) > 0:
            handler(
                LivePatch.of_changes(
                    expected_object, current_object, modified_settings, parent_object, False, cls.apply_live_patch
                )
            )

        context.modified_org_settings = modified_settings

        if is_set_and_valid(expected_object.workflows):
            OrganizationWorkflowSettings.generate_live_patch(
                expected_object.workflows, current_object.workflows, expected_object, context, handler
            )

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch, org_id: str, provider: GitHubProvider) -> None:
        assert patch.patch_type == LivePatchType.CHANGE
        assert patch.changes is not None
        github_settings = await cls.changes_to_provider(org_id, patch.changes, provider)
        await provider.update_org_settings(org_id, github_settings)
