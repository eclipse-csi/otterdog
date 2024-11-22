#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from pydantic import BaseModel
from quart import current_app

from otterdog.webapp.blueprints import Blueprint, BlueprintType, RepoSelector
from otterdog.webapp.db.service import get_configuration_by_github_id

if TYPE_CHECKING:
    from otterdog.models.repository import Repository
    from otterdog.webapp.db.models import ConfigurationModel
    from otterdog.webapp.webhook.github_models import Commit


class RequiredFile(BaseModel):
    path: str
    content: str
    strict: bool = False


class RequiredFileBlueprint(Blueprint):
    repo_selector: RepoSelector | None = None
    files: list[RequiredFile]

    @property
    def type(self) -> BlueprintType:
        return BlueprintType.REQUIRED_FILE

    @cached_property
    def required_paths(self) -> list[str]:
        return [x.path for x in self.files]

    def _matches(self, repo: Repository) -> bool:
        if self.repo_selector is None:
            return True
        else:
            return self.repo_selector.matches(repo)

    def should_reevaluate(self, commits: list[Commit]) -> bool:
        from otterdog.webapp.webhook.github_models import touched_by_commits

        def is_required_path(path: str) -> bool:
            return path in self.required_paths

        return touched_by_commits(is_required_path, commits)

    async def evaluate_repo(
        self,
        installation_id: int,
        github_id: str,
        repo_name: str,
        config: ConfigurationModel | None = None,
    ) -> None:
        from otterdog.webapp.tasks.blueprints.check_files import CheckFilesTask

        config_model = await get_configuration_by_github_id(github_id) if config is None else config
        assert config_model is not None

        current_app.add_background_task(
            CheckFilesTask(
                installation_id,
                github_id,
                repo_name,
                self,
                config_model,
            )
        )
