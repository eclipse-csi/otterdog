#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Any, TypeVar, final

from pydantic import BaseModel

if TYPE_CHECKING:
    from otterdog.models.repository import Repository


class PolicyType(str, Enum):
    MACOS_LARGE_RUNNERS_USAGE = "macos_large_runners"
    REQUIRED_FILE = "required_file"
    PIN_WORKFLOW = "pin_workflow"


PT = TypeVar("PT", bound="Policy")


class Policy(ABC, BaseModel):
    @classmethod
    @abstractmethod
    def policy_type(cls) -> PolicyType: ...

    @property
    def config(self) -> dict[str, Any]:
        return self.model_dump()

    @abstractmethod
    async def evaluate(self, github_id: str) -> None: ...

    @classmethod
    @final
    def create(cls: type[PT], policy_type: PolicyType | str, config: dict[str, Any]) -> PT:
        from .macos_large_runners import MacOSLargeRunnersUsagePolicy
        from .pin_workflow import PinWorkflowPolicy
        from .required_file import RequiredFilePolicy

        if isinstance(policy_type, str):
            policy_type = PolicyType(policy_type)

        return next(c for c in cls.__subclasses__() if c.policy_type() == policy_type).model_validate(config)


def read_policy(content: dict[str, Any]) -> Policy:
    policy_type = content["type"]
    return Policy.create(policy_type, content["config"])


class RepoSelector(BaseModel):
    name_pattern: str | None

    @cached_property
    def _pattern(self):
        return re.compile(self.name_pattern)

    def matches(self, repo: Repository) -> bool:
        return self._pattern.match(repo.name)
