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

from jsonbender import S  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.workflow_settings import WorkflowSettings
from otterdog.utils import UNSET, Change, expect_type, is_set_and_valid, is_unset, unwrap

if TYPE_CHECKING:
    from otterdog.models.organization_workflow_settings import OrganizationWorkflowSettings
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class RepositoryWorkflowSettings(WorkflowSettings):
    """
    Represents workflow settings defined on repository level.
    """

    enabled: bool

    @property
    def model_object_name(self) -> str:
        return "repo_workflow_settings"

    def coerce_from_org_settings(
        self, parent_object: ModelObject | None, org_workflow_settings: OrganizationWorkflowSettings
    ) -> RepositoryWorkflowSettings:
        copy = dataclasses.replace(self)

        if org_workflow_settings.enabled_repositories == "none":
            copy.enabled = UNSET  # type: ignore

        from otterdog.models.repository import Repository

        repository_name = cast(Repository, parent_object).name

        if (
            org_workflow_settings.enabled_repositories == "selected"
            and repository_name not in org_workflow_settings.selected_repositories
        ):
            copy.enabled = UNSET  # type: ignore

        if org_workflow_settings.are_actions_more_restricted(self.allowed_actions):
            copy.allowed_actions = UNSET  # type: ignore
            for prop in self._selected_action_properties:
                copy.__setattr__(prop, UNSET)

        if org_workflow_settings.default_workflow_permissions == "read":
            copy.default_workflow_permissions = UNSET  # type: ignore

        if org_workflow_settings.actions_can_approve_pull_request_reviews is False:
            copy.actions_can_approve_pull_request_reviews = UNSET  # type: ignore

        return copy

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        super().validate(context, parent_object)

        if is_set_and_valid(self.enabled) and self.enabled is True:
            from .github_organization import GitHubOrganization

            org_workflow_settings = cast(GitHubOrganization, context.root_object).settings.workflows

            if org_workflow_settings.enabled_repositories == "none" and self.enabled is True:
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has enabled workflows, "
                    f"while on organization level it is disabled for all repositories, setting will be ignored.",
                )

            from otterdog.models.repository import Repository

            repository_name = cast(Repository, parent_object).name

            if (
                org_workflow_settings.enabled_repositories == "selected"
                and repository_name not in org_workflow_settings.selected_repositories
                and self.enabled is True
            ):
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has enabled workflows, "
                    f"while on organization level it is only enabled for selected repositories, "
                    f"setting will be ignored.",
                )

            if (
                org_workflow_settings.default_workflow_permissions == "read"
                and self.default_workflow_permissions == "write"
            ):
                context.add_failure(
                    FailureType.INFO,
                    f"{self.get_model_header(parent_object)} has 'default_workflow_permissions' of value "
                    f"'{self.default_workflow_permissions}', "
                    f"while on organization level it is restricted to "
                    f"'{org_workflow_settings.default_workflow_permissions}', setting will be ignored.",
                )

            if (
                org_workflow_settings.actions_can_approve_pull_request_reviews is False
                and self.actions_can_approve_pull_request_reviews is True
            ):
                context.add_failure(
                    FailureType.INFO,
                    f"{self.get_model_header(parent_object)} has 'actions_can_approve_pull_request_reviews' enabled, "
                    f"while on organization level it is disabled, setting will be ignored.",
                )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if is_unset(self.enabled):
            return False

        if self.enabled is False:
            if field.name == "enabled":
                return True
            else:
                return False

        return super().include_field_for_diff_computation(field)

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        if "enabled" in data and data["enabled"] is False:
            return {"enabled": S("enabled")}
        else:
            return await super().get_mapping_to_provider(org_id, data, provider)

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: RepositoryWorkflowSettings | None,
        current_object: RepositoryWorkflowSettings | None,
        parent_object: ModelObject | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        expected_object = unwrap(expected_object)

        expected_org_settings = cast(OrganizationSettings, context.expected_org_settings)
        coerced_object = expected_object.coerce_from_org_settings(parent_object, expected_org_settings.workflows)

        if current_object is None:
            handler(LivePatch.of_addition(coerced_object, parent_object, coerced_object.apply_live_patch))
            return

        modified_workflow_settings: dict[str, Change[Any]] = coerced_object.get_difference_from(current_object)

        # FIXME: needed to add this hack to ensure that enabled is also present in
        #        the modified data as GitHub has made this property required.
        if len(modified_workflow_settings) > 0:
            if coerced_object.enabled is True and expected_org_settings.workflows.allowed_actions == "local_only":
                modified_workflow_settings["allowed_actions"] = Change(current_object.allowed_actions, "local_only")

            if "allowed_actions" in modified_workflow_settings:
                modified_workflow_settings["enabled"] = Change(current_object.enabled, coerced_object.enabled)

        if "actions_can_approve_pull_request_reviews" in context.modified_org_workflow_settings:
            change = context.modified_org_workflow_settings["actions_can_approve_pull_request_reviews"]
            if change.to_value is True:
                actions_can_approve_pull_request_reviews = cast(
                    RepositoryWorkflowSettings, coerced_object
                ).actions_can_approve_pull_request_reviews
                if actions_can_approve_pull_request_reviews is False:
                    modified_workflow_settings["actions_can_approve_pull_request_reviews"] = Change(
                        actions_can_approve_pull_request_reviews, actions_can_approve_pull_request_reviews
                    )

        if len(modified_workflow_settings) > 0:
            handler(
                LivePatch.of_changes(
                    coerced_object,
                    current_object,
                    modified_workflow_settings,
                    parent_object,
                    False,
                    cls.apply_live_patch,
                )
            )

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[RepositoryWorkflowSettings],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        from .repository import Repository

        repository = expect_type(patch.parent_object, Repository)

        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.update_repo_workflow_settings(
                    org_id,
                    repository.name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.CHANGE:
                github_settings = await cls.changes_to_provider(org_id, unwrap(patch.changes), provider)
                await provider.update_repo_workflow_settings(org_id, repository.name, github_settings)

            case _:
                raise RuntimeError(f"unexpected patch type '{patch.patch_type}'")
