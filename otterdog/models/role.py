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
from typing import Any, TypeVar

from otterdog.models import (
    FailureType,
    ModelObject,
    ValidationContext,
)
from otterdog.utils import is_set_and_valid

RT = TypeVar("RT", bound="Role")


@dataclasses.dataclass
class Role(ModelObject, abc.ABC):
    """
    Represents a Role.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    source: str = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    description: str
    permissions: list[str]
    base_role: str

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if is_set_and_valid(self.base_role):
            if self.base_role not in {"none", "read", "triage", "write", "maintain", "admin"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'base_role' of value '{self.base_role}', "
                    f"while only values ('none' | 'read' | 'triage' | 'write' | 'maintain' | 'admin') are allowed.",
                )

        if is_set_and_valid(self.base_role) and is_set_and_valid(self.permissions):
            if self.base_role == "none" and len(self.permissions) > 0:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'base_role' of value '{self.base_role}', "
                    f"and specified additional permissions, which is not allowed.",
                )
