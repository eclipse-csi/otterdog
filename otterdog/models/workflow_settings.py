#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
from typing import Any, ClassVar, Optional

from jsonbender import OptionalS, S, bend  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import FailureType, ModelObject, PatchContext, ValidationContext
from otterdog.providers.github import GitHubProvider
from otterdog.utils import (
    UNSET,
    IndentingPrinter,
    is_set_and_valid,
    is_unset,
    write_patch_object_as_json,
)


@dataclasses.dataclass
class WorkflowSettings(ModelObject, abc.ABC):
    """
    Represents workflow settings on organizational / repository level.
    """

    allowed_actions: str
    allow_github_owned_actions: bool
    allow_verified_creator_actions: bool
    allow_action_patterns: list[str]
    default_workflow_permissions: str
    actions_can_approve_pull_request_reviews: bool

    _selected_action_properties: ClassVar[list[str]] = [
        "allow_github_owned_actions",
        "allow_verified_creator_actions",
        "allow_action_patterns",
    ]

    _allowed_actions_level: ClassVar[dict[str, int]] = {
        "all": 1,
        "local_only": 3,
        "selected": 2,
    }

    @classmethod
    def get_allowed_actions_level(cls, allowed_actions: str) -> int:
        if is_set_and_valid(allowed_actions):
            return cls._allowed_actions_level[allowed_actions]
        else:
            return 0

    def are_actions_more_restricted(self, repo_allowed_actions: str) -> bool:
        if is_set_and_valid(self.allowed_actions):
            org_level = WorkflowSettings.get_allowed_actions_level(self.allowed_actions)
            repo_level = WorkflowSettings.get_allowed_actions_level(repo_allowed_actions)
            return org_level >= repo_level
        return False

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if is_set_and_valid(self.allowed_actions):
            if self.allowed_actions not in {"all", "local_only", "selected"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'allowed_actions' of value "
                    f"'{self.allowed_actions}', "
                    f"only values ('all' | 'local_only' | 'selected') are allowed.",
                )

            if self.allowed_actions != "selected" and len(self.allow_action_patterns) > 0:
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has 'allowed_actions' set to "
                    f"'{self.allowed_actions}', "
                    f"but 'allow_action_patterns' is set to '{self.allow_action_patterns}', "
                    f"setting will be ignored.",
                )

        if is_set_and_valid(self.default_workflow_permissions):
            if self.default_workflow_permissions not in {"read", "write"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"'default_workflow_permissions' has value '{self.default_workflow_permissions}', "
                    f"only values ('read' | 'write') are allowed.",
                )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if is_set_and_valid(self.allowed_actions) and self.allowed_actions in ["all", "local_only"]:
            if field.name in self._selected_action_properties:
                return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        if field.name in self._selected_action_properties:
            if self.__getattribute__(field.name) is None:
                return False

        return True

    @classmethod
    def from_model_data(cls, data: dict[str, Any]):
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]):
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update(
            {
                "allow_github_owned_actions": OptionalS("github_owned_allowed", default=None),
                "allow_verified_creator_actions": OptionalS("verified_allowed", default=None),
                "allow_action_patterns": OptionalS("patterns_allowed", default=[]),
                "actions_can_approve_pull_request_reviews": OptionalS(
                    "can_approve_pull_request_reviews", default=UNSET
                ),
            }
        )
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

        if "allow_github_owned_actions" in data:
            mapping.pop("allow_github_owned_actions")
            mapping["github_owned_allowed"] = S("allow_github_owned_actions")

        if "allow_verified_creator_actions" in data:
            mapping.pop("allow_verified_creator_actions")
            mapping["verified_allowed"] = S("allow_verified_creator_actions")

        if "allow_action_patterns" in data:
            mapping.pop("allow_action_patterns")
            mapping["patterns_allowed"] = S("allow_action_patterns")

        if "actions_can_approve_pull_request_reviews" in data:
            mapping.pop("actions_can_approve_pull_request_reviews")
            mapping["can_approve_pull_request_reviews"] = S("actions_can_approve_pull_request_reviews")

        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> Optional[str]:
        return None

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        write_patch_object_as_json(patch, printer, False)
        printer.level_down()
        printer.println("},")
