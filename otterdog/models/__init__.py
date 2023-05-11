# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from abc import ABC, abstractmethod
from dataclasses import dataclass, Field, fields, field as dataclasses_field
from enum import Enum
from typing import Any, Union

from otterdog.providers.github import Github
from otterdog.utils import patch_to_other, is_unset, T, is_different_ignoring_order, Change


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

    def get_difference_from(self, other: "ModelObject") -> dict[str, Change[T]]:
        if not isinstance(other, self.__class__):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        diff_result = {}
        for field in self.model_fields():
            if not self.include_field_for_diff_computation(field):
                continue

            if self.is_nested_model(field):
                continue

            to_value = self.__getattribute__(field.name)
            from_value = other.__getattribute__(field.name)

            if is_unset(to_value) or is_unset(from_value):
                continue

            if is_different_ignoring_order(to_value, from_value):
                diff_result[field.name] = Change(from_value, to_value)

        return diff_result

    def get_patch_to(self, other: "ModelObject") -> dict[str, Any]:
        if not isinstance(other, self.__class__):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        patch_result = {}
        for field in self.model_fields():
            if not self.include_field_for_patch_computation(field):
                continue

            if self.is_nested_model(field):
                continue

            value = self.__getattribute__(field.name)
            other_value = other.__getattribute__(field.name)

            if is_unset(other_value):
                continue

            if is_unset(value):
                continue
            else:
                patch_needed, diff = patch_to_other(value, other_value)
                if patch_needed is True:
                    patch_result[field.name] = diff

        return patch_result

    @classmethod
    def all_fields(cls) -> list[Field]:
        return [field for field in fields(cls)]

    @classmethod
    def model_fields(cls) -> list[Field]:
        return [field for field in fields(cls) if not cls.is_external_only(field)]

    @classmethod
    def provider_fields(cls) -> list[Field]:
        return [field for field in fields(cls) if
                not cls.is_external_only(field) and not cls.is_read_only(field) and not cls.is_nested_model(field)]

    @classmethod
    def _get_field(cls, key: str) -> Field:
        for field in fields(cls):
            if field.name == key:
                return field

        raise ValueError(f"unknown key {key}")

    @staticmethod
    def is_external_only(field: Field) -> bool:
        return field.metadata.get("external_only", False) is True

    @staticmethod
    def is_read_only(field: Field) -> bool:
        return field.metadata.get("read_only", False) is True

    @classmethod
    def is_read_only_key(cls, key: str) -> bool:
        return cls.is_read_only(cls._get_field(key))

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

    def to_provider(self, provider: Union[Github, None] = None) -> dict[str, Any]:
        return self._to_provider(self.to_model_dict(), provider)

    @classmethod
    def changes_to_provider(cls, data: dict[str, Change[Any]], provider: Union[Github, None] = None) -> dict[str, Any]:
        return cls._to_provider({key: change.to_value for key, change in data.items()}, provider)

    @classmethod
    @abstractmethod
    def _to_provider(cls, data: dict[str, Any], provider: Union[Github, None] = None) -> dict[str, Any]:
        pass

    def include_field_for_diff_computation(self, field: Field) -> bool:
        return True

    def include_field_for_patch_computation(self, field: Field) -> bool:
        return self.include_field_for_diff_computation(field)

    def keys(self, for_diff: bool = False, include_nested_models: bool = False) -> list[str]:
        result = list()

        for field in self.model_fields():
            if for_diff is True and not self.include_field_for_diff_computation(field):
                continue

            if include_nested_models is False and self.is_nested_model(field):
                continue

            value = self.__getattribute__(field.name)
            if not is_unset(value):
                result.append(field.name)

        return result

    def to_model_dict(self, for_diff: bool = False, include_nested_models: bool = False) -> dict[str, Any]:
        result = {}

        for key in self.keys(for_diff, include_nested_models):
            value = self.__getattribute__(key)
            if not is_unset(value):
                result[key] = value

        return result
