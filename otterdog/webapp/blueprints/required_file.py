#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import re
from functools import cached_property
from logging import getLogger
from typing import TYPE_CHECKING

from pydantic import BaseModel
from quart import current_app

from otterdog.models.github_organization import GitHubOrganization
from otterdog.webapp.blueprints import Blueprint, BlueprintType
from otterdog.webapp.db.service import get_configuration_by_github_id

if TYPE_CHECKING:
    from otterdog.models.repository import Repository

logger = getLogger(__name__)


class RepoSelector(BaseModel):
    name_pattern: str | list[str] | None

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


class RequiredFile(BaseModel):
    path: str
    content: str
    strict: bool = False


class RequiredFileBlueprint(Blueprint):
    repo_selector: RepoSelector
    files: list[RequiredFile]

    @property
    def type(self) -> BlueprintType:
        return BlueprintType.REQUIRED_FILE

    async def evaluate(self, installation_id: int, github_id: str) -> None:
        config_data = await get_configuration_by_github_id(github_id)
        if config_data is None:
            return

        github_organization = GitHubOrganization.from_model_data(config_data.config)
        for repo in github_organization.repositories:
            if repo.archived is False and self.repo_selector.matches(repo):
                logger.debug(
                    f"checking for required files of blueprint with id '{self.id}' in repo '{github_id}/{repo.name}'"
                )

                from otterdog.webapp.tasks.check_files import CheckFilesTask

                current_app.add_background_task(
                    CheckFilesTask(
                        installation_id,
                        github_id,
                        repo.name,
                        self,
                    )
                )
