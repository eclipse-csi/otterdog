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
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel

if TYPE_CHECKING:
    from otterdog.webapp.db.models import PolicyModel


class PolicyType(str, Enum):
    MACOS_LARGE_RUNNERS_USAGE = "macos_large_runners"
    REQUIRED_FILE = "required_file"


class Policy(ABC, BaseModel):
    path: str
    name: str | None
    description: str | None

    @property
    @abstractmethod
    def type(self) -> PolicyType: ...

    @property
    def config(self) -> dict[str, Any]:
        return self.model_dump(exclude={"path", "name", "description"})

    @property
    def requires_regular_check(self) -> bool:
        return True

    def merge(self, other: Self) -> Self:
        """
        Returns a copy of this Policy merged with the other.
        """
        copy = self.model_copy()
        copy.path = other.path

        if other.name is not None:
            copy.name = other.name

        if other.description is not None:
            copy.description = other.description

        return copy

    @abstractmethod
    async def evaluate(
        self,
        installation_id: int,
        github_id: str,
        repo_name: str | None = None,
        payload: Any | None = None,
    ) -> None: ...


def read_policy(path: str, content: dict[str, Any]) -> Policy:
    return create_policy(
        content["type"],
        path,
        content.get("name"),
        content.get("description"),
        content["config"],
    )


def create_policy(
    policy_type: PolicyType | str,
    path: str,
    name: str | None,
    description: str | None,
    config: dict[str, Any],
) -> Policy:
    if isinstance(policy_type, str):
        policy_type = PolicyType(policy_type)

    data = config.copy()
    data.update({"name": name, "description": description, "path": path})

    match policy_type:
        case PolicyType.MACOS_LARGE_RUNNERS_USAGE:
            from otterdog.webapp.policies.macos_large_runners import MacOSLargeRunnersUsagePolicy

            return MacOSLargeRunnersUsagePolicy.model_validate(data)

        case PolicyType.REQUIRED_FILE:
            from otterdog.webapp.policies.required_file import RequiredFilePolicy

            return RequiredFilePolicy.model_validate(data)

        case _:
            raise RuntimeError(f"unknown policy type '{policy_type}'")


def create_policy_from_model(model: PolicyModel) -> Policy:
    return create_policy(
        model.id.policy_type,
        model.path,
        model.name,
        model.description,
        model.config,
    )
