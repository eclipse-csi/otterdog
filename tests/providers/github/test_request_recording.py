#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Verifies the request statistics against a real HTTP server, as they are recorded by the
HTTP session itself which the HttpClientMock used by other tests replaces.
"""

import asyncio
import json
import socket
from collections import Counter

import pytest
import pytest_asyncio
from aiohttp import ClientPayloadError, web
from aiohttp.test_utils import TestServer

from otterdog.providers.github.auth import token_auth
from otterdog.providers.github.cache.file import file_cache
from otterdog.providers.github.cache.ghproxy import ghproxy_cache
from otterdog.providers.github.graphql import GraphQLClient
from otterdog.providers.github.rest.requester import Requester
from otterdog.providers.github.stats import ApiUsage, collect_api_usage
from otterdog.providers.github.stats.report import ApiUsageReport

_TOKEN = "ghp_do_not_leak_this_token"

_RATE_LIMIT_HEADERS = {
    "x-ratelimit-limit": "5000",
    "x-ratelimit-remaining": "4990",
    "x-ratelimit-reset": "1800000000",
    "x-ratelimit-resource": "core",
}


class _GitHubStub:
    """A minimal GitHub api, counting the requests it receives."""

    def __init__(self) -> None:
        self.hits: Counter[str] = Counter()
        self.request_received = asyncio.Event()
        self.graphql_pool_exhausted = asyncio.Event()

        self.app = web.Application()
        self.app.router.add_get("/orgs/acme/repos", self.paged_repos)
        self.app.router.add_get("/orgs/acme/flaky", self.flaky)
        self.app.router.add_get("/orgs/acme/etag", self.etag)
        self.app.router.add_get("/orgs/acme/no-etag", self.no_etag)
        self.app.router.add_get("/orgs/acme/proxied", self.proxied)
        self.app.router.add_get("/orgs/acme/missing", self.missing)
        self.app.router.add_get("/orgs/acme/slow", self.slow)
        self.app.router.add_get("/orgs/acme/truncated", self.truncated)
        self.app.router.add_get("/orgs/acme/slow-body", self.slow_body)
        self.app.router.add_get("/meta", self.meta)
        self.app.router.add_get("/repos/acme/website/zipball/main", self.zipball)
        self.app.router.add_get("/download/website.zip", self.download)
        self.app.router.add_post("/graphql", self.graphql)

    def _hit(self, request: web.Request) -> None:
        self.hits[request.path] += 1

    async def paged_repos(self, request: web.Request) -> web.Response:
        self._hit(request)
        page = int(request.query.get("page", "1"))
        headers = dict(_RATE_LIMIT_HEADERS)
        if page < 3:
            headers["Link"] = f'<{request.url.with_query(per_page="100", page=str(page + 1))}>; rel="next"'
        return web.json_response([{"name": f"repo-{page}"}], headers=headers)

    async def flaky(self, request: web.Request) -> web.Response:
        self._hit(request)
        if self.hits[request.path] < 3:
            return web.Response(status=502, headers=_RATE_LIMIT_HEADERS)
        return web.json_response({}, headers=_RATE_LIMIT_HEADERS)

    async def etag(self, request: web.Request) -> web.Response:
        self._hit(request)
        if request.headers.get("If-None-Match") == '"v1"':
            return web.Response(status=304, headers={**_RATE_LIMIT_HEADERS, "ETag": '"v1"'})
        return web.json_response({"login": "acme"}, headers={**_RATE_LIMIT_HEADERS, "ETag": '"v1"'})

    async def no_etag(self, request: web.Request) -> web.Response:
        self._hit(request)
        return web.json_response({"login": "acme"}, headers=_RATE_LIMIT_HEADERS)

    async def proxied(self, request: web.Request) -> web.Response:
        self._hit(request)
        return web.json_response({}, headers={**_RATE_LIMIT_HEADERS, "X-From-Cache": "1"})

    async def missing(self, request: web.Request) -> web.Response:
        self._hit(request)
        return web.json_response({"message": "Not Found"}, status=404, headers=_RATE_LIMIT_HEADERS)

    async def slow(self, request: web.Request) -> web.Response:
        self._hit(request)
        self.request_received.set()
        await asyncio.sleep(60)
        return web.json_response({})

    async def _partial_body(self, request: web.Request) -> web.StreamResponse:
        self._hit(request)
        response = web.StreamResponse(headers={**_RATE_LIMIT_HEADERS, "Content-Length": "100"})
        await response.prepare(request)
        await response.write(b"[")
        return response

    async def truncated(self, request: web.Request) -> web.StreamResponse:
        response = await self._partial_body(request)
        if request.transport is not None:
            request.transport.close()
        return response

    async def slow_body(self, request: web.Request) -> web.StreamResponse:
        response = await self._partial_body(request)
        self.request_received.set()
        await asyncio.sleep(60)
        return response

    async def meta(self, request: web.Request) -> web.Response:
        self._hit(request)
        await asyncio.sleep(0.01)
        return web.json_response({}, headers=_RATE_LIMIT_HEADERS)

    async def zipball(self, request: web.Request) -> web.Response:
        self._hit(request)
        raise web.HTTPFound("/download/website.zip", headers=_RATE_LIMIT_HEADERS)

    async def download(self, request: web.Request) -> web.Response:
        # served by another host at GitHub, which does not count against the api quota
        self._hit(request)
        return web.Response(body=b"zip-content")

    async def graphql(self, request: web.Request) -> web.Response:
        self._hit(request)
        query = (await request.json())["query"]
        headers = {**_RATE_LIMIT_HEADERS, "x-ratelimit-resource": "graphql"}

        if "minimizeComment" in query:
            return web.json_response({"data": {"minimizeComment": {"clientMutationId": None}}}, headers=headers)
        elif "updateBranchProtectionRule" in query:
            return web.json_response({"errors": [{"type": "NOT_FOUND", "message": "missing rule"}]}, headers=headers)
        elif "deleteBranchProtectionRule" in query:
            self.hits["deleteBranchProtectionRule"] += 1
            if self.hits["deleteBranchProtectionRule"] < 3:
                return web.Response(status=502, headers=headers)
            return web.json_response(
                {"data": {"deleteBranchProtectionRule": {"clientMutationId": None}}}, headers=headers
            )
        elif "pullRequests(first" in query:
            # keeps every connection of the client busy, its pool is limited to 10 connections
            if self.hits[request.path] >= 10:
                self.graphql_pool_exhausted.set()
            await asyncio.sleep(60)
            return web.json_response({}, headers=headers)
        elif "pullRequest(number" in query:
            # served from the cache of a proxy, the cost belongs to the original request
            comments = {"nodes": [], "pageInfo": {"hasNextPage": False}}
            return web.json_response(
                {"data": {"rateLimit": {"cost": 5}, "repository": {"pullRequest": {"comments": comments}}}},
                headers={**headers, "X-From-Cache": "1"},
            )
        else:
            teams = {"nodes": [{"id": "T1", "name": "team", "slug": "team"}], "pageInfo": {"hasNextPage": False}}
            return web.json_response(
                {"data": {"rateLimit": {"cost": 3, "remaining": 4990}, "organization": {"teams": teams}}},
                headers=headers,
            )


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
    result = Requester(token_auth(_TOKEN), ghproxy_cache(github.url), "api.github.com", "2022-11-28")
    yield result
    await result.close()


@pytest_asyncio.fixture
async def cached_requester(github, tmp_path):
    result = Requester(token_auth(_TOKEN), file_cache(str(tmp_path / "cache")), "api.github.com", "2022-11-28")
    result._base_url = github.url
    yield result
    await result.close()


async def test_every_page_is_a_request(requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        repos = await requester.request_paged_json("GET", "/orgs/acme/repos")

    assert len(repos) == 3
    assert usage.rest.total_requests == 3
    assert usage.rest.quota_cost == {"core": 3}
    assert usage.rest.endpoints["GET /orgs/{org}/repos"].requests == 3
    assert requester.statistics.total_requests == 3


async def test_every_attempt_is_a_request(github, requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        await requester.request_json("GET", "/orgs/acme/flaky")

    assert github.hits["/orgs/acme/flaky"] == 3
    assert usage.rest.total_requests == 3
    assert usage.rest.retried_requests == 2
    assert usage.rest.errors == {"502": 2}
    assert usage.rest.quota_cost == {"core": 3}


async def test_network_errors_are_requests():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    requester = Requester(token_auth(_TOKEN), ghproxy_cache(f"http://127.0.0.1:{port}"), "api.github.com", "v")
    usage = ApiUsage()

    try:
        with collect_api_usage(usage), pytest.raises(OSError):
            await requester.request_raw("GET", "/orgs/acme")
    finally:
        await requester.close()

    assert usage.rest.total_requests == 3
    assert usage.rest.retried_requests == 2
    assert usage.rest.errors == {"network": 3}
    assert len(usage.rest.quota_cost) == 0


async def test_error_status_is_recorded(requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        status, _ = await requester.request_raw("GET", "/orgs/acme/missing")

    assert status == 404
    assert usage.rest.total_requests == 1
    assert usage.rest.errors == {"404": 1}
    assert usage.rest.retried_requests == 0
    # failed requests count against the quota as well
    assert usage.rest.quota_cost == {"core": 1}


async def test_revalidated_response_is_a_free_request(github, cached_requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        first = await cached_requester.request_json("GET", "/orgs/acme/etag")
        second = await cached_requester.request_json("GET", "/orgs/acme/etag")

    assert first == second == {"login": "acme"}
    assert github.hits["/orgs/acme/etag"] == 2
    assert usage.rest.total_requests == 2
    assert usage.rest.cached_responses == 1
    assert usage.rest.quota_cost == {"core": 1}


async def test_local_cache_hit_is_not_a_request(github, cached_requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        await cached_requester.request_json("GET", "/orgs/acme/no-etag")
        # without ETag or Last-Modified, the cached response is served without contacting GitHub
        await cached_requester.request_json("GET", "/orgs/acme/no-etag")

    assert github.hits["/orgs/acme/no-etag"] == 1
    assert usage.rest.total_requests == 1
    assert usage.rest.cached_responses == 0


async def test_proxy_cached_response_is_a_free_request(requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        await requester.request_json("GET", "/orgs/acme/proxied")

    assert usage.rest.total_requests == 1
    assert usage.rest.cached_responses == 1
    assert len(usage.rest.quota_cost) == 0
    # its rate limit headers are the ones of the original request
    assert len(usage.rest.rate_limits) == 0


async def test_stream_and_its_redirect_are_requests(requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        content = b"".join([x async for x in requester.request_stream("GET", "/repos/acme/website/zipball/main")])

    assert content == b"zip-content"
    assert usage.rest.total_requests == 2
    assert usage.rest.retried_requests == 0
    # the download from another host carries no rate limit and costs nothing
    assert usage.rest.quota_cost == {"core": 1}
    assert usage.rest.endpoints["GET /repos/{owner}/{repo}/zipball/{ref}"].requests == 2


async def test_rate_limit_snapshot(requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        await requester.request_json("GET", "/meta")

    rate_limit = usage.rest.rate_limits["core"]
    assert (rate_limit.limit, rate_limit.remaining, rate_limit.reset) == (5000, 4990, 1800000000)
    assert usage.rest.remaining_rate_limit == 4990


async def test_concurrent_requests_are_counted_exactly(github, requester):
    run_usage = ApiUsage()
    first = ApiUsage()
    second = ApiUsage()

    async def run(usage: ApiUsage, count: int) -> None:
        with collect_api_usage(usage):
            await asyncio.gather(*[requester.request_raw("GET", "/meta") for _ in range(count)])

    with collect_api_usage(run_usage):
        await asyncio.gather(run(first, 120), run(second, 80))

    assert github.hits["/meta"] == 200
    assert first.rest.total_requests == 120
    assert second.rest.total_requests == 80
    assert run_usage.rest.total_requests == 200
    assert run_usage.rest.quota_cost == {"core": 200}
    assert requester.statistics.total_requests == 200


async def test_cancelled_request_is_interrupted(github, requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        task = asyncio.create_task(requester.request_raw("GET", "/orgs/acme/slow"))
        await asyncio.wait_for(github.request_received.wait(), timeout=10)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    assert usage.rest.total_requests == 1
    assert usage.rest.interrupted_requests == 1
    assert usage.rest.error_count == 0


async def test_graphql_cost_and_errors(github):
    client = GraphQLClient(token_auth(_TOKEN), ghproxy_cache(github.url))
    usage = ApiUsage()

    try:
        with collect_api_usage(usage):
            teams = await client.get_team_membership("acme", "octocat")
            await client.minimize_comment("C1", "OUTDATED")
            with pytest.raises(RuntimeError, match="failed to update branch protection rule"):
                await client.update_branch_protection_rule("acme", "website", "main", "R1", {})
    finally:
        await client.close()

    assert len(teams) == 1
    assert usage.graphql.total_requests == 3
    assert usage.graphql.quota_cost == {"graphql": 3}
    assert usage.graphql.unpriced_requests == 2
    assert usage.graphql.errors == {"graphql:NOT_FOUND": 1}
    assert usage.graphql.endpoints["query get-team-membership"].quota_cost == 3
    assert usage.graphql.endpoints["mutation minimizeComment"].requests == 1
    assert usage.graphql.rate_limits["graphql"].remaining == 4990
    assert usage.rest.total_requests == 0
    assert client.statistics.total_requests == 3


async def test_failure_while_reading_body_is_recorded_once(github, requester):
    usage = ApiUsage()

    with collect_api_usage(usage), pytest.raises(ClientPayloadError):
        await requester.request_raw("GET", "/orgs/acme/truncated")

    assert github.hits["/orgs/acme/truncated"] == 1
    assert usage.rest.total_requests == 1
    assert usage.rest.errors == {"network": 1}
    assert usage.rest.interrupted_requests == 0


async def test_failure_while_caching_body_is_recorded_per_attempt(github, cached_requester):
    usage = ApiUsage()

    with collect_api_usage(usage), pytest.raises(ClientPayloadError):
        await cached_requester.request_raw("GET", "/orgs/acme/truncated")

    # the cached session reads the body to cache it once the response has been recorded, each attempt fails
    assert github.hits["/orgs/acme/truncated"] == 3
    assert usage.rest.total_requests == 3
    assert usage.rest.retried_requests == 2
    assert usage.rest.errors == {"network": 3}


async def test_cancellation_while_reading_body_is_an_interruption(github, requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        task = asyncio.create_task(requester.request_raw("GET", "/orgs/acme/slow-body"))
        await asyncio.wait_for(github.request_received.wait(), timeout=10)
        # let the client receive the headers, so that it is reading the body when cancelled
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    assert usage.rest.total_requests == 1
    assert usage.rest.interrupted_requests == 1
    assert usage.rest.error_count == 0


async def test_stopping_to_read_a_stream_is_no_failure(requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        stream = requester.request_stream("GET", "/repos/acme/website/zipball/main")
        async for _ in stream:
            break
        await stream.aclose()

    assert usage.rest.total_requests == 2
    assert usage.rest.error_count == 0
    assert usage.rest.interrupted_requests == 0


async def test_graphql_response_cached_by_proxy_costs_nothing(github):
    client = GraphQLClient(token_auth(_TOKEN), ghproxy_cache(github.url))
    usage = ApiUsage()

    try:
        with collect_api_usage(usage):
            await client.get_issue_comments("acme", "website", 1)
    finally:
        await client.close()

    assert usage.graphql.total_requests == 1
    assert usage.graphql.cached_responses == 1
    assert len(usage.graphql.quota_cost) == 0
    assert usage.graphql.unpriced_requests == 0
    assert len(usage.graphql.rate_limits) == 0


async def test_failed_graphql_attempts_are_unpriced(github):
    client = GraphQLClient(token_auth(_TOKEN), ghproxy_cache(github.url))
    usage = ApiUsage()

    try:
        with collect_api_usage(usage):
            await client.delete_branch_protection_rule("acme", "website", "main", "R1")
    finally:
        await client.close()

    assert usage.graphql.total_requests == 3
    assert usage.graphql.retried_requests == 2
    assert usage.graphql.errors == {"502": 2}
    # neither the failed attempts nor the mutation report their cost
    assert usage.graphql.unpriced_requests == 3
    assert len(usage.graphql.quota_cost) == 0


async def test_attempt_waiting_for_a_connection_is_not_a_request(github):
    client = GraphQLClient(token_auth(_TOKEN), ghproxy_cache(github.url))
    usage = ApiUsage()

    try:
        with collect_api_usage(usage):
            tasks = [asyncio.create_task(client.get_pull_requests("acme", "website", "main")) for _ in range(11)]
            await asyncio.wait_for(github.graphql_pool_exhausted.wait(), timeout=10)

            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await client.close()

    assert github.hits["/graphql"] == 10
    assert usage.graphql.total_requests == 10
    assert usage.graphql.interrupted_requests == 10
    assert usage.graphql.unsent_attempts == {"interrupted": 1}


async def test_encoded_slash_remains_part_of_a_name(requester):
    usage = ApiUsage()

    with collect_api_usage(usage):
        await requester.request_raw("GET", "/repos/acme/website/environments/preview%2Fprivate-project")

    assert list(usage.rest.endpoints) == ["GET /repos/{owner}/{repo}/environments/{name}"]


async def test_statistics_do_not_leak_secrets(requester):
    report = ApiUsageReport("plan")

    with collect_api_usage(report.total):
        await requester.request_raw("GET", "/orgs/acme/missing", params={"ref": "secret-branch"})

    report.finish("completed")
    serialized = json.dumps(report.to_json())

    assert _TOKEN not in serialized
    assert "secret-branch" not in serialized
    assert "acme" not in serialized
    assert "GET /orgs/{org}/missing" in serialized
