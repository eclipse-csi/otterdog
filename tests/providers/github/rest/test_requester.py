#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Verifies against a real HTTP server how the requester limits the requests sent concurrently,
sends again the requests that hit a rate limit of GitHub, and the ones that failed if sending
them again is safe.
"""

import asyncio
import json
import socket
import time
from collections import Counter

import pytest
import pytest_asyncio
from aiohttp import (
    ClientConnectorDNSError,
    ClientConnectorError,
    ClientError,
    ClientOSError,
    ClientPayloadError,
    ConnectionTimeoutError,
    ServerDisconnectedError,
    SocketTimeoutError,
    web,
)
from aiohttp.test_utils import TestServer

from otterdog.credentials import Credentials
from otterdog.providers.github import GitHubProvider
from otterdog.providers.github.auth import token_auth
from otterdog.providers.github.cache.ghproxy import ghproxy_cache
from otterdog.providers.github.rest.requester import (
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    Requester,
    get_rate_limit_wait,
    get_retry_options,
)
from otterdog.providers.github.stats import ApiUsage, collect_api_usage

_SECONDARY_RATE_LIMIT = "You have exceeded a secondary rate limit. Please wait a few minutes before you try again."
_PRIMARY_RATE_LIMIT = "API rate limit exceeded for installation ID 1."


class _GitHubStub:
    """A minimal GitHub api, counting the requests it receives and the ones it handles concurrently."""

    def __init__(self) -> None:
        self.hits: Counter[str] = Counter()
        self.in_flight = 0
        self.max_in_flight = 0
        self.received_at: dict[str, float] = {}
        self.hooks: list[dict] = []

        self.app = web.Application()
        self.app.router.add_get("/limited/{times}", self.limited)
        self.app.router.add_get("/limited-for-a-second", self.limited_for_a_second)
        self.app.router.add_get("/exhausted", self.exhausted)
        self.app.router.add_get("/denied", self.denied)
        self.app.router.add_get("/slow", self.slow)
        self.app.router.add_get("/meta", self.meta)
        self.app.router.add_route("*", "/unavailable", self.unavailable)
        self.app.router.add_route("*", "/disconnect", self.disconnect)
        self.app.router.add_post("/orgs/acme/hooks", self.create_hook)

    def _hit(self, request: web.Request) -> int:
        self.hits[request.path] += 1
        self.received_at[request.path] = time.monotonic()
        return self.hits[request.path]

    async def limited(self, request: web.Request) -> web.Response:
        # hits a secondary rate limit the given number of times, telling to send the request again immediately
        if self._hit(request) <= int(request.match_info["times"]):
            return web.json_response({"message": _SECONDARY_RATE_LIMIT}, status=403, headers={"retry-after": "0"})
        return web.json_response({})

    async def limited_for_a_second(self, request: web.Request) -> web.Response:
        if self._hit(request) == 1:
            return web.json_response({"message": _SECONDARY_RATE_LIMIT}, status=429, headers={"retry-after": "1"})
        return web.json_response({})

    async def exhausted(self, request: web.Request) -> web.Response:
        # an exhausted primary rate limit, reset in an hour
        self._hit(request)
        headers = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(time.time()) + 3600)}
        return web.json_response({"message": _PRIMARY_RATE_LIMIT}, status=403, headers=headers)

    async def denied(self, request: web.Request) -> web.Response:
        self._hit(request)
        return web.json_response({"message": "Resource not accessible by integration"}, status=403)

    async def slow(self, request: web.Request) -> web.Response:
        self._hit(request)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.1)
        self.in_flight -= 1
        return web.json_response({})

    async def meta(self, request: web.Request) -> web.Response:
        self._hit(request)
        return web.json_response({})

    async def unavailable(self, request: web.Request) -> web.Response:
        # fails with a server error twice, whatever the method
        if self._hit(request) <= 2:
            return web.Response(status=502)
        return web.json_response({})

    async def disconnect(self, request: web.Request) -> web.Response:
        # the request has been received, but the connection is closed without any response
        self._hit(request)
        if request.transport is not None:
            request.transport.close()
        return web.Response()

    async def create_hook(self, request: web.Request) -> web.Response:
        # the webhook is created, but its response is lost
        self._hit(request)
        self.hooks.append(await request.json())
        return web.Response(status=502)


@pytest_asyncio.fixture
async def github():
    stub = _GitHubStub()
    server = TestServer(stub.app)
    await server.start_server()
    stub.url = str(server.make_url("/")).rstrip("/")  # type: ignore[attr-defined]
    yield stub
    await server.close()


@pytest_asyncio.fixture
async def requester(github):
    # the proxy cache strategy redirects all requests to the stub
    result = Requester(token_auth("token"), ghproxy_cache(github.url), "api.github.com", "2022-11-28")
    yield result
    await result.close()


async def test_request_hitting_a_secondary_rate_limit_is_sent_again(github, requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        assert await requester.request_json("GET", "/limited/2") == {}

    assert github.hits["/limited/2"] == 3
    assert usage.rest.total_requests == 3
    assert usage.rest.retried_requests == 2
    assert usage.rest.errors == {"403": 2}


async def test_rate_limit_is_returned_after_the_last_retry(github, requester):
    status, _ = await requester.request_raw("GET", "/limited/10")

    assert status == 403
    # the request and its 3 retries
    assert github.hits["/limited/10"] == 4


async def test_rate_limit_with_a_long_wait_is_not_retried(github, requester):
    status, body = await requester.request_raw("GET", "/exhausted")

    assert status == 403
    assert _PRIMARY_RATE_LIMIT in body
    assert github.hits["/exhausted"] == 1


async def test_denied_access_is_not_retried(github, requester):
    status, _ = await requester.request_raw("GET", "/denied")

    assert status == 403
    assert github.hits["/denied"] == 1


async def test_request_is_sent_again_after_the_wait_given_by_github(github, requester):
    start = time.monotonic()

    assert await requester.request_json("GET", "/limited-for-a-second") == {}

    assert github.hits["/limited-for-a-second"] == 2
    assert time.monotonic() - start >= 1


async def test_requests_wait_for_the_end_of_a_pause(github, requester):
    # a request that hit a rate limit pauses all requests, not only itself
    paused_until = time.monotonic() + 0.3
    requester._paused_until = paused_until

    await requester.request_json("GET", "/meta")

    assert github.received_at["/meta"] >= paused_until


async def test_concurrent_requests_are_limited(github):
    requester = Requester(token_auth("token"), ghproxy_cache(github.url), "api.github.com", "v", 2)

    try:
        await asyncio.gather(*[requester.request_json("GET", "/slow") for _ in range(6)])
    finally:
        await requester.close()

    assert github.hits["/slow"] == 6
    assert github.max_in_flight == 2


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
async def test_idempotent_request_failing_with_a_server_error_is_sent_again(github, requester, method):
    status, _ = await requester.request_raw(method, "/unavailable", json.dumps({"key": "value"}))

    assert status == 200
    assert github.hits["/unavailable"] == 3


@pytest.mark.parametrize("method", ["POST", "PATCH"])
async def test_request_not_idempotent_failing_with_a_server_error_is_sent_once(github, requester, method):
    usage = ApiUsage()

    with collect_api_usage(usage):
        status, _ = await requester.request_raw(method, "/unavailable", json.dumps({"key": "value"}))

    assert status == 502
    assert github.hits["/unavailable"] == 1
    assert usage.rest.retried_requests == 0


async def test_creation_whose_response_is_lost_is_not_sent_again(github, requester):
    status, _ = await requester.request_raw("POST", "/orgs/acme/hooks", json.dumps({"name": "web"}))

    # the failure is reported, while sending the request again would have created a second webhook
    assert status == 502
    assert github.hooks == [{"name": "web"}]


@pytest.mark.parametrize("method", ["POST", "PATCH"])
async def test_request_not_idempotent_losing_its_connection_is_sent_once(github, requester, method):
    with pytest.raises(ClientError):
        await requester.request_raw(method, "/disconnect", json.dumps({"key": "value"}))

    assert github.hits["/disconnect"] == 1


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH"])
async def test_request_is_sent_again_when_no_connection_could_be_established(method):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    requester = Requester(token_auth("token"), ghproxy_cache(f"http://127.0.0.1:{port}"), "api.github.com", "v")
    usage = ApiUsage()

    try:
        with collect_api_usage(usage), pytest.raises(ClientConnectorError):
            await requester.request_raw(method, "/orgs/acme/hooks", json.dumps({"name": "web"}))
    finally:
        await requester.close()

    assert usage.rest.unsent_attempts == {"network": 3}


@pytest.mark.parametrize(
    ("method", "exception", "sent_again"),
    [
        ("GET", ServerDisconnectedError, True),
        ("HEAD", ClientPayloadError, True),
        ("PUT", SocketTimeoutError, True),
        ("DELETE", ClientOSError, True),
        # no connection could be established, the request has not been sent
        ("POST", ClientConnectorError, True),
        ("POST", ClientConnectorDNSError, True),
        ("PATCH", ConnectionTimeoutError, True),
        # the request may have been received by GitHub
        ("POST", ServerDisconnectedError, False),
        ("POST", ClientOSError, False),
        ("PATCH", SocketTimeoutError, False),
        ("PATCH", ClientPayloadError, False),
    ],
)
def test_exceptions_after_which_a_request_is_sent_again(method, exception, sent_again):
    # matches the exceptions as aiohttp_retry does
    exceptions = get_retry_options(method).exceptions
    assert any(issubclass(exception, retried) for retried in exceptions) == sent_again


@pytest.mark.parametrize(
    ("method", "sent_again"),
    [
        ("GET", True),
        ("HEAD", True),
        ("OPTIONS", True),
        ("PUT", True),
        ("DELETE", True),
        ("POST", False),
        ("PATCH", False),
    ],
)
def test_server_errors_after_which_a_request_is_sent_again(method, sent_again):
    assert get_retry_options(method).retry_all_server_errors == sent_again


@pytest.mark.parametrize(
    ("status", "body", "headers", "retries", "expected"),
    [
        (200, "{}", {}, 0, None),
        (404, "Not Found", {}, 0, None),
        (403, "Resource not accessible by integration", {}, 0, None),
        (403, _SECONDARY_RATE_LIMIT, {"retry-after": "30"}, 0, 30),
        (429, _SECONDARY_RATE_LIMIT, {"retry-after": "30"}, 2, 30),
        (403, _SECONDARY_RATE_LIMIT, {"retry-after": "600"}, 0, None),
        (403, _SECONDARY_RATE_LIMIT, {}, 0, 60),
        (403, _SECONDARY_RATE_LIMIT, {}, 1, 120),
        (403, _SECONDARY_RATE_LIMIT, {}, 2, 240),
        (403, _SECONDARY_RATE_LIMIT, {}, 3, None),
        # without retry-after, a secondary rate limit leaves the primary rate limit unchanged
        (403, _SECONDARY_RATE_LIMIT, {"x-ratelimit-remaining": "10", "x-ratelimit-reset": "1"}, 0, 60),
    ],
)
def test_rate_limit_wait(status, body, headers, retries, expected):
    assert get_rate_limit_wait(status, body, headers, retries) == expected


def test_rate_limit_wait_until_the_reset_of_an_exhausted_rate_limit():
    headers = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(time.time()) + 10)}

    wait = get_rate_limit_wait(403, _PRIMARY_RATE_LIMIT, headers, 0)

    assert wait is not None
    assert 9 <= wait <= 11


async def test_provider_limits_the_requests_sent_concurrently():
    credentials = Credentials(None, None, None, "token")

    async with GitHubProvider(credentials) as provider:
        assert provider.rest_api.requester.max_concurrent_requests == DEFAULT_MAX_CONCURRENT_REQUESTS

    async with GitHubProvider(credentials, 20) as provider:
        assert provider.rest_api.requester.max_concurrent_requests == 20
