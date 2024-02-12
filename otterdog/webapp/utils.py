#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************
import asyncio
import re
from datetime import datetime
from logging import getLogger
from typing import Optional, cast

from hypercorn.logging import Logger as HypercornLogger
from hypercorn.typing import ResponseSummary, WWWScope
from quart import current_app

from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.providers.github.auth import app_auth, token_auth
from otterdog.providers.github.rest import RestApi
from otterdog.webapp.db.models import InstallationModel

logger = getLogger(__name__)

_APP_REST_API: Optional[RestApi] = None
_INSTALLATION_REST_APIS: dict[str, tuple[RestApi, datetime]] = {}
_REST_APIS_LOCK = asyncio.Lock()

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
    global _INSTALLATION_REST_APIS, _REST_APIS_LOCK
    installation = str(installation_id)

    async with _REST_APIS_LOCK:
        current_api, expires_at = _INSTALLATION_REST_APIS.get(installation, (None, datetime.now()))

        if current_api is not None and expires_at is not None:
            if expires_at > datetime.now():
                return current_api
            else:
                await current_api.close()

        token, expires_at = await get_rest_api_for_app().app.create_installation_access_token(installation)
        rest_api = RestApi(token_auth(token))
        _INSTALLATION_REST_APIS[installation] = (rest_api, expires_at)
        return rest_api


async def get_otterdog_config() -> OtterdogConfig:
    global _OTTERDOG_CONFIG

    if _OTTERDOG_CONFIG is None:
        _OTTERDOG_CONFIG = await _load_otterdog_config()

    return _OTTERDOG_CONFIG


async def refresh_otterdog_config(sha: str):
    global _OTTERDOG_CONFIG
    _OTTERDOG_CONFIG = await _load_otterdog_config(sha)


async def _load_otterdog_config(ref: Optional[str] = None) -> OtterdogConfig:
    app_root = current_app.config["APP_ROOT"]
    config_file_owner = current_app.config["OTTERDOG_CONFIG_OWNER"]
    config_file_repo = current_app.config["OTTERDOG_CONFIG_REPO"]
    config_file_path = current_app.config["OTTERDOG_CONFIG_PATH"]

    logger.info(
        f"loading otterdog config from url "
        f"'https://github.com/{config_file_owner}/{config_file_repo}/{config_file_path}'"
    )

    async with RestApi(token_auth(current_app.config["OTTERDOG_CONFIG_TOKEN"])) as rest_api:
        content = await rest_api.content.get_content(config_file_owner, config_file_repo, config_file_path, ref)
        import aiofiles

        async with aiofiles.tempfile.NamedTemporaryFile("wt") as file:
            name = cast(str, file.name)
            await file.write(content)
            await file.flush()
            return OtterdogConfig(name, False, app_root)


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


async def fetch_config_from_github(
    rest_api: RestApi,
    org_id: str,
    owner: str,
    repo: str,
    filename: str,
    ref: Optional[str] = None,
) -> str:
    path = f"otterdog/{org_id}.jsonnet"
    content, sha = await rest_api.content.get_content_with_sha(
        owner,
        repo,
        path,
        ref,
    )

    import aiofiles

    async with aiofiles.open(filename, "w") as file:
        await file.write(content)

    return sha


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
