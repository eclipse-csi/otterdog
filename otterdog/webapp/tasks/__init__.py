#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property
from logging import Logger, getLogger
from typing import Generic, Optional, TypeVar, Union

from otterdog.providers.github.rest import RestApi
from otterdog.webapp import mongo
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.utils import get_rest_api_for_installation

logger = getLogger(__name__)

T = TypeVar("T")


class Task(ABC, Generic[T]):
    @cached_property
    def logger(self) -> Logger:
        return getLogger(type(self).__name__)

    @staticmethod
    async def get_rest_api(installation_id: int) -> RestApi:
        return await get_rest_api_for_installation(installation_id)

    @abstractmethod
    def create_task_model(self) -> TaskModel:
        pass

    async def execute(self) -> Optional[T]:
        self.logger.debug(f"executing task '{self!r}'")

        await self._pre_execute()

        task_model = self.create_task_model()
        await mongo.odm.save(task_model)

        try:
            result = await self._execute()
            await self._post_execute(result)

            task_model.status = "success"
            task_model.updated_at = datetime.utcnow()
            await mongo.odm.save(task_model)

            return result
        except RuntimeError as ex:
            self.logger.exception(f"failed to execute task '{self!r}'", exc_info=ex)
            await self._post_execute(ex)

            task_model.status = f"failure: {str(ex)}"
            task_model.updated_at = datetime.utcnow()
            await mongo.odm.save(task_model)

            return None

    async def _pre_execute(self) -> None:
        pass

    async def _post_execute(self, result_or_exception: Union[T, Exception]) -> None:
        pass

    @abstractmethod
    async def _execute(self) -> T:
        pass

    @abstractmethod
    def __repr__(self) -> str:
        pass
