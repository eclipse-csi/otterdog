# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, Iterator

from colorama import Style

from otterdog.providers.github import Github
from otterdog.jsonnet import JsonnetConfig
from otterdog.utils import patch_to_other, is_unset, T, is_different_ignoring_order, Change, IndentingPrinter


class FailureType(Enum):
    WARNING = 1
    ERROR = 2


@dataclasses.dataclass
class ValidationContext(object):
    validation_failures: list[tuple[FailureType, str]] = dataclasses.field(default_factory=list)

    def add_failure(self, failure_type: FailureType, message: str):
        self.validation_failures.append((failure_type, message))


@dataclasses.dataclass
class ModelObject(ABC):
    """
    The abstract base class for any model object.
    """

    def __post_init__(self):
        """
        Assigns to all field which are UNSET their default value, if one is available.
        """
        for field in self.all_fields():
            value = self.__getattribute__(field.name)
            if is_unset(value):
                if field.default is not dataclasses.MISSING:
                    self.__setattr__(field.name, field.default)
                elif field.default_factory is not dataclasses.MISSING:
                    self.__setattr__(field.name, field.default_factory())

    @property
    @abstractmethod
    def model_object_name(self) -> str:
        pass

    def is_keyed(self) -> bool:
        return any(field.metadata.get("key", False) for field in self.all_fields())

    def get_key(self) -> str:
        return next(filter(lambda field: field.metadata.get("key", False) is True, self.all_fields())).name

    def get_key_value(self) -> Any:
        return self.__getattribute__(self.get_key())

    @abstractmethod
    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        pass

    def get_difference_from(self, other: ModelObject) -> dict[str, Change[T]]:
        if not isinstance(other, self.__class__):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        diff_result: dict[str, Change[T]] = {}
        for key in self.keys(for_diff=True,
                             for_patch=False,
                             include_nested_models=False,
                             exclude_unset_keys=True):

            to_value = self.__getattribute__(key)
            from_value = other.__getattribute__(key)

            if is_unset(from_value):
                continue

            if is_different_ignoring_order(to_value, from_value):
                diff_result[key] = Change(from_value, to_value)

        return diff_result

    def get_patch_to(self, other: ModelObject) -> dict[str, Any]:
        if not isinstance(other, self.__class__):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        patch_result = {}
        for key in self.keys(for_diff=False,
                             for_patch=True,
                             include_nested_models=False,
                             exclude_unset_keys=True):

            value = self.__getattribute__(key)
            other_value = other.__getattribute__(key)

            if is_unset(other_value):
                continue

            patch_needed, diff = patch_to_other(value, other_value)
            if patch_needed is True:
                patch_result[key] = diff

        return patch_result

    @classmethod
    def all_fields(cls) -> list[dataclasses.Field]:
        return [field for field in dataclasses.fields(cls)]

    @classmethod
    def model_fields(cls) -> list[dataclasses.Field]:
        return [field for field in dataclasses.fields(cls) if not cls.is_external_only(field)]

    @classmethod
    def model_only_fields(cls) -> list[dataclasses.Field]:
        return [field for field in dataclasses.fields(cls) if cls.is_model_only(field)]

    @classmethod
    def provider_fields(cls) -> list[dataclasses.Field]:
        return [field for field in dataclasses.fields(cls) if
                not cls.is_external_only(field) and
                not cls.is_model_only(field) and
                not cls.is_read_only(field) and
                not cls.is_nested_model(field)]

    @classmethod
    def _get_field(cls, key: str) -> dataclasses.Field:
        for field in dataclasses.fields(cls):
            if field.name == key:
                return field

        raise ValueError(f"unknown key {key}")

    @staticmethod
    def is_external_only(field: dataclasses.Field) -> bool:
        return field.metadata.get("external_only", False) is True

    @staticmethod
    def is_read_only(field: dataclasses.Field) -> bool:
        return field.metadata.get("read_only", False) is True

    @classmethod
    def is_read_only_key(cls, key: str) -> bool:
        return cls.is_read_only(cls._get_field(key))

    @staticmethod
    def is_model_only(field: dataclasses.Field) -> bool:
        return field.metadata.get("model_only", False) is True

    @staticmethod
    def is_nested_model(field: dataclasses.Field) -> bool:
        return field.metadata.get("nested_model", False) is True

    def get_model_objects(self) -> Iterator[tuple[ModelObject, ModelObject]]:
        yield from []

    def get_model_header(self, parent_object: Optional[ModelObject] = None) -> str:
        header = f"{Style.BRIGHT}{self.model_object_name}{Style.RESET_ALL}"

        if self.is_keyed():
            key = self.get_key()
            header = header + f"[{key}={Style.BRIGHT}\"{self.get_key_value()}\"{Style.RESET_ALL}"

            if isinstance(parent_object, ModelObject):
                header = header + f", {parent_object.model_object_name}=" \
                                  f"{Style.BRIGHT}\"{parent_object.get_key_value()}\"{Style.RESET_ALL}"

            header = header + "]"

        return header

    @classmethod
    @abstractmethod
    def from_model_data(cls, data: dict[str, Any]):
        pass

    @classmethod
    @abstractmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]):
        pass

    def to_provider_data(self, provider: Optional[Github] = None) -> dict[str, Any]:
        return self._to_provider_data(self.to_model_dict(), provider)

    @classmethod
    def changes_to_provider(cls, data: dict[str, Change[Any]], provider: Optional[Github] = None) -> dict[str, Any]:
        return cls._to_provider_data({key: change.to_value for key, change in data.items()}, provider)

    @classmethod
    @abstractmethod
    def _to_provider_data(cls, data: dict[str, Any], provider: Optional[Github] = None) -> dict[str, Any]:
        pass

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return self.include_field_for_diff_computation(field)

    def keys(self,
             for_diff: bool = False,
             for_patch: bool = False,
             include_nested_models: bool = False,
             exclude_unset_keys: bool = True) -> list[str]:

        result = list()

        for field in self.model_fields():
            if for_diff is True and not self.include_field_for_diff_computation(field):
                continue

            if for_patch is True and not self.include_field_for_patch_computation(field):
                continue

            if (for_diff or for_patch) and self.is_model_only(field):
                continue

            if include_nested_models is False and self.is_nested_model(field):
                continue

            if exclude_unset_keys:
                value = self.__getattribute__(field.name)
                if not is_unset(value):
                    result.append(field.name)
            else:
                result.append(field.name)

        return result

    def to_model_dict(self, for_diff: bool = False, include_nested_models: bool = False) -> dict[str, Any]:
        result = {}

        for key in self.keys(for_diff=for_diff,
                             include_nested_models=include_nested_models,
                             exclude_unset_keys=True):
            result[key] = self.__getattribute__(key)

        return result

    @abstractmethod
    def to_jsonnet(self,
                   printer: IndentingPrinter,
                   jsonnet_config: JsonnetConfig,
                   extend: bool,
                   default_object: ModelObject) -> None:
        pass
