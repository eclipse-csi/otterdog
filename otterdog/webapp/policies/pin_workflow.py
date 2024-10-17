#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from logging import getLogger

from quart import current_app

from otterdog.models.github_organization import GitHubOrganization
from otterdog.webapp.db.service import get_configuration_by_github_id, get_installation_by_github_id
from otterdog.webapp.policies import Policy, PolicyType, RepoSelector
from otterdog.webapp.tasks.pin_workflow import PinWorkflowTask

logger = getLogger(__name__)


class PinWorkflowPolicy(Policy):
    repo_selector: RepoSelector

    @classmethod
    def policy_type(cls) -> PolicyType:
        return PolicyType.PIN_WORKFLOW

    async def evaluate(self, github_id: str) -> None:
        installation = await get_installation_by_github_id(github_id)
        if installation is None:
            return

        config_data = await get_configuration_by_github_id(github_id)
        if config_data is None:
            return

        github_organization = GitHubOrganization.from_model_data(config_data.config)
        for repo in github_organization.repositories:
            if self.repo_selector.matches(repo):
                logger.debug(f"checking for unpinned workflows in repo '{github_id}/{repo.name}'")

                title = "Pinning workflows"
                body = "This PR has been automatically created by otterdog due to an active policy."

                current_app.add_background_task(
                    PinWorkflowTask(
                        installation.installation_id,
                        github_id,
                        repo.name,
                        title,
                        body,
                    )
                )
