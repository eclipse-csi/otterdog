# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
from typing import Any, TypeVar, Optional

from jsonbender import bend, S, OptionalS  # type: ignore

from otterdog.models import ModelObject, ValidationContext, FailureType, LivePatchContext, LivePatchHandler, LivePatch
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, is_unset, Change, associate_by_key

VT = TypeVar("VT", bound="Variable")


@dataclasses.dataclass
class Variable(ModelObject, abc.ABC):
    """
    Represents a Variable.
    """

    name: str = dataclasses.field(metadata={"key": True})
    value: str

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if self.name.startswith("GITHUB_"):
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} starts with prefix 'GITHUB_' which is not allowed for variables.",
            )

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
        return mapping

    @classmethod
    def get_mapping_to_provider(cls, org_id: str, data: dict[str, Any], provider: GitHubProvider) -> dict[str, Any]:
        return {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: Optional[ModelObject],
        current_object: Optional[ModelObject],
        parent_object: Optional[ModelObject],
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        if current_object is None:
            assert isinstance(expected_object, Variable)
            handler(LivePatch.of_addition(expected_object, parent_object, expected_object.apply_live_patch))
            return

        if expected_object is None:
            assert isinstance(current_object, Variable)
            handler(LivePatch.of_deletion(current_object, parent_object, current_object.apply_live_patch))
            return

        assert isinstance(expected_object, Variable)
        assert isinstance(current_object, Variable)

        modified_variable: dict[str, Change[Any]] = expected_object.get_difference_from(current_object)

        if len(modified_variable) > 0:
            handler(
                LivePatch.of_changes(
                    expected_object,
                    current_object,
                    modified_variable,
                    parent_object,
                    False,
                    expected_object.apply_live_patch,
                )
            )

    @classmethod
    def generate_live_patch_of_list(
        cls,
        expected_variables: list[VT],
        current_variables: list[VT],
        parent_object: Optional[ModelObject],
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        expected_variables_by_name = associate_by_key(expected_variables, lambda x: x.name)

        for current_variable in current_variables:
            variable_name = current_variable.name

            expected_variable = expected_variables_by_name.get(variable_name)
            if expected_variable is None:
                cls.generate_live_patch(None, current_variable, parent_object, context, handler)
                continue

            # pop the already handled variable
            expected_variables_by_name.pop(expected_variable.name)

            cls.generate_live_patch(expected_variable, current_variable, parent_object, context, handler)

        for variable_name, variable in expected_variables_by_name.items():
            cls.generate_live_patch(variable, None, parent_object, context, handler)
