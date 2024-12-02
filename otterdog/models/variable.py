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

from otterdog.models import FailureType, ModelObject, ValidationContext

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
                f"{self.get_model_header(parent_object)} starts with prefix 'GITHUB_', "
                f"which is not allowed for variables.",
            )
