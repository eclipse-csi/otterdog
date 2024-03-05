#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import os.path
import re
import sys
from datetime import datetime, timedelta
from functools import cache
from logging import getLogger
from typing import cast

from hypercorn.logging import Logger as HypercornLogger
from hypercorn.typing import ResponseSummary, WWWScope
from quart import Quart, current_app
from quart_redis import get_redis  # type: ignore

from otterdog.config import OtterdogConfig
from otterdog.providers.github.auth import app_auth, token_auth
from otterdog.providers.github.cache.redis import redis_cache
from otterdog.providers.github.graphql import GraphQLClient
from otterdog.providers.github.rest import RestApi

logger = getLogger(__name__)

_OTTERDOG_CONFIG: OtterdogConfig | None = None
_CREATE_INSTALLATION_TOKEN_LOCK = asyncio.Lock()


def _get_redis_cache():
    return redis_cache(current_app.config["REDIS_URI"], get_redis())


async def close_rest_apis():
    app_api_cache = get_rest_api_for_app.cache_info()
    if app_api_cache.hits > 0:
        logger.debug("closing rest api for app")
        await get_rest_api_for_app().close()


@cache
def get_rest_api_for_app() -> RestApi:
    logger.debug("creating rest api for app")
    github_app_id = current_app.config["GITHUB_APP_ID"]
    github_app_private_key = current_app.config["GITHUB_APP_PRIVATE_KEY"]
    return RestApi(app_auth(github_app_id, github_app_private_key), _get_redis_cache())


async def get_token_for_installation(installation_id: int) -> tuple[str, datetime]:
    redis = get_redis()

    async with _CREATE_INSTALLATION_TOKEN_LOCK:
        installation_key = f"token:{installation_id}"
        current_data = decode_bytes_dict(await redis.hgetall(installation_key))

        cached_token = current_data.get("token", None)
        expires_at_str = current_data.get("expires_at", None)

        if cached_token is not None and expires_at_str is not None:
            expires_at = datetime.fromisoformat(expires_at_str)
            # add a buffer of 1 min for expiration to be safe
            # the assumption is that any processing using the returned token
            # will not take longer than 1 min (in fact will be much shorter)
            if expires_at > (current_utc_time() + timedelta(minutes=1)):
                logger.info(
                    f"re-using installation token for installation '{installation_id}' expiring at '{expires_at}'"
                )
                return cached_token, expires_at

        logger.info(f"creating new installation token for installation '{installation_id}'")
        token, expires_at = await get_rest_api_for_app().app.create_installation_access_token(str(installation_id))
        await redis.hset(
            installation_key,
            mapping={"token": token, "expires_at": expires_at.isoformat()},
        )
        return token, expires_at


def decode_bytes_dict(data: dict[bytes, bytes]) -> dict[str, str]:
    return {k.decode("utf-8"): v.decode("utf-8") for k, v in data.items()}


async def get_rest_api_for_installation(installation_id: int) -> RestApi:
    token, _ = await get_token_for_installation(installation_id)
    return RestApi(token_auth(token), _get_redis_cache())


async def get_graphql_api_for_installation(installation_id: int) -> GraphQLClient:
    token, _ = await get_token_for_installation(installation_id)
    return GraphQLClient(token_auth(token))


def get_app_root_directory(app: Quart | None = None) -> str:
    config = app.config if app is not None else current_app.config
    return config["APP_ROOT"]


def get_db_root_directory(app: Quart | None = None) -> str:
    config = app.config if app is not None else current_app.config
    return config["DB_ROOT"]


@cache
def get_temporary_base_directory(app: Quart | None = None) -> str:
    return os.path.join(get_app_root_directory(app), "tmp")


async def get_otterdog_config() -> OtterdogConfig:
    global _OTTERDOG_CONFIG

    if _OTTERDOG_CONFIG is None:
        _OTTERDOG_CONFIG = await _load_otterdog_config()

    return _OTTERDOG_CONFIG


async def refresh_otterdog_config(sha: str | None = None) -> OtterdogConfig:
    global _OTTERDOG_CONFIG
    _OTTERDOG_CONFIG = await _load_otterdog_config(sha)
    return _OTTERDOG_CONFIG


async def _load_otterdog_config(ref: str | None = None) -> OtterdogConfig:
    app_root = current_app.config["APP_ROOT"]
    config_file_owner = current_app.config["OTTERDOG_CONFIG_OWNER"]
    config_file_repo = current_app.config["OTTERDOG_CONFIG_REPO"]
    config_file_path = current_app.config["OTTERDOG_CONFIG_PATH"]

    logger.info(
        f"loading otterdog config from url "
        f"'https://github.com/{config_file_owner}/{config_file_repo}/{config_file_path}'"
    )

    async with RestApi(token_auth(current_app.config["OTTERDOG_CONFIG_TOKEN"]), _get_redis_cache()) as rest_api:
        content = await rest_api.content.get_content(config_file_owner, config_file_repo, config_file_path, ref)
        import aiofiles

        async with aiofiles.tempfile.NamedTemporaryFile("wt") as file:
            name = cast(str, file.name)
            await file.write(content)
            await file.flush()
            return OtterdogConfig(name, False, app_root)


def get_admin_team() -> str:
    return current_app.config["GITHUB_ADMIN_TEAM"]


async def fetch_config_from_github(
    rest_api: RestApi,
    org_id: str,
    owner: str,
    repo: str,
    filename: str,
    ref: str | None = None,
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


def current_utc_time() -> datetime:
    if sys.version_info < (3, 12):
        return datetime.utcnow()
    else:
        from datetime import UTC

        return datetime.now(UTC)
