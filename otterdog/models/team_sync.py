#  *******************************************************************************
#  Copyright (c) 2023-2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


import abc
import dataclasses
from typing import Any

from jsonbender import S  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import FailureType, LivePatch, LivePatchType, ModelObject, ValidationContext
from otterdog.providers.github import GitHubProvider
from otterdog.utils import expect_type, unwrap


@dataclasses.dataclass
class TeamSync(ModelObject, abc.ABC):
    """
    Represents a team sync to an IdP provider
    """

    name: str = dataclasses.field(metadata={"key": True})
    description: str
    id: str

    @property
    def model_object_name(self) -> str:
        return "team_sync"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_team_sync}"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        missing: list[str] = []

        if not self.id or not self.id.strip():
            missing.append("id")
        if not self.name or not self.name.strip():
            missing.append("name")
        if not self.description or not self.description.strip():
            missing.append("description")

        if missing:
            context.add_failure(
                FailureType.ERROR,
                (
                    f"{self.get_model_header(parent_object)} is missing required fields: "
                    f"{', '.join(missing)}. "
                    "Fields must not be empty or whitespace-only."
                ),
            )

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)
        mapping.update({"id": S("group_id"), "name": S("group_name"), "description": S("group_description")})
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)
        mapping.update(
            {
                "group_id": S("id"),
                "group_name": S("name"),
                "group_description": S("description"),
            }
        )

        return {k: v for k, v in mapping.items() if k.startswith("group_")}

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch["TeamSync"], org_id: str, provider: GitHubProvider) -> None:
        from .team import Team

        team = expect_type(patch.parent_object, Team)

        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_org_team_sync_group(
                    org_id,
                    team.name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                await provider.delete_org_team_sync_group(
                    org_id,
                    team.name,
                    await unwrap(patch.current_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.CHANGE:
                await provider.update_org_team_sync_group(
                    org_id,
                    team.name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
