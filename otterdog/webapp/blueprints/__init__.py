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
from logging import Logger, getLogger
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from otterdog.models.github_organization import GitHubOrganization

if TYPE_CHECKING:
    from otterdog.models.repository import Repository
    from otterdog.webapp.db.models import BlueprintModel, ConfigurationModel

BLUEPRINT_PATH = "otterdog/blueprints"


class BlueprintType(str, Enum):
    REQUIRED_FILE = "required_file"
    PIN_WORKFLOW = "pin_workflow"


class Blueprint(ABC, BaseModel):
    id: str
    path: str
    name: str | None
    description: str | None

    @cached_property
    def logger(self) -> Logger:
        return getLogger(type(self).__name__)

    @property
    @abstractmethod
    def type(self) -> BlueprintType: ...

    @property
    def config(self) -> dict[str, Any]:
        return self.model_dump(exclude={"id", "path", "name", "description"})

    @abstractmethod
    def _matches(self, repo: Repository) -> bool: ...

    async def evaluate(self, installation_id: int, github_id: str, recheck: bool = False) -> None:
        from otterdog.webapp.db.models import BlueprintStatus
        from otterdog.webapp.db.service import (
            cleanup_blueprint_status_of_repo,
            find_blueprint_status,
            get_configuration_by_github_id,
        )

        config_data = await get_configuration_by_github_id(github_id)
        if config_data is None:
            return

        github_organization = GitHubOrganization.from_model_data(config_data.config)
        for repo in github_organization.repositories:
            if repo.archived is False and self._matches(repo):
                # if no recheck is requested, only check the repo if it was not checked before
                if recheck is False:
                    blueprint_status_model = await find_blueprint_status(github_id, repo.name, self.id)
                    if blueprint_status_model is not None and blueprint_status_model.status not in (
                        BlueprintStatus.NOT_CHECKED,
                        BlueprintStatus.RECHECK,
                        BlueprintStatus.FAILURE,
                    ):
                        continue

                self.logger.debug(f"checking blueprint with id '{self.id}' in repo '{github_id}/{repo.name}'")
                await self.evaluate_repo(installation_id, github_id, repo.name, config_data)
            else:
                # if a recheck is needed, cleanup status of non-matching repos if they exist
                if recheck:
                    await cleanup_blueprint_status_of_repo(github_id, repo.name, self.id)

    @abstractmethod
    async def evaluate_repo(
        self,
        installation_id: int,
        github_id: str,
        repo_name: str,
        config: ConfigurationModel | None = None,
    ) -> None: ...


def read_blueprint(path: str, content: dict[str, Any]) -> Blueprint:
    return create_blueprint(
        content["type"],
        content["id"],
        path,
        content.get("name"),
        content.get("description"),
        content["config"] if content.get("config") is not None else {},
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

        case BlueprintType.PIN_WORKFLOW:
            from otterdog.webapp.blueprints.pin_workflow import PinWorkflowBlueprint

            return PinWorkflowBlueprint.model_validate(data)

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


class RepoSelector(BaseModel):
    name_pattern: str | list[str]

    @cached_property
    def _pattern(self) -> re.Pattern | None:
        if self.name_pattern is None:
            return None
        elif isinstance(self.name_pattern, str):
            return re.compile(self.name_pattern)
        else:
            return re.compile("|".join(self.name_pattern))

    def matches(self, repo: Repository) -> bool:
        pattern = self._pattern
        if pattern is not None:
            return bool(pattern.fullmatch(repo.name))
        else:
            return False
