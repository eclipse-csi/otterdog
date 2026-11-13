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
from typing import TYPE_CHECKING, Any, ClassVar, cast

from jsonbender import F, K, OptionalS  # type: ignore

from otterdog.logging import get_logger
from otterdog.models import FailureType, LivePatch, LivePatchType, ValidationContext
from otterdog.models.actions_policy import ActionsPolicy
from otterdog.utils import UNSET, is_set_and_present, is_set_and_valid, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.models.github_organization import GitHubOrganization
    from otterdog.providers.github import GitHubProvider

_logger = get_logger(__name__)

# the conditions targeting repositories that otterdog does not support, they are kept when a policy is updated
_UNSUPPORTED_REPOSITORY_CONDITIONS = ("repository_id", "repository_property")


@dataclasses.dataclass
class OrganizationActionsPolicy(ActionsPolicy):
    """
    Represents an Actions policy defined on organization level, which targets repositories by name.

    A policy targeting repositories by id or by custom property, which otterdog does not support, keeps its targeting
    when it is updated, its repository names are not compared.
    """

    # the lists replace the default value in a patch, so that a default targeting all repositories can be narrowed
    include_repo_names: list[str] = dataclasses.field(metadata={"replace_on_patch": True})
    exclude_repo_names: list[str] = dataclasses.field(metadata={"replace_on_patch": True})
    protect_repo_names: bool

    # the conditions targeting repositories that are not supported, as read from GitHub
    unsupported_conditions: dict[str, Any] = dataclasses.field(metadata={"external_only": True})

    _condition_keys: ClassVar[list[tuple[str, ...]]] = [
        *ActionsPolicy._condition_keys,
        ("include_repo_names", "exclude_repo_names", "protect_repo_names"),
    ]

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

        conditions = data.get("conditions") or {}
        unsupported_conditions = {
            key: conditions[key] for key in _UNSUPPORTED_REPOSITORY_CONDITIONS if conditions.get(key) is not None
        }
        mapping["unsupported_conditions"] = K(unsupported_conditions)

        if len(unsupported_conditions) > 0:
            _logger.warning(
                "actions policy '%s' targets repositories by %s, which is not supported, its targeting is kept on "
                "update",
                data.get("name"),
                " and ".join(unsupported_conditions),
            )
            # the repositories are not targeted by name, the names are not compared
            for key in ["include_repo_names", "exclude_repo_names", "protect_repo_names"]:
                mapping[key] = K(UNSET)

            return mapping

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

    def with_unsupported_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Returns the data of an update of this current policy that keeps its settings not supported by otterdog:
        its unsupported rules, and its targeting of repositories by id or by custom property, which replaces the
        repository names of the configuration as GitHub only supports one kind of targeting.
        """
        data = super().with_unsupported_settings(data)

        if not is_set_and_present(self.unsupported_conditions) or len(self.unsupported_conditions) == 0:
            return data

        conditions = {key: value for key, value in (data.get("conditions") or {}).items() if key != "repository_name"}
        return {**data, "conditions": {**conditions, **self.unsupported_conditions}}

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
                expected_object = unwrap(patch.expected_object).with_unset_values_from(current_object)
                await provider.update_org_actions_policy(
                    org_id,
                    current_object.id,
                    current_object.name,
                    current_object.with_unsupported_settings(await expected_object.to_provider_data(org_id, provider)),
                )
