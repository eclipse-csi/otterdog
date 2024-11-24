#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from quart import current_app

from otterdog.models.github_organization import GitHubOrganization
from otterdog.webapp.blueprints import Blueprint, BlueprintType
from otterdog.webapp.db.service import get_configuration_by_github_id, get_installation_by_github_id

if TYPE_CHECKING:
    from otterdog.models.repository import Repository
    from otterdog.webapp.db.models import ConfigurationModel
    from otterdog.webapp.webhook.github_models import Commit


class AppendConfigurationBlueprint(Blueprint):
    condition: str
    content: str

    @property
    def type(self) -> BlueprintType:
        return BlueprintType.APPEND_CONFIGURATION

    async def _get_repositories(self, config_model: ConfigurationModel) -> list[Repository]:
        installation_model = await get_installation_by_github_id(config_model.github_id)
        if installation_model is not None and installation_model.config_repo is not None:
            github_organization = GitHubOrganization.from_model_data(config_model.config)
            repo = github_organization.get_repository(installation_model.config_repo)
            if repo is not None:
                return [repo]

        return []

    def _matches(self, repo: Repository) -> bool:
        return True

    def should_reevaluate(self, commits: list[Commit]) -> bool:
        from otterdog.webapp.webhook.github_models import touched_by_commits

        def is_configuration_path(path: str) -> bool:
            return path.startswith("otterdog/") and path.endswith(".jsonnet")

        return touched_by_commits(is_configuration_path, commits)

    async def evaluate_repo(
        self,
        installation_id: int,
        github_id: str,
        repo_name: str,
        config: ConfigurationModel | None = None,
    ) -> None:
        from otterdog.webapp.tasks.blueprints.append_configuration import AppendConfigurationTask

        config_model = await get_configuration_by_github_id(github_id) if config is None else config
        if config_model is None:
            self.logger.warning(
                f"evaluating_repo for blueprint with id '{self.id}': no configuration found for github_id '{github_id}'"
            )
            return

        current_app.add_background_task(
            AppendConfigurationTask(
                installation_id,
                github_id,
                repo_name,
                self,
                config_model,
            )
        )
