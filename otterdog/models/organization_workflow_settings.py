#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
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
    ValidationContext,
)
from otterdog.models.workflow_settings import WorkflowSettings
from otterdog.utils import is_set_and_valid

if TYPE_CHECKING:
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class OrganizationWorkflowSettings(WorkflowSettings):
    """
    Represents workflow settings defined on organization level.
    """

    enabled_repositories: str
    selected_repositories: list[str]

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
                    f"{parent_object.get_model_header()} has 'enabled_repositories' of value "
                    f"'{self.enabled_repositories}', "
                    f"while only values ('all' | 'none' | 'selected') are allowed.",
                )

            if self.enabled_repositories != "selected" and len(self.selected_repositories) > 0:
                context.add_failure(
                    FailureType.WARNING,
                    f"{parent_object.get_model_header()} has 'enabled_repositories' set to "
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
