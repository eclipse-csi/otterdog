#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import socket
from unittest import mock

import pytest

from otterdog.webapp.internal import routes


async def test_init_forces_the_refresh_of_every_installation(app, fake_redis, monkeypatch):
    """
    Exercised through a request context rather than a test client.

    Booting the app would run its startup hooks, which expect a running mongodb.
    """

    update_installations_from_config = mock.AsyncMock()

    monkeypatch.setattr(routes, "refresh_otterdog_config", mock.AsyncMock(return_value="config"))
    monkeypatch.setattr(routes, "refresh_global_policies", mock.AsyncMock(return_value=["policy"]))
    monkeypatch.setattr(routes, "refresh_global_blueprints", mock.AsyncMock(return_value=["blueprint"]))
    monkeypatch.setattr(routes, "update_installations_from_config", update_installations_from_config)
    monkeypatch.setattr(app, "add_background_task", mock.MagicMock())

    async with app.test_request_context("/internal/init"):
        _, status = await routes.init()

    assert status == 200
    update_installations_from_config.assert_awaited_once_with(
        "config", ["policy"], ["blueprint"], force_update_data=True
    )


class _InstallationTask:
    """An installation task running until it is told to complete."""

    def __init__(self) -> None:
        self.completed = asyncio.Event()

    async def execute(self) -> None:
        await self.completed.wait()


@pytest.fixture
def init_scheduling_a_task(monkeypatch):
    """Makes /internal/init schedule a single installation task, as many as there are organizations otherwise."""
    from otterdog.webapp.db import service

    task = _InstallationTask()

    async def update_installations_from_config(*args, **kwargs):
        service._schedule_installation_task(task)

    monkeypatch.setattr(routes, "refresh_otterdog_config", mock.AsyncMock())
    monkeypatch.setattr(routes, "refresh_global_policies", mock.AsyncMock())
    monkeypatch.setattr(routes, "refresh_global_blueprints", mock.AsyncMock())
    monkeypatch.setattr(routes, "update_installations_from_config", update_installations_from_config)
    monkeypatch.setattr(routes, "refresh_organization_digests", mock.AsyncMock())

    yield task

    # never leave a background task waiting
    task.completed.set()


async def _until(condition, timeout: float = 1.0) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.005)


async def test_init_is_rejected_while_another_one_runs(app, fake_redis, init_scheduling_a_task):
    async with app.test_request_context("/internal/init"):
        _, status = await routes.init()
        assert status == 200

        body, status, headers = await routes.init()

    assert status == 429
    assert headers == {"Retry-After": "60"}
    assert body == {"status": "an initialization is already running"}
    routes.refresh_otterdog_config.assert_awaited_once()


async def test_the_init_lease_is_held_until_the_tasks_it_scheduled_completed(app, fake_redis, init_scheduling_a_task):
    """The response is sent once the tasks are scheduled, calling again meanwhile would schedule them once more."""
    async with app.test_request_context("/internal/init"):
        _, status = await routes.init()

        assert status == 200
        await asyncio.sleep(0.05)
        assert routes._INIT_LEASE_KEY in fake_redis.values

        init_scheduling_a_task.completed.set()
        await _until(lambda: routes._INIT_LEASE_KEY not in fake_redis.values)

        # another initialization can then start
        _, status = await routes.init()
        assert status == 200


async def test_the_init_lease_is_released_when_the_init_fails(app, fake_redis, init_scheduling_a_task):
    routes.refresh_otterdog_config.side_effect = RuntimeError("boom")

    async with app.test_request_context("/internal/init"):
        with pytest.raises(RuntimeError):
            await routes.init()

        await _until(lambda: routes._INIT_LEASE_KEY not in fake_redis.values)


async def test_the_init_lease_is_released_after_the_maximum_duration(
    app, fake_redis, init_scheduling_a_task, monkeypatch
):
    """A task that never completes must not keep any initialization from running anymore."""
    monkeypatch.setattr(routes, "INIT_MAX_DURATION_IN_SECONDS", 0.05)

    async with app.test_request_context("/internal/init"):
        await routes.init()

        await _until(lambda: routes._INIT_LEASE_KEY not in fake_redis.values)

    assert not init_scheduling_a_task.completed.is_set()


async def test_check_is_rejected_while_another_one_runs(app, fake_redis, monkeypatch):
    async def slow_blueprints(limit):
        await asyncio.sleep(0.05)
        return []

    get_blueprints = mock.AsyncMock(side_effect=slow_blueprints)
    monkeypatch.setattr(routes, "get_blueprints_by_last_checked_time", get_blueprints)

    async def check():
        async with app.test_request_context("/internal/check"):
            return await routes.check(50)

    responses = await asyncio.gather(check(), check())

    assert sorted(response[1] for response in responses) == [200, 429]
    get_blueprints.assert_awaited_once()

    # the lease is released along with the check
    assert routes._CHECK_LEASE_KEY not in fake_redis.values
    _, status = await check()
    assert status == 200


async def test_the_check_lease_is_released_when_the_check_fails(app, fake_redis, monkeypatch):
    monkeypatch.setattr(routes, "get_blueprints_by_last_checked_time", mock.AsyncMock(side_effect=RuntimeError("boom")))

    async with app.test_request_context("/internal/check"):
        with pytest.raises(RuntimeError):
            await routes.check(50)

    assert routes._CHECK_LEASE_KEY not in fake_redis.values


@pytest.fixture(autouse=True)
def reset_readiness_cache(monkeypatch):
    # the cached result and its lock are kept by the module, each test starts on a new event loop
    monkeypatch.setattr(routes, "_readiness_lock", asyncio.Lock())
    monkeypatch.setattr(routes, "_readiness_result", None)


@pytest.fixture
def healthy_dependencies(monkeypatch):
    """Replaces the checks of mongodb and redis, ghproxy is checked against a real socket."""
    monkeypatch.setattr(routes.mongo, "ping", mock.AsyncMock())
    redis = mock.MagicMock()
    redis.ping = mock.AsyncMock()
    monkeypatch.setattr(routes, "get_redis", lambda: redis)
    return redis


@pytest.fixture
async def ghproxy_uri():
    server = await asyncio.start_server(lambda reader, writer: writer.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.close()
    await server.wait_closed()


def _closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _ready(app, ghproxy_uri):
    app.config["GHPROXY_URI"] = ghproxy_uri
    async with app.test_request_context("/internal/ready"):
        return await routes.ready()


async def test_ready_when_every_dependency_is_reachable(app, healthy_dependencies, ghproxy_uri):
    body, status = await _ready(app, ghproxy_uri)

    assert status == 200
    assert body == {
        "status": "ok",
        "checks": {"mongodb": {"status": "ok"}, "redis": {"status": "ok"}, "ghproxy": {"status": "ok"}},
    }


async def test_not_ready_when_mongodb_fails(app, healthy_dependencies, ghproxy_uri, monkeypatch):
    from pymongo.errors import ServerSelectionTimeoutError

    monkeypatch.setattr(
        routes.mongo, "ping", mock.AsyncMock(side_effect=ServerSelectionTimeoutError("mongodb:27017 refused"))
    )

    body, status = await _ready(app, ghproxy_uri)

    assert status == 503
    assert body["status"] == "error"
    # the message of the error, disclosing the address of the server, is not returned
    assert body["checks"]["mongodb"] == {"status": "error", "error": "ServerSelectionTimeoutError"}
    assert body["checks"]["redis"] == {"status": "ok"}
    assert body["checks"]["ghproxy"] == {"status": "ok"}


async def test_not_ready_when_redis_is_not_initialized(app, ghproxy_uri, monkeypatch):
    """Without patching get_redis, redis is not initialized as the app is not served."""
    monkeypatch.setattr(routes.mongo, "ping", mock.AsyncMock())

    body, status = await _ready(app, ghproxy_uri)

    assert status == 503
    assert body["checks"]["redis"] == {"status": "error", "error": "RedisNotInitialized"}


async def test_not_ready_when_ghproxy_is_unreachable(app, healthy_dependencies):
    body, status = await _ready(app, f"http://127.0.0.1:{_closed_port()}")

    assert status == 503
    assert body["checks"]["ghproxy"] == {"status": "error", "error": "ConnectionRefusedError"}
    assert body["checks"]["mongodb"] == {"status": "ok"}


async def test_not_ready_when_a_dependency_does_not_answer_in_time(app, healthy_dependencies, ghproxy_uri, monkeypatch):
    async def hang():
        await asyncio.sleep(10)

    healthy_dependencies.ping = hang
    monkeypatch.setattr(routes, "READINESS_CHECK_TIMEOUT_IN_SECONDS", 0.05)

    body, status = await _ready(app, ghproxy_uri)

    assert status == 503
    assert body["checks"]["redis"] == {"status": "error", "error": "TimeoutError"}
    assert body["checks"]["mongodb"] == {"status": "ok"}


async def test_health_does_not_depend_on_any_dependency(app, monkeypatch):
    monkeypatch.setattr(routes.mongo, "ping", mock.AsyncMock(side_effect=AssertionError("must not be called")))

    async with app.test_request_context("/internal/health"):
        assert await routes.health() == ({}, 200)


async def test_concurrent_requests_share_a_single_run_of_the_checks(
    app, healthy_dependencies, ghproxy_uri, monkeypatch
):
    """A burst of requests must not turn into a burst of connections to the dependencies."""

    async def slow_ping(**_):
        await asyncio.sleep(0.05)

    mongo_ping = mock.AsyncMock(side_effect=slow_ping)
    monkeypatch.setattr(routes.mongo, "ping", mongo_ping)

    responses = await asyncio.gather(*(_ready(app, ghproxy_uri) for _ in range(20)))

    assert {status for _, status in responses} == {200}
    assert mongo_ping.await_count == 1
    assert healthy_dependencies.ping.await_count == 1


async def test_the_result_is_reused_until_it_expires(app, healthy_dependencies, ghproxy_uri, monkeypatch):
    await _ready(app, ghproxy_uri)
    await _ready(app, ghproxy_uri)

    assert healthy_dependencies.ping.await_count == 1

    monkeypatch.setattr(routes, "READINESS_CACHE_TTL_IN_SECONDS", 0)
    await _ready(app, ghproxy_uri)

    assert healthy_dependencies.ping.await_count == 2


async def test_a_failure_is_reused_as_well(app, healthy_dependencies, ghproxy_uri):
    """Probing a dependency that is down is what piles up connections, the failure must be cached too."""
    healthy_dependencies.ping.side_effect = ConnectionError("redis:6379 refused")

    for _ in range(3):
        _, status = await _ready(app, ghproxy_uri)
        assert status == 503

    assert healthy_dependencies.ping.await_count == 1


async def test_mongodb_is_pinged_with_a_bounded_timeout(app, healthy_dependencies, ghproxy_uri):
    await _ready(app, ghproxy_uri)

    routes.mongo.ping.assert_awaited_once_with(timeout=routes.READINESS_CHECK_TIMEOUT_IN_SECONDS)
