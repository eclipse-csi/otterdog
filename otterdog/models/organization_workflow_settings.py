#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from jsonbender import Forall, If, K, S  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.models.workflow_settings import WorkflowSettings
from otterdog.utils import Change, is_set_and_valid, unwrap

if TYPE_CHECKING:
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class OrganizationWorkflowSettings(WorkflowSettings):
    """
    Represents workflow settings defined on organization level.
    """

    enabled_repositories: str
    selected_repositories: list[str]

    @property
    def model_object_name(self) -> str:
        return "org_workflow_settings"

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if self.enabled_repositories == "none":
            if field.name == "enabled_repositories":
                return True
            else:
                return False

        if field.name == "selected_repositories":
            if self.enabled_repositories == "selected":
                return True
            else:
                return False

        return super().include_field_for_diff_computation(field)

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        super().validate(context, parent_object)

        if is_set_and_valid(self.enabled_repositories):
            if self.enabled_repositories not in {"all", "none", "selected"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'enabled_repositories' of value "
                    f"'{self.enabled_repositories}', "
                    f"while only values ('all' | 'none' | 'selected') are allowed.",
                )

            if self.enabled_repositories != "selected" and len(self.selected_repositories) > 0:
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has 'enabled_repositories' set to "
                    f"'{self.enabled_repositories}', "
                    f"but 'selected_repositories' is set to '{self.selected_repositories}', setting will be ignored.",
                )

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        mapping.update(
            {
                "selected_repositories": If(
                    S("selected_repositories") == K(None),
                    K([]),
                    S("selected_repositories") >> Forall(lambda x: x["name"]),
                ),
            }
        )

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        if "selected_repositories" in data:
            mapping.pop("selected_repositories")
            mapping["selected_repository_ids"] = K(await provider.get_repo_ids(org_id, data["selected_repositories"]))

        return mapping

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: OrganizationWorkflowSettings | None,
        current_object: OrganizationWorkflowSettings | None,
        parent_object: ModelObject | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        expected_object = unwrap(expected_object)
        current_object = unwrap(current_object)

        modified_workflow_settings: dict[str, Change[Any]] = expected_object.get_difference_from(current_object)

        # FIXME: needed to add this hack to ensure that enabled_repositories is also present in
        #        the modified data as GitHub has made this property required.
        if "allowed_actions" in modified_workflow_settings:
            enabled_repositories = expected_object.enabled_repositories
            modified_workflow_settings["enabled_repositories"] = Change(enabled_repositories, enabled_repositories)

        if len(modified_workflow_settings) > 0:
            handler(
                LivePatch.of_changes(
                    expected_object,
                    current_object,
                    modified_workflow_settings,
                    parent_object,
                    False,
                    cls.apply_live_patch,
                )
            )

        context.modified_org_workflow_settings = modified_workflow_settings

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[OrganizationWorkflowSettings],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        if patch.patch_type != LivePatchType.CHANGE:
            raise ValueError(f"unexpected patch_type '{patch.patch_type}'")

        github_settings = await cls.changes_to_provider(org_id, unwrap(patch.changes), provider)
        await provider.update_org_workflow_settings(org_id, github_settings)
