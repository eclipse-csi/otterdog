#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, cast

from jsonbender import F, Forall, If, K, OptionalS, S  # type: ignore

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
from otterdog.utils import (
    UNSET,
    Change,
    IndentingPrinter,
    is_set_and_present,
    is_set_and_valid,
    write_patch_object_as_json,
)

from .custom_property import CustomProperty
from .organization_workflow_settings import OrganizationWorkflowSettings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class OrganizationSettings(ModelObject):
    """
    Represents settings of a GitHub Organization.
    """

    name: str | None
    plan: str = dataclasses.field(metadata={"read_only": True})
    description: str | None
    email: str | None
    location: str | None
    company: str | None
    billing_email: str
    twitter_username: str | None
    blog: str | None
    has_discussions: bool
    discussion_source_repository: str | None
    has_organization_projects: bool
    default_branch_name: str
    default_repository_permission: str
    two_factor_requirement: bool = dataclasses.field(metadata={"read_only": True})
    web_commit_signoff_required: bool
    default_code_security_configurations_disabled: bool
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
    custom_properties: list[CustomProperty] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)

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

        if is_set_and_present(self.description) and len(self.description) > 160:
            context.add_failure(
                FailureType.ERROR,
                "setting 'description' exceeds maximum allowed length of 160 chars.",
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

        if is_set_and_present(self.custom_properties):
            for custom_property in self.custom_properties:
                custom_property.validate(context, self)

        if is_set_and_present(self.workflows):
            self.workflows.validate(context, self)

    def get_model_objects(self) -> Iterator[tuple[ModelObject, ModelObject]]:
        if is_set_and_present(self.custom_properties):
            for custom_property in self.custom_properties:
                yield custom_property, self
                yield from custom_property.get_model_objects()

        if is_set_and_present(self.workflows):
            yield self.workflows, self
            yield from self.workflows.get_model_objects()

    @classmethod
    def get_mapping_from_model(cls) -> dict[str, Any]:
        mapping = super().get_mapping_from_model()

        mapping.update(
            {
                "custom_properties": OptionalS("custom_properties", default=[])
                >> Forall(lambda x: CustomProperty.from_model_data(x)),
                "workflows": If(
                    OptionalS("workflows", default=None) == K(None),
                    K(UNSET),
                    S("workflows") >> F(lambda x: OrganizationWorkflowSettings.from_model_data(x)),
                ),
            }
        )

        return mapping

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)
        mapping["plan"] = OptionalS("plan", "name", default=UNSET)
        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return None

    def changes_require_web_ui(self, changes: dict[str, Change]) -> bool:
        from otterdog.providers.github import is_org_settings_key_retrieved_via_web_ui

        return any(is_org_settings_key_retrieved_via_web_ui(key) for key in changes)

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        write_patch_object_as_json(patch, printer, False)

        # print custom properties
        if is_set_and_present(self.custom_properties) and len(self.custom_properties) > 0:
            default_org_custom_property = CustomProperty.from_model_data(config.default_org_custom_property_config)

            if len(self.custom_properties) > 0:
                printer.println("custom_properties+: [")
                printer.level_up()

                for custom_property in self.custom_properties:
                    custom_property.to_jsonnet(printer, config, context, False, default_org_custom_property)

                printer.level_down()
                printer.println("],")

        if is_set_and_present(self.workflows):
            default_workflow_settings = cast(OrganizationSettings, default_object).workflows

            patch = self.workflows.get_patch_to(default_workflow_settings)
            if len(patch) > 0:
                printer.print("workflows+:")
                self.workflows.to_jsonnet(printer, config, context, False, default_workflow_settings)

        printer.level_down()
        printer.println("},")

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: ModelObject | None,
        current_object: ModelObject | None,
        parent_object: ModelObject | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        assert isinstance(expected_object, OrganizationSettings)
        assert isinstance(current_object, OrganizationSettings)

        modified_settings: dict[str, Change[Any]] = expected_object.get_difference_from(current_object)

        # this setting is only intended to disable any existing default configuration, it can not be enabled per se
        if "default_code_security_configurations_disabled" in modified_settings:
            change: Change[bool] = cast(
                Change[bool], modified_settings.get("default_code_security_configurations_disabled")
            )
            if change.from_value is True and change.to_value is False:
                modified_settings.pop("default_code_security_configurations_disabled")

        if len(modified_settings) > 0:
            handler(
                LivePatch.of_changes(
                    expected_object, current_object, modified_settings, parent_object, False, cls.apply_live_patch
                )
            )

        context.modified_org_settings = modified_settings

        if is_set_and_valid(expected_object.custom_properties):
            CustomProperty.generate_live_patch_of_list(
                expected_object.custom_properties,
                current_object.custom_properties,
                expected_object,
                context,
                handler,
            )

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
