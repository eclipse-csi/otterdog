#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import json
import re
import sys
from datetime import datetime, timedelta
from functools import cache
from logging import getLogger
from typing import cast

import yaml
from quart import Quart, current_app
from quart_redis import get_redis  # type: ignore

from otterdog.cache import get_github_cache
from otterdog.config import OtterdogConfig
from otterdog.providers.github.auth import app_auth, token_auth
from otterdog.providers.github.cache.ghproxy import ghproxy_cache
from otterdog.providers.github.cache.redis import redis_cache
from otterdog.providers.github.graphql import GraphQLClient
from otterdog.providers.github.rest import RestApi
from otterdog.webapp.blueprints import Blueprint, read_blueprint
from otterdog.webapp.policies import Policy, read_policy

logger = getLogger(__name__)

_OTTERDOG_CONFIG: OtterdogConfig | None = None
_OTTERDOG_CONFIG_RETRIEVED_AT: datetime | None = None
_OTTERDOG_CONFIG_LOCK = asyncio.Lock()

_CREATE_INSTALLATION_TOKEN_LOCK = asyncio.Lock()

_GLOBAL_POLICIES: list[Policy] | None = None
_GLOBAL_BLUEPRINTS: list[Blueprint] | None = None


def get_base_url():
    return current_app.config["BASE_URL"]


def get_project_base_url():
    return current_app.config["PROJECTS_BASE_URL"]


def get_github_redis_cache(app_config):
    return redis_cache(app_config["REDIS_URI"], get_redis())


def get_github_ghproxy_cache(app_config):
    return ghproxy_cache(app_config["GHPROXY_URI"])


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
    return RestApi(app_auth(github_app_id, github_app_private_key), get_github_cache())


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
    return RestApi(token_auth(token), get_github_cache())


async def get_graphql_api_for_installation(installation_id: int) -> GraphQLClient:
    token, _ = await get_token_for_installation(installation_id)
    return GraphQLClient(token_auth(token), get_github_cache())


def get_app_root_directory(app: Quart | None = None) -> str:
    config = app.config if app is not None else current_app.config
    return config["APP_ROOT"]


def get_db_root_directory(app: Quart | None = None) -> str:
    config = app.config if app is not None else current_app.config
    return config["DB_ROOT"]


@cache
def get_temporary_base_directory(app: Quart | None = None) -> str:
    import os

    return os.path.join(get_app_root_directory(app), "tmp", f"worker-{os.getpid()}")


async def get_otterdog_config() -> OtterdogConfig:
    global _OTTERDOG_CONFIG, _OTTERDOG_CONFIG_RETRIEVED_AT

    redis = get_redis()

    async with _OTTERDOG_CONFIG_LOCK:
        key = f"config:{_get_otterdog_config_url()}"
        current_data = decode_bytes_dict(await redis.hgetall(key))

        configuration = current_data.get("configuration", None)
        created_at_str = current_data.get("created_at", None)

        if created_at_str is None or configuration is None:
            return await refresh_otterdog_config()

        created_at = datetime.fromisoformat(created_at_str)
        if (
            _OTTERDOG_CONFIG_RETRIEVED_AT is None
            or _OTTERDOG_CONFIG is None
            or created_at > _OTTERDOG_CONFIG_RETRIEVED_AT
        ):
            logger.info("loading otterdog config from cache")
            _OTTERDOG_CONFIG = OtterdogConfig.from_dict(
                json.loads(configuration), False, current_app.config["APP_ROOT"]
            )
            _OTTERDOG_CONFIG_RETRIEVED_AT = created_at
        else:
            logger.info("re-using locally cached otterdog config")

    return _OTTERDOG_CONFIG


async def refresh_otterdog_config(sha: str | None = None) -> OtterdogConfig:
    global _OTTERDOG_CONFIG, _OTTERDOG_CONFIG_RETRIEVED_AT

    config_url = _get_otterdog_config_url()
    logger.info(f"refreshing otterdog config from config url '{config_url}'")

    redis = get_redis()
    config = await _load_otterdog_config(sha)

    created_at = current_utc_time()

    _OTTERDOG_CONFIG = config
    _OTTERDOG_CONFIG_RETRIEVED_AT = created_at

    await redis.hset(
        f"config:{config_url}",
        mapping={
            "configuration": json.dumps(config.configuration),
            "created_at": created_at.isoformat(),
        },
    )

    return config


def _get_otterdog_config_url() -> str:
    config_file_owner = current_app.config["OTTERDOG_CONFIG_OWNER"]
    config_file_repo = current_app.config["OTTERDOG_CONFIG_REPO"]
    config_file_path = current_app.config["OTTERDOG_CONFIG_PATH"]

    return f"'https://github.com/{config_file_owner}/{config_file_repo}/{config_file_path}'"


async def _load_otterdog_config(ref: str | None = None) -> OtterdogConfig:
    app_root = current_app.config["APP_ROOT"]
    config_file_owner = current_app.config["OTTERDOG_CONFIG_OWNER"]
    config_file_repo = current_app.config["OTTERDOG_CONFIG_REPO"]
    config_file_path = current_app.config["OTTERDOG_CONFIG_PATH"]

    logger.info(
        f"loading otterdog config from url "
        f"'https://github.com/{config_file_owner}/{config_file_repo}/{config_file_path}'"
    )

    async with RestApi(token_auth(current_app.config["OTTERDOG_CONFIG_TOKEN"]), get_github_cache()) as rest_api:
        content = await rest_api.content.get_content(config_file_owner, config_file_repo, config_file_path, ref)
        import aiofiles

        async with aiofiles.tempfile.NamedTemporaryFile("wt") as file:
            name = cast("str", file.name)
            await file.write(content)
            await file.flush()
            return OtterdogConfig.from_file(name, False, app_root)


async def refresh_global_policies(sha: str | None = None) -> list[Policy]:
    global _GLOBAL_POLICIES
    _GLOBAL_POLICIES = await _load_global_policies(sha)
    return _GLOBAL_POLICIES


async def _load_global_policies(ref: str | None = None) -> list[Policy]:
    config_file_owner = current_app.config["OTTERDOG_CONFIG_OWNER"]
    config_file_repo = current_app.config["OTTERDOG_CONFIG_REPO"]
    config_file_path = "policies"

    logger.info(
        f"loading global policies from url "
        f"'https://github.com/{config_file_owner}/{config_file_repo}/{config_file_path}'"
    )

    policies = {}

    async with RestApi(token_auth(current_app.config["OTTERDOG_CONFIG_TOKEN"]), get_github_cache()) as rest_api:
        try:
            entries = await rest_api.content.get_content_object(
                config_file_owner, config_file_repo, config_file_path, ref
            )
        except RuntimeError:
            entries = []

        for entry in entries:
            path = entry["path"]
            if is_yaml_file(path):
                content = await rest_api.content.get_content(config_file_owner, config_file_repo, path, ref)
                try:
                    # TODO: do not hardcode the path to the default branch
                    policy_path = f"https://github.com/{config_file_owner}/{config_file_repo}/blob/main/{path}"
                    policy = read_policy(policy_path, yaml.safe_load(content))

                    if policy.type in policies:
                        logger.error(f"duplicate global policy with type '{policy.type}' in path '{path}', skipping")
                    else:
                        policies[policy.type] = policy
                except (ValueError, RuntimeError) as e:
                    logger.error(f"failed reading global policy from path '{path}'", exc_info=e)

    return list(policies.values())


async def refresh_global_blueprints(sha: str | None = None) -> list[Blueprint]:
    global _GLOBAL_BLUEPRINTS
    _GLOBAL_BLUEPRINTS = await _load_global_blueprints(sha)
    return _GLOBAL_BLUEPRINTS


async def _load_global_blueprints(ref: str | None = None) -> list[Blueprint]:
    config_file_owner = current_app.config["OTTERDOG_CONFIG_OWNER"]
    config_file_repo = current_app.config["OTTERDOG_CONFIG_REPO"]
    config_file_path = "blueprints"

    logger.info(
        f"loading global blueprints from url "
        f"'https://github.com/{config_file_owner}/{config_file_repo}/{config_file_path}'"
    )

    blueprints = {}

    async with RestApi(token_auth(current_app.config["OTTERDOG_CONFIG_TOKEN"]), get_github_cache()) as rest_api:
        try:
            entries = await rest_api.content.get_content_object(
                config_file_owner, config_file_repo, config_file_path, ref
            )
        except RuntimeError:
            entries = []

        for entry in entries:
            path = entry["path"]
            if is_yaml_file(path):
                content = await rest_api.content.get_content(config_file_owner, config_file_repo, path, ref)
                try:
                    # TODO: do not hardcode the path to the default branch
                    blueprint_path = f"https://github.com/{config_file_owner}/{config_file_repo}/blob/main/{path}"
                    blueprint = read_blueprint(blueprint_path, yaml.safe_load(content))

                    if blueprint.type in blueprints:
                        logger.error(
                            f"duplicate global blueprint with type '{blueprint.type}' in path '{path}', skipping"
                        )
                    else:
                        blueprints[blueprint.type] = blueprint
                except (ValueError, RuntimeError) as e:
                    logger.error(f"failed reading global blueprint from path '{path}'", exc_info=e)

    return list(blueprints.values())


def get_admin_teams() -> list[str]:
    teams = str(current_app.config["GITHUB_ADMIN_TEAMS"])
    return teams.split(",")


def get_full_admin_team_slugs(org_id: str) -> list[str]:
    return [f"{org_id}/{team_slug}" for team_slug in get_admin_teams()]


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


def epoch_utc_time():
    if sys.version_info < (3, 12):
        return datetime.utcfromtimestamp(0)
    else:
        from datetime import UTC

        return datetime.fromtimestamp(0, UTC)


def current_utc_time() -> datetime:
    if sys.version_info < (3, 12):
        return datetime.utcnow()
    else:
        from datetime import UTC

        return datetime.now(UTC)


def make_aware_utc(d: datetime) -> datetime:
    if sys.version_info < (3, 12):
        from datetime import timezone

        utc = timezone(timedelta(0))
        return d.astimezone(utc)
    else:
        from datetime import UTC

        return d.astimezone(UTC)


async def backoff_if_needed(last_event: datetime, required_timeout: timedelta) -> None:
    last_event = make_aware_utc(last_event)
    now = make_aware_utc(current_utc_time())

    current_timeout = now - last_event

    if current_timeout < required_timeout:
        remaining_backoff = required_timeout - current_timeout
        remaining_backoff_seconds = remaining_backoff.total_seconds() + 1
        logger.debug(f"backing off {remaining_backoff_seconds}s")
        await asyncio.sleep(remaining_backoff_seconds)


def has_minimum_timedelta_elapsed(last_event: datetime, minimum_timedelta: timedelta) -> bool:
    last_event = make_aware_utc(last_event)
    now = make_aware_utc(current_utc_time())

    current_timedelta = now - last_event
    return current_timedelta >= minimum_timedelta


def is_cache_control_enabled() -> bool:
    return bool(current_app.config["CACHE_CONTROL"]) is True


def is_yaml_file(path: str) -> bool:
    return path.endswith((".yml", ".yaml"))
