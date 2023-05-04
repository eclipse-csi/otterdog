# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from abc import ABC, abstractmethod
from dataclasses import dataclass, Field, fields, field as dataclasses_field
from typing import Literal, Any
from enum import Enum


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

    def diff(self, other: "ModelObject") -> bool:
        if type(self) != type(other):
            raise RuntimeError("not matching")

        for field in self.model_fields():
            value = self.__getattribute__(field.name)
            print(value)

    @classmethod
    def all_fields(cls) -> list[Field]:
        return [field for field in fields(cls)]

    @classmethod
    def model_fields(cls) -> list[Field]:
        return [field for field in fields(cls) if field.metadata.get("external_only", False) is False]

    @staticmethod
    def is_read_only(field: Field) -> bool:
        return field.metadata.get("readonly", False) is True

    @classmethod
    @abstractmethod
    def from_model(cls, data: dict[str, Any]):
        pass

    @classmethod
    @abstractmethod
    def from_provider(cls, data: dict[str, Any]):
        pass


class Unset:
    """
    A marker class to indicate that a value is unset and thus should
    not be considered. This is different to None.
    """
    def __repr__(self) -> str:
        return "<UNSET>"

    def __bool__(self) -> Literal[False]:
        return False

    def __copy__(self):
        return UNSET

    def __deepcopy__(self, memo: dict[int, Any]):
        return UNSET


UNSET = Unset()


def is_unset(value: Any) -> bool:
    """
    Returns whether the given value is an instance of Unset.
    """
    return value is UNSET


def is_set_and_valid(value: Any) -> bool:
    return not is_unset(value) and value is not None
