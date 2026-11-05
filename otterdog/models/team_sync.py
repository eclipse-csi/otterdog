#  *******************************************************************************
#  Copyright (c) 2023-2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
from typing import TYPE_CHECKING, Any

from jsonbender import OptionalS, S  # type: ignore

from otterdog.models import FailureType, LivePatch, LivePatchType, ModelObject, ValidationContext
from otterdog.utils import expect_type, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class TeamSync(ModelObject, abc.ABC):
    """
    Represents an identity provider (IdP) group connected to a team via GitHub Enterprise Cloud team synchronization.

    The group is identified by its id, the name and description are required by the GitHub API
    when connecting the group, but are informational only.
    """

    id: str = dataclasses.field(metadata={"key": True})
    name: str
    description: str

    @property
    def model_object_name(self) -> str:
        return "team_sync"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_team_sync}"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        missing: list[str] = []

        if not isinstance(self.id, str) or not self.id.strip():
            missing.append("id")
        if not isinstance(self.name, str) or not self.name.strip():
            missing.append("name")

        if missing:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} is missing required fields: {', '.join(missing)}, "
                "fields must not be empty or whitespace-only.",
            )

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)
        mapping.update(
            {
                "id": S("group_id"),
                "name": OptionalS("group_name", default=""),
                "description": OptionalS("group_description", default=""),
            }
        )
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        # the GitHub API requires all 3 properties for each connected group
        return {
            "group_id": S("id"),
            "group_name": OptionalS("name", default=""),
            "group_description": OptionalS("description", default=""),
        }

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch[TeamSync], org_id: str, provider: GitHubProvider) -> None:
        from otterdog.models.team import Team

        team = expect_type(patch.parent_object, Team)

        match patch.patch_type:
            case LivePatchType.ADD | LivePatchType.CHANGE:
                await provider.update_org_team_sync_group(
                    org_id,
                    team.slug,
                    team.name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                await provider.delete_org_team_sync_group(
                    org_id,
                    team.slug,
                    team.name,
                    unwrap(patch.current_object).id,
                )
