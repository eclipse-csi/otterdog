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
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from otterdog.webapp.db.models import BlueprintModel


BLUEPRINT_PATH = "otterdog/blueprints"


class BlueprintType(str, Enum):
    REQUIRED_FILE = "required_file"


class Blueprint(ABC, BaseModel):
    id: str
    path: str
    name: str | None
    description: str | None

    @property
    @abstractmethod
    def type(self) -> BlueprintType: ...

    @property
    def config(self) -> dict[str, Any]:
        return self.model_dump(exclude={"path", "name", "description"})

    @abstractmethod
    async def evaluate(self, installation_id: int, github_id: str) -> None: ...


def read_blueprint(path: str, content: dict[str, Any]) -> Blueprint:
    return create_blueprint(
        content["type"],
        content["id"],
        path,
        content["name"],
        content.get("description"),
        content["config"],
    )


def create_blueprint(
    blueprint_type: BlueprintType | str,
    blueprint_id: str,
    path: str,
    name: str | None,
    description: str | None,
    config: dict[str, Any],
) -> Blueprint:
    if isinstance(blueprint_type, str):
        blueprint_type = BlueprintType(blueprint_type)

    data = config.copy()
    data.update(
        {
            "id": blueprint_id,
            "name": name,
            "description": description,
            "path": path,
        }
    )

    match blueprint_type:
        case BlueprintType.REQUIRED_FILE:
            from otterdog.webapp.blueprints.required_file import RequiredFileBlueprint

            return RequiredFileBlueprint.model_validate(data)

        case _:
            raise RuntimeError(f"unknown blueprint type '{blueprint_type}'")


def create_blueprint_from_model(model: BlueprintModel) -> Blueprint:
    return create_blueprint(
        model.id.blueprint_type,
        model.id.blueprint_id,
        model.path,
        model.name,
        model.description,
        model.config,
    )


def is_blueprint_path(path: str) -> bool:
    from otterdog.webapp.utils import is_yaml_file

    return path.startswith(BLUEPRINT_PATH) and is_yaml_file(path)
