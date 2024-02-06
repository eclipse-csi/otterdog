#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from abc import ABC, abstractmethod
from functools import cached_property
from logging import Logger, getLogger
from typing import Generic, Optional, TypeVar, Union

from otterdog.providers.github.rest import RestApi
from otterdog.webapp import db
from otterdog.webapp.db.models import DBTask
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
    def create_db_task(self) -> DBTask:
        pass

    async def execute(self) -> Optional[T]:
        self.logger.debug(f"executing task '{self!r}'")

        await self._pre_execute()

        db_task = self.create_db_task()
        db.session.add(db_task)
        db.session.commit()

        try:
            result = await self._execute()
            await self._post_execute(result)

            db_task.status = "success"
            db.session.commit()

            return result
        except RuntimeError as ex:
            self.logger.exception(f"failed to execute task '{self!r}'", exc_info=ex)
            await self._post_execute(ex)

            db_task.status = f"failure: {str(ex)}"
            db.session.commit()

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
