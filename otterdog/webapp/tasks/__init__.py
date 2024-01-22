#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from datetime import datetime
from typing import Optional

from quart import current_app

from otterdog.providers.github.rest import RestApi
from otterdog.providers.github.rest.auth import app_auth, token_auth

_APP_REST_API: Optional[RestApi] = None
_INSTALLATION_REST_APIS: dict[str, tuple[RestApi, datetime]] = {}


def _create_rest_api_for_app() -> RestApi:
    github_app_id = current_app.config["GITHUB_APP_ID"]
    github_app_private_key = current_app.config["GITHUB_APP_PRIVATE_KEY"]
    return RestApi(app_auth(github_app_id, github_app_private_key))


def get_rest_api_for_app() -> RestApi:
    global _APP_REST_API

    if _APP_REST_API is None:
        _APP_REST_API = _create_rest_api_for_app()

    return _APP_REST_API


def get_rest_api_for_installation(installation_id: int) -> RestApi:
    global _INSTALLATION_REST_APIS
    installation = str(installation_id)

    current_api, expires_at = _INSTALLATION_REST_APIS.get(installation, (None, datetime.now()))
    if current_api is not None and expires_at is not None:
        if expires_at > datetime.now():
            return current_api

    token, expires_at = get_rest_api_for_app().app.create_installation_access_token(installation)
    rest_api = RestApi(token_auth(token))
    _INSTALLATION_REST_APIS[installation] = (rest_api, expires_at)
    return rest_api
