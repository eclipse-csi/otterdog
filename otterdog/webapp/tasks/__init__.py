#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import contextlib
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from functools import cached_property
from logging import Logger, getLogger
from typing import Generic, Protocol, TypeVar

import aiofiles

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider, GraphQLClient
from otterdog.providers.github.rest import RestApi
from otterdog.providers.github.stats import RequestStatistics
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
    get_temporary_base_directory,
)

T = TypeVar("T")


class Task(ABC, Generic[T]):
    @cached_property
    def logger(self) -> Logger:
        return getLogger(type(self).__name__)

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
                self._update_task_model(task_model)

            if task_model is not None:
                await finish_task(task_model)

            return result
        except Exception as ex:
            self.logger.exception(f"failed to execute task '{self!r}'", exc_info=ex)
            await self._post_execute(ex)

            if task_model is not None:
                await fail_task(task_model, ex)

            return None
        finally:
            await self._cleanup()

    async def _pre_execute(self) -> None:
        pass

    async def _post_execute(self, result_or_exception: T | Exception) -> None:
        pass

    def _update_task_model(self, task: TaskModel) -> None:
        pass

    @abstractmethod
    async def _execute(self) -> T:
        pass

    async def _cleanup(self) -> None:
        pass

    @abstractmethod
    def __repr__(self) -> str:
        pass


class InstallationBasedTask(Protocol):
    installation_id: int

    __rest_api: RestApi | None = None
    __graphql_api: GraphQLClient | None = None

    __rest_statistics: RequestStatistics | None = None
    __graphql_statistics: RequestStatistics | None = None

    @property
    async def rest_api(self) -> RestApi:
        if self.__rest_api is None:
            self.__rest_api = await get_rest_api_for_installation(self.installation_id)
        return self.__rest_api

    @property
    def rest_statistics(self) -> RequestStatistics:
        if self.__rest_statistics is None:
            self.__rest_statistics = RequestStatistics()
        return self.__rest_statistics

    @property
    def graphql_statistics(self) -> RequestStatistics:
        if self.__graphql_statistics is None:
            self.__graphql_statistics = RequestStatistics()
        return self.__graphql_statistics

    @property
    async def graphql_api(self) -> GraphQLClient:
        if self.__graphql_api is None:
            self.__graphql_api = await get_graphql_api_for_installation(self.installation_id)
        return self.__graphql_api

    def _merge_rest_statistics(self, other: RequestStatistics) -> None:
        self.rest_statistics.merge(other)

    def _merge_graphql_statistics(self, other: RequestStatistics) -> None:
        self.graphql_statistics.merge(other)

    def merge_statistics_from_provider(self, provider: GitHubProvider) -> None:
        self._merge_rest_statistics(provider.rest_api.statistics)
        self._merge_graphql_statistics(provider.graphql_client.statistics)

    def _update_task_model(self, task: TaskModel) -> None:
        if self.__rest_api is not None:
            self._merge_rest_statistics(self.__rest_api.statistics)

        if self.__graphql_api is not None:
            self._merge_graphql_statistics(self.__graphql_api.statistics)

        if self.rest_statistics.total_requests == 0:
            cache_stats = "rest: no requests"
        else:
            cache_stats = (
                f"rest: {self.rest_statistics.cached_responses}/{self.rest_statistics.total_requests} "
                f"request(s) cached"
            )

        if self.rest_statistics.remaining_rate_limit != -1:
            rate_limit = f"rest: {self.rest_statistics.remaining_rate_limit}"
        else:
            rate_limit = "rest: N/A"

        if self.graphql_statistics.total_requests == 0:
            cache_stats += ",\ngraphql: no requests"
        else:
            cache_stats += f",\ngraphql: {self.graphql_statistics.total_requests} request(s)"

        if self.graphql_statistics.remaining_rate_limit != -1:
            rate_limit += f",\ngraphql: {self.graphql_statistics.remaining_rate_limit}"
        else:
            rate_limit += ",\ngraphql: N/A"

        task.cache_stats = cache_stats
        task.rate_limit_remaining = rate_limit

    # Ignore pycharm warning:
    # https://youtrack.jetbrains.com/issue/PY-66517/False-unexpected-argument-with-asynccontextmanager-defined-as-a-method
    @contextlib.asynccontextmanager
    async def get_organization_config(
        self,
        initialize_template: bool = True,
    ) -> AsyncIterator[OrganizationConfig]:
        installation = await get_installation(self.installation_id)
        if installation is None:
            raise RuntimeError(f"failed to find organization config for installation with id '{self.installation_id}'")

        rest_api = await self.rest_api

        async with aiofiles.tempfile.TemporaryDirectory(dir=get_temporary_base_directory()) as work_dir:
            assert rest_api.token is not None
            org_config = await get_organization_config(installation, rest_api.token, work_dir)

            if initialize_template:
                jsonnet_config = org_config.jsonnet_config
                await jsonnet_config.init_template()

            yield org_config

    async def minimize_outdated_comments(
        self,
        org_id: str,
        repo_name: str,
        pull_request_number: int,
        matching_header: str,
    ) -> None:
        graphql_api = await self.graphql_api
        comments = await graphql_api.get_issue_comments(org_id, repo_name, pull_request_number)
        for comment in comments:
            comment_id = comment["id"]
            body = comment["body"]
            is_minimized = comment["isMinimized"]

            if bool(is_minimized) is False and matching_header in body:
                await graphql_api.minimize_comment(comment_id, "OUTDATED")

    async def _cleanup(self) -> None:
        if self.__rest_api is not None:
            await self.__rest_api.close()

        if self.__graphql_api is not None:
            await self.__graphql_api.close()


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
