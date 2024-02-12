#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from functools import cached_property
from logging import Logger, getLogger
from typing import AsyncIterator, Generic, Optional, TypeVar, Union

import aiofiles

from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.providers.github.rest import RestApi
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import (
    create_task,
    fail_task,
    finish_task,
    get_installation,
)
from otterdog.webapp.utils import get_organization_config, get_rest_api_for_installation

logger = getLogger(__name__)

T = TypeVar("T")


class Task(ABC, Generic[T]):
    @cached_property
    def logger(self) -> Logger:
        return getLogger(type(self).__name__)

    @staticmethod
    async def get_rest_api(installation_id: int) -> RestApi:
        return await get_rest_api_for_installation(installation_id)

    def create_task_model(self) -> Optional[TaskModel]:
        return None

    async def __call__(self, *args, **kwargs):
        await self.execute()

    async def execute(self) -> Optional[T]:
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
        except RuntimeError as ex:
            self.logger.exception(f"failed to execute task '{self!r}'", exc_info=ex)
            await self._post_execute(ex)

            if task_model is not None:
                await fail_task(task_model, ex)

            return None

    async def _pre_execute(self) -> None:
        pass

    async def _post_execute(self, result_or_exception: Union[T, Exception]) -> None:
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

    @abstractmethod
    def __repr__(self) -> str:
        pass
