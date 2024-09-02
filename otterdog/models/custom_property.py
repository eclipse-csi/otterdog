#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Any

from jsonbender import OptionalS, S, bend  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, is_set_and_present, is_set_and_valid, is_unset


@dataclasses.dataclass
class CustomProperty(ModelObject):
    """
    Represents a Custom Property defined in an Organization.
    """

    name: str = dataclasses.field(metadata={"key": True})
    value_type: str
    required: bool
    default_value: str | list[str] | None
    description: str | None
    allowed_values: list[str] | None

    @property
    def model_object_name(self) -> str:
        return "custom_property"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if is_set_and_valid(self.value_type):
            if self.value_type not in {"string", "single_select", "multi_select", "true_false"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'value_type' of value "
                    f"'{self.value_type}', "
                    f"only values ('string' | 'single_select' | 'multi_select' | 'true_false') are allowed.",
                )

            if (
                self.value_type in {"single_select", "multi_select"}
                and is_set_and_present(self.allowed_values)
                and len(self.allowed_values) == 0
            ):
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'value_type' of value "
                    f"'{self.value_type}' but no 'allowed_values' defined.",
                )

            if (
                self.value_type in {"single_select", "multi_select"}
                and is_set_and_present(self.allowed_values)
                and len(self.allowed_values) > 200
            ):
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'value_type' of value "
                    f"'{self.value_type}' but more than 200 elements as 'allowed_values' defined.",
                )

        if is_set_and_valid(self.required) and self.required is True:
            if not is_set_and_present(self.default_value):
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'required' set to 'True' "
                    f"but no property 'default_value' is specified.",
                )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if self.required is not True:
            if field.name in ["default_value"]:
                return False

        if self.value_type not in {"single_select", "multi_select"}:
            if field.name in ["allowed_values"]:
                return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    @classmethod
    def from_model_data(cls, data: dict[str, Any]) -> CustomProperty:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]) -> CustomProperty:
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update({"name": S("property_name")})
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

        if "name" in data:
            mapping.pop("name")

        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_custom_property}"

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch, org_id: str, provider: GitHubProvider) -> None:
        from .repository import Repository

        match patch.patch_type:
            case LivePatchType.ADD:
                assert isinstance(patch.expected_object, CustomProperty)
                assert isinstance(patch.parent_object, Repository)
                await provider.add_org_custom_property(
                    org_id,
                    patch.expected_object.name,
                    await patch.expected_object.to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                assert isinstance(patch.current_object, CustomProperty)
                assert isinstance(patch.parent_object, Repository)
                await provider.delete_org_custom_property(org_id, patch.current_object.name)

            case LivePatchType.CHANGE:
                assert patch.changes is not None
                assert isinstance(patch.current_object, CustomProperty)
                assert isinstance(patch.parent_object, Repository)
                await provider.update_org_custom_property(
                    org_id,
                    patch.current_object.name,
                    await cls.changes_to_provider(org_id, patch.changes, provider),
                )
