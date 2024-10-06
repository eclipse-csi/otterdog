#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel


class PolicyType(str, Enum):
    MACOS_LARGE_RUNNERS_USAGE = "macos_large_runners"
    REQUIRED_FILE = "required_file"


class Policy(ABC, BaseModel):
    @property
    @abstractmethod
    def type(self) -> PolicyType: ...

    @property
    def config(self) -> dict[str, Any]:
        return self.model_dump()

    @abstractmethod
    async def evaluate(self, github_id: str) -> None: ...


def read_policy(content: dict[str, Any]) -> Policy:
    policy_type = content["type"]
    return create_policy(policy_type, content["config"])


def create_policy(policy_type: PolicyType | str, config: dict[str, Any]) -> Policy:
    if isinstance(policy_type, str):
        policy_type = PolicyType(policy_type)

    match policy_type:
        case PolicyType.MACOS_LARGE_RUNNERS_USAGE:
            from otterdog.webapp.policies.macos_large_runners import MacOSLargeRunnersUsagePolicy

            return MacOSLargeRunnersUsagePolicy.model_validate(config)

        case PolicyType.REQUIRED_FILE:
            from otterdog.webapp.policies.required_file import RequiredFilePolicy

            return RequiredFilePolicy.model_validate(config)

        case _:
            raise RuntimeError(f"unknown policy type '{policy_type}'")
