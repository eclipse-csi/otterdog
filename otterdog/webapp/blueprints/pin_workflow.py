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

from otterdog.webapp.blueprints import Blueprint, BlueprintType, RepoSelector

if TYPE_CHECKING:
    from otterdog.models.repository import Repository
    from otterdog.webapp.db.models import ConfigurationModel
    from otterdog.webapp.webhook.github_models import Commit


class PinWorkflowBlueprint(Blueprint):
    repo_selector: RepoSelector | None = None

    @property
    def type(self) -> BlueprintType:
        return BlueprintType.PIN_WORKFLOW

    def _matches(self, repo: Repository) -> bool:
        if self.repo_selector is None:
            return True
        else:
            return self.repo_selector.matches(repo)

    def should_reevaluate(self, commits: list[Commit]) -> bool:
        from otterdog.webapp.webhook.github_models import touched_by_commits

        def is_workflow_path(path: str) -> bool:
            return path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))

        return touched_by_commits(is_workflow_path, commits)

    async def evaluate_repo(
        self,
        installation_id: int,
        github_id: str,
        repo_name: str,
        config: ConfigurationModel | None = None,
    ) -> None:
        from otterdog.webapp.tasks.blueprints.pin_workflow import PinWorkflowTask

        current_app.add_background_task(
            PinWorkflowTask(
                installation_id,
                github_id,
                repo_name,
                self,
            )
        )
