#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
from dataclasses import dataclass

from otterdog.providers.github.rest import RestApi
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.tasks import InstallationBasedTask, Task


@dataclass(repr=False)
class CheckFileTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    path: str
    content: str
    strict: bool
    branch_prefix: str
    pr_title: str
    pr_body: str

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _execute(self) -> None:
        self.logger.info(
            "checking file '%s' in repo '%s/%s'",
            self.path,
            self.org_id,
            self.repo_name,
        )

        rest_api = await self.rest_api

        try:
            content = await rest_api.content.get_content(self.org_id, self.repo_name, self.path)
            if self.strict is False or self.content == content:
                return
        except RuntimeError:
            # file does not exist, so let's create it
            pass

        self.logger.debug(f"creating pull request for required file '{self.path}'")
        await self._create_pull_request_if_necessary(rest_api)

    async def _create_pull_request_if_necessary(self, rest_api: RestApi) -> None:
        default_branch = await rest_api.repo.get_default_branch(self.org_id, self.repo_name)
        file_name = os.path.basename(self.path)
        branch_name = f"otterdog/{self.branch_prefix}/{file_name}"

        try:
            await rest_api.reference.get_branch_reference(self.org_id, self.repo_name, branch_name)
        except RuntimeError:
            # branch does not yet exist, create it
            default_branch_data = await rest_api.reference.get_branch_reference(
                self.org_id,
                self.repo_name,
                default_branch,
            )
            default_branch_sha = default_branch_data["object"]["sha"]

            await rest_api.reference.create_reference(
                self.org_id,
                self.repo_name,
                branch_name,
                default_branch_sha,
            )

        await rest_api.content.update_content(
            self.org_id,
            self.repo_name,
            self.path,
            self.content,
            branch_name,
            f"Updating file {self.path}",
        )

        open_pull_requests = await rest_api.pull_request.get_pull_requests(
            self.org_id, self.repo_name, "open", default_branch
        )

        for pr in open_pull_requests:
            if pr["head"]["ref"] == branch_name:
                self.logger.debug(f"PR#{pr['number']} already exists for branch '{branch_name}', skipping")
                return

        self.logger.debug("creating pull request")

        await rest_api.pull_request.create_pull_request(
            self.org_id,
            self.repo_name,
            self.pr_title,
            branch_name,
            default_branch,
            self.pr_body,
        )

    def __repr__(self) -> str:
        return f"CheckFileTask(repo='{self.org_id}/{self.repo_name}', path='{self.path}')"
