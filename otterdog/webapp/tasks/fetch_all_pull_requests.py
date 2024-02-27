#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from otterdog.webapp.db.models import ApplyStatus, TaskModel
from otterdog.webapp.db.service import update_or_create_pull_request
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.webhook.github_models import PullRequest


@dataclass(repr=False)
class FetchAllPullRequestsTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _pre_execute(self) -> None:
        self.logger.info(
            "fetching all pull requests from repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

    async def _execute(self) -> None:
        rest_api = await self.rest_api

        all_pull_requests = await rest_api.pull_request.get_pull_requests(
            self.org_id, self.repo_name, state="all", base_ref="main"
        )

        for pr in all_pull_requests:
            pr_from_github = PullRequest.model_validate(pr)

            # when importing already closed PRs we consider them being applied already
            pr_status = pr_from_github.get_pr_status()
            apply_status = ApplyStatus.COMPLETED if pr_status == "MERGED" else None

            await update_or_create_pull_request(
                self.org_id,
                self.repo_name,
                pr_from_github,
                apply_status=apply_status,
            )

    def __repr__(self) -> str:
        return f"FetchAllPullRequestsTask(repo={self.org_id}/{self.repo_name})"
