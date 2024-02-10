#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses

import aiofiles

from otterdog.utils import jsonnet_evaluate_file
from otterdog.webapp import mongo
from otterdog.webapp.db.models import ConfigurationModel
from otterdog.webapp.db.service import get_installation
from otterdog.webapp.tasks import Task
from otterdog.webapp.utils import (
    fetch_config,
    get_organization_config,
    get_otterdog_config,
)


@dataclasses.dataclass(repr=False)
class FetchConfigTask(Task[None]):
    installation_id: int
    org_id: str
    repo_name: str

    async def _pre_execute(self) -> None:
        self.logger.info(
            "fetching latest config from repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

    async def _execute(self) -> None:
        otterdog_config = await get_otterdog_config()

        installation = await get_installation(self.installation_id)
        if installation is None:
            raise RuntimeError(f"failed to find organization config for installation with id '{self.installation_id}'")

        rest_api = await self.get_rest_api(self.installation_id)

        async with aiofiles.tempfile.TemporaryDirectory(dir=otterdog_config.jsonnet_base_dir) as work_dir:
            assert rest_api.token is not None
            org_config = await get_organization_config(installation, rest_api.token, work_dir)

            jsonnet_config = org_config.jsonnet_config
            await jsonnet_config.init_template()

            config_file = jsonnet_config.org_config_file
            sha = await fetch_config(
                rest_api,
                self.org_id,
                self.org_id,
                org_config.config_repo,
                config_file,
            )

            config_data = jsonnet_evaluate_file(config_file)
            model = ConfigurationModel(  # type: ignore
                github_id=self.org_id,
                project_name=installation.project_name,
                config=config_data,
                sha=sha,
            )
            await mongo.odm.save(model)

    def __repr__(self) -> str:
        return f"FetchConfigTask(repo={self.org_id}/{self.repo_name})"
