#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os.path
import re
from datetime import datetime
from logging import getLogger
from typing import Optional

from hypercorn.logging import Logger as HypercornLogger
from hypercorn.typing import ResponseSummary, WWWScope
from quart import current_app

from otterdog.config import OtterdogConfig
from otterdog.providers.github.auth import app_auth, token_auth
from otterdog.providers.github.rest import RestApi

logger = getLogger(__name__)

_APP_REST_API: Optional[RestApi] = None
_INSTALLATION_REST_APIS: dict[str, tuple[RestApi, datetime]] = {}

_OTTERDOG_CONFIG: Optional[OtterdogConfig] = None


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


async def fetch_config(rest_api: RestApi, org_id: str, owner: str, repo: str, filename: str, ref: str):
    path = f"otterdog/{org_id}.jsonnet"
    content = await rest_api.content.get_content(
        owner,
        repo,
        path,
        ref,
    )
    with open(filename, "w") as file:
        file.write(content)


def escape_for_github(text: str) -> str:
    lines = text.splitlines()

    output = []
    for line in lines:
        ansi_escape = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]")
        line = ansi_escape.sub("", line)

        diff_escape = re.compile(r"(\s+)([-+!])(\s+)")
        line = diff_escape.sub(r"\g<2>\g<1>", line)

        diff_escape2 = re.compile(r"(\s+)(~)")
        line = diff_escape2.sub(r"!\g<1>", line)

        output.append(line)

    return "\n".join(output)


class SaneLogger(HypercornLogger):
    """
    A custom logger to prevent duplicate access log entries:
    https://github.com/pgjones/hypercorn/issues/158
    """

    async def access(self, request: WWWScope, response: ResponseSummary, request_time: float) -> None:
        if response is not None:
            await super().access(request, response, request_time)
