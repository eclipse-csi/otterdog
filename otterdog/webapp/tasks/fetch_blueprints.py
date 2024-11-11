#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

import yaml

from otterdog.providers.github.rest import RestApi
from otterdog.webapp.blueprints import BLUEPRINT_PATH, Blueprint, read_blueprint
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import (
    cleanup_blueprints_of_owner,
    cleanup_blueprints_status_of_owner,
    update_or_create_blueprint,
)
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import is_yaml_file


@dataclass(repr=False)
class FetchBlueprintsTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    global_blueprints: list[Blueprint]

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _execute(self) -> None:
        self.logger.info(
            "fetching blueprints from repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        async with self.get_organization_config() as org_config:
            rest_api = await self.rest_api
            blueprints = await self._fetch_blueprints(rest_api, org_config.config_repo)

            await cleanup_blueprints_of_owner(self.org_id, list(blueprints))
            await cleanup_blueprints_status_of_owner(self.org_id, list(blueprints))

            for blueprint in list(blueprints.values()):
                await update_or_create_blueprint(self.org_id, blueprint)

    async def _fetch_blueprints(self, rest_api: RestApi, repo: str) -> dict[str, Blueprint]:
        config_file_path = BLUEPRINT_PATH
        blueprints = {p.id: p for p in self.global_blueprints}

        try:
            entries = await rest_api.content.get_content_object(self.org_id, repo, config_file_path)
        except RuntimeError:
            entries = []

        for entry in entries:
            path = entry["path"]
            if is_yaml_file(path):
                content = await rest_api.content.get_content(self.org_id, repo, path)
                try:
                    # TODO: do not hardcode the path to the default branch
                    blueprint_path = f"https://github.com/{self.org_id}/{repo}/blob/main/{path}"
                    blueprint = read_blueprint(blueprint_path, yaml.safe_load(content))

                    if blueprint.id in blueprints:
                        self.logger.error(f"duplicate blueprint with id '{blueprint.id}' in path '{path}', skipping")
                    else:
                        blueprints[blueprint.id] = blueprint
                except (KeyError, ValueError, RuntimeError) as ex:
                    self.logger.error(f"failed reading blueprint from path '{path}'", exc_info=ex)

        return blueprints

    def __repr__(self) -> str:
        return f"FetchBlueprintTask(repo='{self.org_id}/{self.repo_name}')"
