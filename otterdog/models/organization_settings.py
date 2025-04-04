#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
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
from otterdog.providers.github import is_org_settings_key_retrieved_via_web_ui
from otterdog.utils import (
    UNSET,
    Change,
    IndentingPrinter,
    associate_by_key,
    is_set_and_present,
    is_set_and_valid,
    unwrap,
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
    workflows: OrganizationWorkflowSettings = dataclasses.field(metadata={"embedded_model": True})
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
                    f"while only values ('none' | 'read' | 'write' | 'admin') are allowed.",
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

        if "workflows" in data:
            workflow_data = data["workflows"]
            mapping["workflows"] = K(OrganizationWorkflowSettings.from_provider_data(org_id, workflow_data))
        else:
            mapping["workflows"] = K(UNSET)

        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return None

    def changes_require_web_ui(self, changes: dict[str, Change]) -> bool:
        from otterdog.providers.github import is_org_settings_key_retrieved_via_web_ui

        return any(is_org_settings_key_retrieved_via_web_ui(key) for key in changes)

    def unset_settings_requiring_web_ui(self) -> None:
        for key in self.keys():
            if is_org_settings_key_retrieved_via_web_ui(key):
                self.__setattr__(key, UNSET)

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        default_org_settings = cast(OrganizationSettings, default_object)

        patch = self.get_patch_to(default_object)

        if "workflows" in patch:
            patch.pop("workflows")

        write_patch_object_as_json(patch, printer, False)

        # print custom properties
        if is_set_and_present(self.custom_properties) and len(self.custom_properties) > 0:
            properties_by_name = associate_by_key(self.custom_properties, lambda x: x.name)
            default_properties_by_name = associate_by_key(default_org_settings.custom_properties, lambda x: x.name)

            for default_property_name in set(default_properties_by_name):
                if default_property_name in properties_by_name:
                    properties_by_name.pop(default_property_name)

            default_org_custom_property = CustomProperty.from_model_data(config.default_org_custom_property_config)

            if len(properties_by_name) > 0:
                printer.println("custom_properties+: [")
                printer.level_up()

                for _, custom_property in properties_by_name.items():
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
        expected_object: OrganizationSettings | None,
        current_object: OrganizationSettings | None,
        parent_object: ModelObject | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        expected_object = unwrap(expected_object)
        current_object = unwrap(current_object)

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

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[OrganizationSettings],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        if patch.patch_type != LivePatchType.CHANGE:
            raise ValueError(f"unexpected patch_type '{patch.patch_type}'")

        github_settings = await cls.changes_to_provider(org_id, unwrap(patch.changes), provider)

        if "workflows" in github_settings:
            github_settings.pop("workflows")
            update_workflows = True
        else:
            update_workflows = False

        await provider.update_org_settings(
            org_id,
            github_settings,
        )

        if update_workflows is True:
            data = unwrap(patch.expected_object).workflows.to_model_dict(for_diff=True)
            github_data = await OrganizationWorkflowSettings.dict_to_provider_data(org_id, data, provider)

            await provider.update_org_workflow_settings(org_id, github_data)
