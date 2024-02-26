#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses

from otterdog.utils import jsonnet_evaluate_file
from otterdog.webapp.db.models import ConfigurationModel, TaskModel
from otterdog.webapp.db.service import save_config
from otterdog.webapp.tasks import Task
from otterdog.webapp.utils import fetch_config_from_github


@dataclasses.dataclass(repr=False)
class FetchConfigTask(Task[None]):
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
            "fetching latest config from repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

    async def _execute(self) -> None:
        rest_api = await self.get_rest_api(self.installation_id)

        async with self.get_organization_config(rest_api, self.installation_id) as org_config:
            config_file = org_config.jsonnet_config.org_config_file
            sha = await fetch_config_from_github(
                rest_api,
                self.org_id,
                self.org_id,
                org_config.config_repo,
                config_file,
            )

            config_data = jsonnet_evaluate_file(config_file)
            config = ConfigurationModel(  # type: ignore
                github_id=self.org_id,
                project_name=org_config.name,
                config=config_data,
                sha=sha,
            )
            await save_config(config)

    def __repr__(self) -> str:
        return f"FetchConfigTask(repo={self.org_id}/{self.repo_name})"
