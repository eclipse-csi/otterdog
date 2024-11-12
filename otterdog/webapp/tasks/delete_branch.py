#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.tasks import InstallationBasedTask, Task


@dataclass(repr=False)
class DeleteBranchTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    ref: str

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _execute(self) -> None:
        self.logger.info(
            "deleting ref '%s' in repo '%s/%s'",
            self.ref,
            self.org_id,
            self.repo_name,
        )

        rest_api = await self.rest_api
        await rest_api.reference.delete_reference(self.org_id, self.repo_name, self.ref)
        self.logger.debug(f"deleted branch '{self.ref}' in repo '{self.org_id}/{self.repo_name}'")

    def __repr__(self) -> str:
        return f"DeleteBranchTask(repo='{self.org_id}/{self.repo_name}', ref='{self.ref}')"
