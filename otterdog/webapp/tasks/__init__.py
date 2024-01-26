#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os.path
from datetime import datetime
from logging import getLogger
from typing import Optional

from quart import current_app

from otterdog.config import OtterdogConfig
from otterdog.providers.github.auth import app_auth, token_auth
from otterdog.providers.github.rest import RestApi

_APP_REST_API: Optional[RestApi] = None
_INSTALLATION_REST_APIS: dict[str, tuple[RestApi, datetime]] = {}

_OTTERDOG_CONFIG: Optional[OtterdogConfig] = None

logger = getLogger(__name__)


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
        _OTTERDOG_CONFIG = load_otterdog_config()

    return _OTTERDOG_CONFIG


def load_otterdog_config() -> OtterdogConfig:
    app_root = current_app.config["APP_ROOT"]
    config_file_url = current_app.config["OTTERDOG_CONFIG_URL"]

    import requests

    with requests.get(config_file_url) as response:
        config_file = os.path.join(app_root, "otterdog.json")
        logger.info(f"writing otterdog configuration to '{config_file}'")
        with open(config_file, "w") as file:
            file.write(response.text)

    return OtterdogConfig(config_file, False, app_root)
