#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic
from urllib.parse import urlparse

from quart import current_app
from quart_redis import get_redis  # type: ignore

from otterdog.webapp import mongo
from otterdog.webapp.blueprints import create_blueprint_from_model
from otterdog.webapp.db.service import (
    InstallationTaskTracker,
    get_blueprints_by_last_checked_time,
    get_installation_by_github_id,
    logger,
    save_blueprint,
    track_installation_tasks,
    update_installations_from_config,
)
from otterdog.webapp.lease import RedisLease
from otterdog.webapp.statistics import refresh_organization_digests
from otterdog.webapp.utils import (
    current_utc_time,
    has_minimum_timedelta_elapsed,
    refresh_global_blueprints,
    refresh_global_policies,
    refresh_otterdog_config,
)

from . import blueprint

# how long a single dependency may take to answer before the readiness check gives up on it,
# below the timeout of the probes of the helm chart, 3 seconds, to answer them with the actual result
READINESS_CHECK_TIMEOUT_IN_SECONDS = 2.0

# how long the result of the readiness checks is reused, whatever the number of requests in the meantime
READINESS_CACHE_TTL_IN_SECONDS = 5.0

_readiness_lock = asyncio.Lock()
_readiness_result: tuple[float, dict[str, dict[str, str]]] | None = None

# an initialization and a check of the blueprints run at most once at a time across all workers,
# requests received meanwhile are rejected rather than queued, so that they can not pile up work
_INIT_LEASE_KEY = "internal-init"
_CHECK_LEASE_KEY = "internal-check"

# short enough to recover quickly from a worker disappearing while holding a lease, which is
# renewed as long as the work it protects is running
_LEASE_TTL_IN_SECONDS = 300

# the lease of an initialization is held until the installation tasks it scheduled have completed,
# but released after that long whatever happens, so that a stuck task can not block it forever
INIT_MAX_DURATION_IN_SECONDS = 3600

# when to call again after being rejected, honored by `curl --retry`, which the helm chart uses to initialize
_RETRY_AFTER_IN_SECONDS = 60


@blueprint.route("/health")
async def health():
    """
    Liveness check, only tells whether the webapp answers requests.

    It does not depend on any external service on purpose: a dependency being down
    must not get the webapp restarted, use /internal/ready to check them.
    """
    return {}, 200


async def _check_mongodb() -> None:
    await mongo.ping(timeout=READINESS_CHECK_TIMEOUT_IN_SECONDS)


async def _check_redis() -> None:
    await get_redis().ping()


async def _check_ghproxy() -> None:
    """
    Opens a TCP connection to ghproxy, without sending any request.

    Every HTTP request sent to ghproxy is forwarded to GitHub, so an HTTP check would
    depend on GitHub being available and count against its rate limit. The own health
    endpoint of ghproxy listens on a separate port that is not part of the configuration.
    """
    uri = urlparse(current_app.config["GHPROXY_URI"])
    port = uri.port or (443 if uri.scheme == "https" else 80)

    _, writer = await asyncio.open_connection(uri.hostname, port)
    writer.close()
    await writer.wait_closed()


_READINESS_CHECKS: dict[str, Callable[[], Awaitable[None]]] = {
    "mongodb": _check_mongodb,
    "redis": _check_redis,
    "ghproxy": _check_ghproxy,
}


async def _run_readiness_check(name: str, probe: Callable[[], Awaitable[None]]) -> dict[str, str]:
    try:
        await asyncio.wait_for(probe(), timeout=READINESS_CHECK_TIMEOUT_IN_SECONDS)
        return {"status": "ok"}
    except Exception as ex:
        # only the type of the error is returned, its message may disclose details of the infrastructure
        logger.warning("readiness check of '%s' failed: %r", name, ex)
        return {"status": "error", "error": type(ex).__name__}


async def _get_readiness_checks() -> dict[str, dict[str, str]]:
    """
    Runs the readiness checks at most once every READINESS_CACHE_TTL_IN_SECONDS in each worker.

    Requests received while the checks run wait for their result rather than starting new ones,
    so a burst of requests does not turn into a burst of connections to the dependencies, and
    a failure is reused as well, as probing a dependency that is down is what piles them up.
    """
    global _readiness_result

    async with _readiness_lock:
        if _readiness_result is not None:
            checked_at, checks = _readiness_result
            if monotonic() - checked_at < READINESS_CACHE_TTL_IN_SECONDS:
                return checks

        results = await asyncio.gather(
            *(_run_readiness_check(name, probe) for name, probe in _READINESS_CHECKS.items())
        )
        checks = dict(zip(_READINESS_CHECKS, results, strict=True))

        _readiness_result = (monotonic(), checks)
        return checks


@blueprint.route("/ready")
async def ready():
    """
    Readiness check, tells whether the services the webapp depends on are reachable.

    Answers 200 when all of them are, 503 otherwise, along with the result of each check.
    """
    checks = await _get_readiness_checks()

    is_ready = all(result["status"] == "ok" for result in checks.values())
    return {"status": "ok" if is_ready else "error", "checks": checks}, 200 if is_ready else 503


def _already_running(what: str):
    logger.debug("%s is already running, rejecting the request", what)
    return {"status": f"{what} is already running"}, 429, {"Retry-After": str(_RETRY_AFTER_IN_SECONDS)}


@blueprint.route("/init")
async def init():
    """
    Refreshes the data of every installation, once at a time across all workers.

    The refresh goes on in background tasks after the response, the lease is held until
    they have completed, as calling again meanwhile would schedule all of them once more.
    """
    lease = RedisLease(_INIT_LEASE_KEY, _LEASE_TTL_IN_SECONDS)
    if not await lease.acquire():
        return _already_running("an initialization")

    tracker = InstallationTaskTracker()
    current_app.add_background_task(_hold_until_completed, lease, tracker)

    with track_installation_tasks(tracker):
        config = await refresh_otterdog_config()
        policies = await refresh_global_policies()
        blueprints = await refresh_global_blueprints()
        await update_installations_from_config(config, policies, blueprints, force_update_data=True)

    # refreshed in the background, the statistics page then never waits for GitHub itself,
    # a refresh of the digests is already kept from running more than once at a time
    current_app.add_background_task(refresh_organization_digests)

    return {}, 200


async def _hold_until_completed(lease: RedisLease, tracker: InstallationTaskTracker) -> None:
    async with lease.held():
        try:
            await asyncio.wait_for(tracker.wait(), timeout=INIT_MAX_DURATION_IN_SECONDS)
        except TimeoutError:
            logger.warning(
                "the initialization did not complete within %d seconds, allowing another one to start",
                INIT_MAX_DURATION_IN_SECONDS,
            )


@blueprint.route("/check", defaults={"limit": 50})
@blueprint.route("/check/<int:limit>")
async def check(limit: int):
    """Evaluates the blueprints, once at a time across all workers."""
    lease = RedisLease(_CHECK_LEASE_KEY, _LEASE_TTL_IN_SECONDS)
    if not await lease.acquire():
        return _already_running("a check of the blueprints")

    async with lease.held():
        await _check_blueprints(limit)

    return {}, 200


async def _check_blueprints(limit: int) -> None:
    from datetime import timedelta

    logger.info("checking blueprints...")

    for blueprint_model in await get_blueprints_by_last_checked_time(limit=limit):
        org_id = blueprint_model.id.org_id

        if blueprint_model.last_checked is not None and not has_minimum_timedelta_elapsed(
            blueprint_model.last_checked, timedelta(seconds=current_app.config["BLUEPRINT_CHECK_INTERVAL"])
        ):
            logger.debug(
                "skipping blueprint with id '%s' for org '%s', last checked at '%s'",
                blueprint_model.id.blueprint_id,
                org_id,
                blueprint_model.last_checked.strftime("%d/%m/%Y %H:%M:%S"),
            )
            continue

        installation = await get_installation_by_github_id(org_id)
        if installation is None:
            logger.error("no installation model found for org '%s'", org_id)
            continue

        logger.debug("checking blueprint with id '%s' for org '%s'...", blueprint_model.id.blueprint_id, org_id)

        blueprint_instance = create_blueprint_from_model(blueprint_model)
        await blueprint_instance.evaluate(installation.installation_id, org_id, blueprint_model.recheck_needed)

        blueprint_model.last_checked = current_utc_time()

        # if we were forced to do a recheck, reset it afterward
        if blueprint_model.recheck_needed is True:
            blueprint_model.recheck_needed = False

        await save_blueprint(blueprint_model)


@blueprint.route("/<template>")
async def route_template(template: str):
    return {}, 404


@blueprint.errorhandler(Exception)
async def error_exception(error):
    import traceback

    traceback.print_exception(error)
    return {}, 500
