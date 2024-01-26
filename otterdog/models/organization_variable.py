#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Any, Optional, cast

from jsonbender import Forall, If, K, OptionalS, S, bend  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import FailureType, LivePatch, LivePatchType, ValidationContext
from otterdog.models.variable import Variable
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, is_set_and_valid, is_unset


@dataclasses.dataclass
class OrganizationVariable(Variable):
    """
    Represents a Variable defined on organization level.
    """

    visibility: str
    selected_repositories: list[str]

    @property
    def model_object_name(self) -> str:
        return "org_variable"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        super().validate(context, parent_object)

        if is_set_and_valid(self.visibility):
            from .github_organization import GitHubOrganization

            org = cast(GitHubOrganization, parent_object)
            if self.visibility == "private" and org.settings.plan == "free":
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'visibility' of value "
                    f"'{self.visibility}' which is not available for organization with free plan.",
                )
            elif self.visibility not in {"public", "private", "selected"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'visibility' of value "
                    f"'{self.visibility}', "
                    f"only values ('public' | 'private' | 'selected') are allowed.",
                )

            if self.visibility != "selected" and len(self.selected_repositories) > 0:
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has 'visibility' set to "
                    f"'{self.visibility}', "
                    f"but 'selected_repositories' is set to '{self.selected_repositories}', "
                    f"setting will be ignored.",
                )

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]):
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update(
            {
                "visibility": If(
                    S("visibility") == K("all"),
                    K("public"),
                    OptionalS("visibility", default=UNSET),
                ),
                "selected_repositories": OptionalS("selected_repositories", default=[]) >> Forall(lambda x: x["name"]),
            }
        )
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

        if "visibility" in mapping:
            mapping["visibility"] = If(S("visibility") == K("public"), K("all"), S("visibility"))

        if "selected_repositories" in mapping:
            mapping.pop("selected_repositories")
            mapping["selected_repository_ids"] = K(await provider.get_repo_ids(org_id, data["selected_repositories"]))

        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> Optional[str]:
        return f"orgs.{jsonnet_config.create_org_variable}"

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch, org_id: str, provider: GitHubProvider) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                assert isinstance(patch.expected_object, OrganizationVariable)
                await provider.add_org_variable(
                    org_id,
                    await patch.expected_object.to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                assert isinstance(patch.current_object, OrganizationVariable)
                await provider.delete_org_variable(org_id, patch.current_object.name)

            case LivePatchType.CHANGE:
                assert isinstance(patch.expected_object, OrganizationVariable)
                assert isinstance(patch.current_object, OrganizationVariable)
                await provider.update_org_variable(
                    org_id,
                    patch.current_object.name,
                    await patch.expected_object.to_provider_data(org_id, provider),
                )
