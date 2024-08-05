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


class PolicyType(str, Enum):
    MACOS_LARGE_RUNNERS_USAGE = "macos_large_runners"


class Policy(ABC):
    @property
    @abstractmethod
    def type(self) -> PolicyType: ...

    @property
    @abstractmethod
    def config(self) -> dict[str, Any]: ...


def read_policy(content: dict[str, Any]) -> Policy:
    policy_type = content["type"]

    match policy_type:
        case PolicyType.MACOS_LARGE_RUNNERS_USAGE.value:
            from otterdog.webapp.policies.macos_large_runners import (
                MacOSLargeRunnersUsagePolicy,
            )

            return MacOSLargeRunnersUsagePolicy(**content["config"])
        case _:
            raise RuntimeError(f"unknown policy type '{policy_type}'")
