#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from quart import render_template

from otterdog.webapp.db.models import BlueprintStatus, TaskModel
from otterdog.webapp.db.service import (
    find_blueprint_status_by_pr,
    save_blueprint_status,
)
from otterdog.webapp.tasks import (
    InstallationBasedTask,
    Task,
)
from otterdog.webapp.webhook.github_models import PullRequest


@dataclass(repr=False)
class UpdateBlueprintStatusTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    pull_request: PullRequest

    @property
    def pull_request_number(self) -> int:
        return self.pull_request.number

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _execute(self) -> None:
        blueprint_status = await find_blueprint_status_by_pr(self.org_id, self.repo_name, self.pull_request.number)
        if blueprint_status is not None:
            self.logger.info(
                "updating status for blueprint id '%s' of repo '%s/%s'",
                blueprint_status.id.blueprint_id,
                self.org_id,
                self.repo_name,
            )

            if self.pull_request.state == "open":
                # reinstate checks for this blueprint id / repo combination
                blueprint_status.status = BlueprintStatus.REMEDIATION_PREPARED
            else:
                if self.pull_request.merged is True:
                    blueprint_status.status = BlueprintStatus.RECHECK
                    blueprint_status.remediation_pr = None
                elif self.pull_request.merged is False:
                    blueprint_status.status = BlueprintStatus.DISMISSED
                    await self._add_comment_to_pr(blueprint_status.id.blueprint_id)

            await save_blueprint_status(blueprint_status)

    async def _add_comment_to_pr(self, blueprint_id: str) -> None:
        comment = await render_template(
            "comment/dismissal_comment.txt",
            blueprint_id=blueprint_id,
        )

        await self.minimize_outdated_comments(
            self.org_id,
            self.repo_name,
            self.pull_request_number,
            "<!-- Otterdog Comment: blueprint-dismissal -->",
        )

        # add a comment about dismissal to the PR
        rest_api = await self.rest_api
        await rest_api.issue.create_comment(
            self.org_id,
            self.repo_name,
            str(self.pull_request_number),
            comment,
        )

    def __repr__(self) -> str:
        return (
            f"UpdateBlueprintStatusTask(repo={self.org_id}/{self.repo_name}, pull_request=#{self.pull_request_number})"
        )
