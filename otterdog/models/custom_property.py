#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from jsonbender import OptionalS, S  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.utils import Change, is_set_and_present, is_set_and_valid, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


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
                    f"{self.get_model_header(parent_object)} has 'value_type' set to '{self.value_type}', "
                    f"while only values ('string' | 'single_select' | 'multi_select' | 'true_false') are allowed.",
                )

            if (
                self.value_type in {"single_select", "multi_select"}
                and is_set_and_present(self.allowed_values)
                and len(self.allowed_values) == 0
            ):
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'value_type' set to '{self.value_type}', "
                    f"but no 'allowed_values' are defined.",
                )

            if (
                self.value_type in {"single_select", "multi_select"}
                and is_set_and_present(self.allowed_values)
                and len(self.allowed_values) > 200
            ):
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'value_type' set to '{self.value_type}', "
                    f"but more than 200 elements as 'allowed_values' are defined.",
                )

        if is_set_and_valid(self.required):
            if self.required is True:
                if not is_set_and_present(self.default_value):
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has 'required' set to 'true', "
                        f"but no property 'default_value' is specified.",
                    )
            elif is_set_and_present(self.default_value):
                if isinstance(self.default_value, str) and len(self.default_value) > 0:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has 'required' set to 'false' "
                        f"but property 'default_value' is set to a non-empty value.",
                    )
                elif isinstance(self.default_value, list) and len(self.default_value) > 0:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has 'required' set to 'false' "
                        f"but property 'default_value' is set to a non-empty list.",
                    )

        if is_set_and_valid(self.default_value) and is_set_and_valid(self.value_type):
            if self.value_type == "single_select" and not isinstance(self.default_value, str):
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'value_type' set to '{self.value_type}', "
                    f"but 'default_value' contains a list of values '{self.default_value}'.",
                )

        if (
            is_set_and_present(self.default_value)
            and is_set_and_present(self.allowed_values)
            and len(self.allowed_values) > 0
        ):
            if isinstance(self.default_value, str) and self.default_value not in self.allowed_values:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'default_value' set to '{self.default_value}', "
                    f"but it is not in the list of allowed values '{self.allowed_values}'.",
                )
            elif isinstance(self.default_value, list):
                for value in self.default_value:
                    if value not in self.allowed_values:
                        context.add_failure(
                            FailureType.ERROR,
                            f"{self.get_model_header(parent_object)} has a 'default_value' set to "
                            f"'{self.default_value}', "
                            f"but some of its elements are not in the list of allowed values '{self.allowed_values}'.",
                        )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if self.required is not True and field.name in ["default_value"]:
            return False

        if self.value_type not in {"single_select", "multi_select"} and field.name in ["allowed_values"]:
            return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)
        mapping.update(
            {
                "name": S("property_name"),
                "allowed_values": OptionalS("allowed_values", default=[]),
            }
        )
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        if "name" in data:
            mapping.pop("name")

        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_custom_property}"

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: CustomProperty | None,
        current_object: CustomProperty | None,
        parent_object: ModelObject | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        if current_object is None:
            expected_object = unwrap(expected_object)
            handler(LivePatch.of_addition(expected_object, parent_object, expected_object.apply_live_patch))
            return

        if expected_object is None:
            handler(LivePatch.of_deletion(current_object, parent_object, current_object.apply_live_patch))
            return

        modified_property: dict[str, Change[Any]] = expected_object.get_difference_from(current_object)

        if len(modified_property) > 0:
            if "value_type" in modified_property:
                raise RuntimeError(
                    f"trying to change 'value_type' to '{expected_object.value_type}' for "
                    f"{expected_object.get_model_header(parent_object)} which is not supported."
                )

            handler(
                LivePatch.of_changes(
                    expected_object,
                    current_object,
                    modified_property,
                    parent_object,
                    False,
                    expected_object.apply_live_patch,
                )
            )

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch[CustomProperty], org_id: str, provider: GitHubProvider) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                expected_object = unwrap(patch.expected_object)
                await provider.add_org_custom_property(
                    org_id,
                    expected_object.name,
                    await expected_object.to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                current_object = unwrap(patch.current_object)
                await provider.delete_org_custom_property(org_id, current_object.name)

            case LivePatchType.CHANGE:
                await provider.update_org_custom_property(
                    org_id,
                    unwrap(patch.current_object).name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
