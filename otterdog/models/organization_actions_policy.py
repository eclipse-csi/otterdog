#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
import fnmatch
from typing import TYPE_CHECKING, Any, cast

from jsonbender import F, K, OptionalS  # type: ignore

from otterdog.models import FailureType, LivePatch, LivePatchType, ValidationContext
from otterdog.models.actions_policy import ActionsPolicy
from otterdog.utils import is_set_and_valid, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.models.github_organization import GitHubOrganization
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class OrganizationActionsPolicy(ActionsPolicy):
    """
    Represents an Actions policy defined on organization level, which targets repositories by name.
    """

    include_repo_names: list[str]
    exclude_repo_names: list[str]
    protect_repo_names: bool

    @property
    def model_object_name(self) -> str:
        return "org_actions_policy"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_actions_policy}"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        super().validate(context, parent_object)

        header = self.get_model_header(parent_object)
        repositories = cast("GitHubOrganization", context.root_object).repositories
        all_repo_names = [x.name for x in repositories]

        for key in ["include_repo_names", "exclude_repo_names"]:
            patterns = self.__getattribute__(key)
            if not is_set_and_valid(patterns):
                continue

            for pattern in patterns:
                if pattern != "~ALL" and len(fnmatch.filter(all_repo_names, pattern)) == 0:
                    context.add_failure(
                        FailureType.WARNING,
                        f"{header} has an '{key}' pattern '{pattern}' that does not match any existing repository",
                    )

        if is_set_and_valid(self.include_repo_names) and len(self.include_repo_names) == 0:
            context.add_failure(
                FailureType.WARNING,
                f"{header} has an empty 'include_repo_names', the policy does not apply to any repository, "
                f"use '~ALL' to target all repositories.",
            )

        if (
            self.protect_repo_names is True
            and is_set_and_valid(self.include_repo_names)
            and is_set_and_valid(self.exclude_repo_names)
            and len(self.include_repo_names) == 0
            and len(self.exclude_repo_names) == 0
        ):
            context.add_failure(
                FailureType.WARNING,
                f"{header} has 'protect_repo_names' set to '{self.protect_repo_names}' "
                f"but 'include_repo_names' and 'exclude_repo_names' are empty.",
            )

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        def repository_name(key: str, default: Any) -> Any:
            return OptionalS("conditions", default={}) >> F(
                lambda conditions: ((conditions or {}).get("repository_name") or {}).get(key) or default
            )

        mapping.update(
            {
                "include_repo_names": repository_name("include", []),
                "exclude_repo_names": repository_name("exclude", []),
                "protect_repo_names": repository_name("protected", False),
            }
        )

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        repo_names = {}
        for key, condition_key in [
            ("include_repo_names", "include"),
            ("exclude_repo_names", "exclude"),
            ("protect_repo_names", "protected"),
        ]:
            if key in mapping:
                mapping.pop(key)
                repo_names[condition_key] = K(data[key])

        if len(repo_names) > 0:
            mapping.setdefault("conditions", {})["repository_name"] = repo_names

        return mapping

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[OrganizationActionsPolicy],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_org_actions_policy(
                    org_id,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                current_object = unwrap(patch.current_object)
                await provider.delete_org_actions_policy(org_id, current_object.id, current_object.name)

            case LivePatchType.CHANGE:
                current_object = unwrap(patch.current_object)
                expected_object = unwrap(patch.expected_object).with_unset_rules_from(current_object)
                await provider.update_org_actions_policy(
                    org_id,
                    current_object.id,
                    current_object.name,
                    current_object.with_unsupported_rules(await expected_object.to_provider_data(org_id, provider)),
                )
