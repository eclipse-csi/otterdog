# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from abc import ABC, abstractmethod
from dataclasses import dataclass, Field, fields, field as dataclasses_field
from typing import Any
from enum import Enum

from otterdog.utils import diff_to_expected, is_unset


class FailureType(Enum):
    WARNING = 1
    ERROR = 2


@dataclass
class ValidationContext(object):
    validation_failures: list[tuple[FailureType, str]] = dataclasses_field(default_factory=list)

    def add_failure(self, failure_type: FailureType, message: str):
        self.validation_failures.append((failure_type, message))


@dataclass
class ModelObject(ABC):
    """
    The abstract base class for any model object.
    """

    def is_keyed(self) -> bool:
        return any(field.metadata.get("key", False) for field in self.all_fields())

    def get_key(self) -> str:
        return next(filter(lambda field: field.metadata.get("key", False) is True, self.all_fields())).name

    @abstractmethod
    def validate(self, context: ValidationContext, parent_object: object) -> None:
        pass

    def diff_to(self, other: "ModelObject") -> dict[str, Any]:
        if type(self) != type(other):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        diff_result = {}
        for field in self.model_fields():
            if not self.include_field(field):
                continue

            if self.is_nested_model(field):
                continue

            value = self.__getattribute__(field.name)
            other_value = other.__getattribute__(field.name)

            if is_unset(other_value):
                continue

            if is_unset(value):
                diff_result[field.name] = value
            else:
                values_different, diff = diff_to_expected(value, other_value)
                if values_different is True:
                    diff_result[field.name] = diff

        return diff_result

    @classmethod
    def all_fields(cls) -> list[Field]:
        return [field for field in fields(cls)]

    @classmethod
    def model_fields(cls) -> list[Field]:
        return [field for field in fields(cls) if field.metadata.get("external_only", False) is False]

    @staticmethod
    def is_read_only(field: Field) -> bool:
        return field.metadata.get("readonly", False) is True

    @staticmethod
    def is_nested_model(field: Field) -> bool:
        return field.metadata.get("model", False) is True

    @classmethod
    @abstractmethod
    def from_model(cls, data: dict[str, Any]):
        pass

    @classmethod
    @abstractmethod
    def from_provider(cls, data: dict[str, Any]):
        pass

    def include_field(self, field: Field) -> bool:
        return True

    def to_model_dict(self, include_nested_models: bool = False) -> dict[str, Any]:
        result = {}

        for field in self.model_fields():
            if not self.include_field(field):
                continue

            if include_nested_models is False and self.is_nested_model(field):
                continue

            value = self.__getattribute__(field.name)
            if not is_unset(value):
                result[field.name] = value

        return result
