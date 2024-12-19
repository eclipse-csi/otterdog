#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
import fnmatch
from typing import TYPE_CHECKING, Any, cast

from jsonbender import K, OptionalS  # type: ignore

from otterdog.models import FailureType, LivePatch, LivePatchType, ValidationContext
from otterdog.models.ruleset import Ruleset
from otterdog.utils import is_set_and_valid, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class OrganizationRuleset(Ruleset):
    """
    Represents a ruleset defined on organization level.
    """

    include_repo_names: list[str]
    exclude_repo_names: list[str]
    protect_repo_names: bool

    @property
    def model_object_name(self) -> str:
        return "org_ruleset"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_ruleset}"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        from otterdog.models.github_organization import GitHubOrganization

        super().validate(context, parent_object)

        repositories = cast(GitHubOrganization, context.root_object).repositories
        all_repo_names = (x.name for x in repositories)

        if is_set_and_valid(self.include_repo_names):
            for repo_name_pattern in self.include_repo_names:
                if repo_name_pattern == "~ALL":
                    continue
                elif len(fnmatch.filter(all_repo_names, repo_name_pattern)) == 0:
                    context.add_failure(
                        FailureType.WARNING,
                        f"{self.get_model_header(parent_object)} has an 'include_repo_names' pattern "
                        f"'{repo_name_pattern}' that does not match any existing repository",
                    )

        if is_set_and_valid(self.exclude_repo_names):
            for repo_name_pattern in self.exclude_repo_names:
                if repo_name_pattern == "~ALL":
                    continue
                elif len(fnmatch.filter(all_repo_names, repo_name_pattern)) == 0:
                    context.add_failure(
                        FailureType.WARNING,
                        f"{self.get_model_header(parent_object)} has an 'exclude_repo_names' pattern "
                        f"'{repo_name_pattern}' that does not match any existing repository",
                    )

        if is_set_and_valid(self.protect_repo_names):
            if (
                self.protect_repo_names is True
                and len(self.include_repo_names) == 0
                and len(self.exclude_repo_names) == 0
            ):
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has 'protect_repo_names' set to "
                    f"'{self.protect_repo_names}' but 'include_repo_names' and 'exclude_repo_names' are empty.",
                )

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        mapping.update(
            {
                "include_repo_names": OptionalS("conditions", "repository_name", "include", default=[]),
                "exclude_repo_names": OptionalS("conditions", "repository_name", "exclude", default=[]),
                "protect_repo_names": OptionalS("conditions", "repository_name", "protected", default=False),
            }
        )

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        # include_repo_names / exclude_repo_names
        repo_names = {}
        if "include_repo_names" in data:
            mapping.pop("include_repo_names")
            repo_names["include"] = K(data["include_repo_names"])

        if "exclude_repo_names" in data:
            mapping.pop("exclude_repo_names")
            repo_names["exclude"] = K(data["exclude_repo_names"])

        if "protect_repo_names" in data:
            mapping.pop("protect_repo_names")
            repo_names["protected"] = K(data["protect_repo_names"])

        if len(repo_names) > 0:
            conditions = mapping.get("conditions", {})
            conditions.update({"repository_name": repo_names})

        return mapping

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[OrganizationRuleset],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_org_ruleset(
                    org_id,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                current_object = unwrap(patch.current_object)
                await provider.delete_org_ruleset(org_id, current_object.id, current_object.name)

            case LivePatchType.CHANGE:
                current_object = unwrap(patch.current_object)
                await provider.update_org_ruleset(
                    org_id,
                    current_object.id,
                    current_object.name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
