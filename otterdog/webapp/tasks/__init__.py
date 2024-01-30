#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os.path
from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property
from logging import Logger, getLogger
from typing import Generic, Optional, TypeVar, Union

from quart import current_app

from otterdog.config import OtterdogConfig
from otterdog.providers.github.auth import app_auth, token_auth
from otterdog.providers.github.rest import RestApi

_APP_REST_API: Optional[RestApi] = None
_INSTALLATION_REST_APIS: dict[str, tuple[RestApi, datetime]] = {}

_OTTERDOG_CONFIG: Optional[OtterdogConfig] = None

logger = getLogger(__name__)

T = TypeVar("T")


class Task(ABC, Generic[T]):
    @cached_property
    def logger(self) -> Logger:
        return getLogger(type(self).__name__)

    @staticmethod
    async def get_rest_api(installation_id: int) -> RestApi:
        return await get_rest_api_for_installation(installation_id)

    async def execute(self) -> Optional[T]:
        self.logger.debug(f"executing task '{self!r}'")

        await self._pre_execute()

        try:
            result = await self._execute()
            await self._post_execute(result)
            return result
        except RuntimeError as ex:
            self.logger.exception(f"failed to execute task '{self!r}'", exc_info=ex)
            await self._post_execute(ex)
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


def _create_rest_api_for_app() -> RestApi:
    github_app_id = current_app.config["GITHUB_APP_ID"]
    github_app_private_key = current_app.config["GITHUB_APP_PRIVATE_KEY"]
    return RestApi(app_auth(github_app_id, github_app_private_key))


def get_rest_api_for_app() -> RestApi:
    global _APP_REST_API

    if _APP_REST_API is None:
        _APP_REST_API = _create_rest_api_for_app()

    return _APP_REST_API


async def get_rest_api_for_installation(installation_id: int) -> RestApi:
    global _INSTALLATION_REST_APIS
    installation = str(installation_id)

    current_api, expires_at = _INSTALLATION_REST_APIS.get(installation, (None, datetime.now()))
    if current_api is not None and expires_at is not None:
        if expires_at > datetime.now():
            return current_api

    token, expires_at = await get_rest_api_for_app().app.create_installation_access_token(installation)
    rest_api = RestApi(token_auth(token))
    _INSTALLATION_REST_APIS[installation] = (rest_api, expires_at)
    return rest_api


def get_otterdog_config() -> OtterdogConfig:
    global _OTTERDOG_CONFIG

    if _OTTERDOG_CONFIG is None:
        _OTTERDOG_CONFIG = _load_otterdog_config()

    return _OTTERDOG_CONFIG


def refresh_otterdog_config():
    global _OTTERDOG_CONFIG
    _OTTERDOG_CONFIG = _load_otterdog_config()


def _load_otterdog_config() -> OtterdogConfig:
    app_root = current_app.config["APP_ROOT"]
    config_file_url = current_app.config["OTTERDOG_CONFIG_URL"]

    logger.info(f"loading otterdog config from url '{config_file_url}'")

    import requests

    with requests.get(config_file_url) as response:
        config_file = os.path.join(app_root, "otterdog.json")
        with open(config_file, "w") as file:
            file.write(response.text)

    return OtterdogConfig(config_file, False, app_root)
