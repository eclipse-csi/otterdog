#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cached_property
from logging import Logger, getLogger
from typing import Generic, TypeVar

import aiofiles

from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.providers.github.rest import RestApi
from otterdog.webapp.db.models import InstallationModel, TaskModel
from otterdog.webapp.db.service import (
    create_task,
    fail_task,
    finish_task,
    get_installation,
)
from otterdog.webapp.utils import (
    get_graphql_api_for_installation,
    get_rest_api_for_installation,
)

logger = getLogger(__name__)

T = TypeVar("T")


class Task(ABC, Generic[T]):
    @cached_property
    def logger(self) -> Logger:
        return getLogger(type(self).__name__)

    @staticmethod
    async def get_rest_api(installation_id: int) -> RestApi:
        return await get_rest_api_for_installation(installation_id)

    def create_task_model(self) -> TaskModel | None:
        return None

    async def __call__(self, *args, **kwargs):
        await self.execute()

    async def execute(self) -> T | None:
        self.logger.debug(f"executing task '{self!r}'")

        task_model = self.create_task_model()
        if task_model is not None:
            await create_task(task_model)

        try:
            await self._pre_execute()

            result = await self._execute()
            await self._post_execute(result)

            if task_model is not None:
                await finish_task(task_model)

            return result
        except Exception as ex:
            self.logger.exception(f"failed to execute task '{self!r}'", exc_info=ex)
            await self._post_execute(ex)

            if task_model is not None:
                await fail_task(task_model, ex)

            return None

    async def _pre_execute(self) -> None:
        pass

    async def _post_execute(self, result_or_exception: T | Exception) -> None:
        pass

    @abstractmethod
    async def _execute(self) -> T:
        pass

    # Ignore pycharm warning:
    # https://youtrack.jetbrains.com/issue/PY-66517/False-unexpected-argument-with-asynccontextmanager-defined-as-a-method
    @asynccontextmanager
    async def get_organization_config(
        self, otterdog_config: OtterdogConfig, rest_api: RestApi, installation_id: int, initialize_template: bool = True
    ) -> AsyncIterator[OrganizationConfig]:
        installation = await get_installation(installation_id)
        if installation is None:
            raise RuntimeError(f"failed to find organization config for installation with id '{installation_id}'")

        async with aiofiles.tempfile.TemporaryDirectory(dir=otterdog_config.jsonnet_base_dir) as work_dir:
            assert rest_api.token is not None
            org_config = await get_organization_config(installation, rest_api.token, work_dir)

            if initialize_template:
                jsonnet_config = org_config.jsonnet_config
                await jsonnet_config.init_template()

            yield org_config

    @staticmethod
    async def minimize_outdated_comments(
        installation_id: int,
        org_id: str,
        repo_name: str,
        pull_request_number: int,
        matching_header: str,
    ) -> None:
        graphql_api = await get_graphql_api_for_installation(installation_id)
        comments = await graphql_api.get_issue_comments(org_id, repo_name, pull_request_number)
        for comment in comments:
            comment_id = comment["id"]
            body = comment["body"]
            is_minimized = comment["isMinimized"]

            if bool(is_minimized) is False and matching_header in body:
                await graphql_api.minimize_comment(comment_id, "OUTDATED")

    @abstractmethod
    def __repr__(self) -> str:
        pass


async def get_organization_config(org_model: InstallationModel, token: str, work_dir: str) -> OrganizationConfig:
    assert org_model.project_name is not None
    assert org_model.config_repo is not None
    assert org_model.base_template is not None

    return OrganizationConfig.of(
        org_model.project_name,
        org_model.github_id,
        org_model.config_repo,
        org_model.base_template,
        {"provider": "inmemory", "api_token": token},
        work_dir,
    )
