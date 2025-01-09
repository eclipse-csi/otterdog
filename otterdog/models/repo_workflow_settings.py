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

from jsonbender import S  # type: ignore

from otterdog.models import (
    FailureType,
    ModelObject,
    ValidationContext,
)
from otterdog.models.workflow_settings import WorkflowSettings
from otterdog.utils import UNSET, is_set_and_valid, is_unset

if TYPE_CHECKING:
    from otterdog.models.organization_workflow_settings import OrganizationWorkflowSettings
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class RepositoryWorkflowSettings(WorkflowSettings):
    """
    Represents workflow settings defined on repository level.
    """

    enabled: bool

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

        if org_workflow_settings.are_actions_more_or_equally_restricted(copy.allowed_actions):
            copy.allowed_actions = UNSET  # type: ignore
            for prop in self._selected_action_properties:
                copy.__setattr__(prop, UNSET)

        if org_workflow_settings.default_workflow_permissions == "read":
            copy.default_workflow_permissions = UNSET  # type: ignore

        if org_workflow_settings.actions_can_approve_pull_request_reviews is False:
            copy.actions_can_approve_pull_request_reviews = UNSET  # type: ignore

        return copy

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        from .repository import Repository

        super().validate(context, parent_object)

        repo = cast(Repository, parent_object)

        actions_enabled = None
        if is_set_and_valid(self.enabled) and self.enabled is True:
            from .github_organization import GitHubOrganization

            actions_enabled = True
            org_workflow_settings = cast(GitHubOrganization, context.root_object).settings.workflows

            if org_workflow_settings.enabled_repositories == "none":
                actions_enabled = False
                context.add_failure(
                    FailureType.INFO,
                    f"{parent_object.get_model_header()} has enabled workflows, "
                    f"while on organization level it is disabled for all repositories, setting will be ignored.",
                )

            if (
                org_workflow_settings.enabled_repositories == "selected"
                and repo.name not in org_workflow_settings.selected_repositories
            ):
                actions_enabled = False
                context.add_failure(
                    FailureType.INFO,
                    f"{parent_object.get_model_header()} has enabled workflows, "
                    f"while on organization level it is only enabled for selected repositories, "
                    f"setting will be ignored.",
                )

            if org_workflow_settings.are_actions_more_restricted(self.allowed_actions):
                context.add_failure(
                    FailureType.INFO,
                    f"{parent_object.get_model_header()} has set 'allowed_actions' to '{self.allowed_actions}', "
                    f"while on organization level it is more restricted to '{org_workflow_settings.allowed_actions}', "
                    f"setting will be ignored.",
                )

            if (
                org_workflow_settings.default_workflow_permissions == "read"
                and self.default_workflow_permissions == "write"
            ):
                context.add_failure(
                    FailureType.INFO,
                    f"{parent_object.get_model_header()} has 'default_workflow_permissions' of value "
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
                    f"{parent_object.get_model_header()} has 'actions_can_approve_pull_request_reviews' enabled, "
                    f"while on organization level it is disabled, setting will be ignored.",
                )
        elif self.enabled is False:
            actions_enabled = False

        if repo.code_scanning_default_setup_enabled is True and actions_enabled is False:
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has 'code_scanning_default_setup_enabled' of "
                f"value '{repo.code_scanning_default_setup_enabled}' while GitHub Actions are disabled.",
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
