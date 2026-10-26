#  *******************************************************************************
#  Copyright (c) 2024-2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Statistics about the requests sent to GitHub.

Every HTTP request that leaves the process is counted exactly once, when it terminates, including
every page of a paginated result and every retried attempt. It is then classified into subsets:
retries, errors, cached responses and interrupted requests. A response served from a local cache
without contacting GitHub never reaches the network and is thus not counted at all.

The quota cost is tracked apart from the number of requests. For the REST api, it is estimated as
one point per response that is neither revalidated (304) nor served by a caching proxy, for the
GraphQL api it is the cost GitHub reports in the body of a query response.
"""

from __future__ import annotations

import contextlib
import dataclasses
import time
from asyncio import CancelledError
from collections import Counter
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from otterdog.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from types import SimpleNamespace
    from typing import Any

    from aiohttp import (
        ClientSession,
        TraceConfig,
        TraceRequestEndParams,
        TraceRequestExceptionParams,
        TraceRequestRedirectParams,
        TraceRequestStartParams,
    )

_logger = get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class RateLimit:
    resource: str
    limit: int
    remaining: int
    # epoch seconds at which the current window ends
    reset: int

    def to_json(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "reset": datetime.fromtimestamp(self.reset, UTC).isoformat() if self.reset > 0 else None,
        }


@dataclasses.dataclass
class EndpointStatistics:
    requests: int = 0
    quota_cost: int = 0


@dataclasses.dataclass(frozen=True)
class RequestOutcome:
    endpoint: str
    retry: bool = False
    error: str | None = None
    cached: bool = False
    interrupted: bool = False
    # the resource charged with one point for this request, if any
    quota_resource: str | None = None
    rate_limit: RateLimit | None = None


@dataclasses.dataclass
class RequestStatistics:
    total_requests: int = 0
    retried_requests: int = 0
    cached_responses: int = 0
    interrupted_requests: int = 0
    unpriced_requests: int = 0
    errors: Counter[str] = dataclasses.field(default_factory=Counter)
    quota_cost: Counter[str] = dataclasses.field(default_factory=Counter)
    endpoints: dict[str, EndpointStatistics] = dataclasses.field(default_factory=dict)
    rate_limits: dict[str, RateLimit] = dataclasses.field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(self.errors.values())

    @property
    def remaining_rate_limit(self) -> int:
        if len(self.rate_limits) == 0:
            return -1
        else:
            return min(x.remaining for x in self.rate_limits.values())

    def record(self, outcome: RequestOutcome) -> None:
        self.total_requests += 1
        self._endpoint(outcome.endpoint).requests += 1

        if outcome.retry:
            self.retried_requests += 1

        if outcome.error is not None:
            self.errors[outcome.error] += 1

        if outcome.cached:
            self.cached_responses += 1

        if outcome.interrupted:
            self.interrupted_requests += 1

        if outcome.quota_resource is not None:
            self.add_quota_cost(outcome.quota_resource, 1, outcome.endpoint)

        if outcome.rate_limit is not None:
            self.update_rate_limit(outcome.rate_limit)

    def record_retry(self) -> None:
        self.retried_requests += 1

    def record_error(self, error: str) -> None:
        """Records an error carried by the body of a response that did not fail by its status."""
        self.errors[error] += 1

    def record_failure(self, error: str | None, interrupted: bool) -> None:
        """Records the failure of a request that has been recorded as successful, e.g. while reading its body."""
        if interrupted:
            self.interrupted_requests += 1
        elif error is not None:
            self.errors[error] += 1

    def record_unpriced_request(self) -> None:
        self.unpriced_requests += 1

    def add_quota_cost(self, resource: str, cost: int, endpoint: str) -> None:
        self.quota_cost[resource] += cost
        self._endpoint(endpoint).quota_cost += cost

    def update_rate_limit(self, rate_limit: RateLimit, now: float | None = None) -> None:
        current = self.rate_limits.get(rate_limit.resource)
        if current is None or self._supersedes(rate_limit, current, time.time() if now is None else now):
            self.rate_limits[rate_limit.resource] = rate_limit

    @staticmethod
    def _supersedes(rate_limit: RateLimit, current: RateLimit, now: float) -> bool:
        if rate_limit.reset > current.reset and now >= current.reset:
            # the window of the current value has ended, the quota has been reset since
            return True

        if rate_limit.reset < current.reset and now >= rate_limit.reset:
            # a delayed response of a window that has ended already
            return False

        # keep the lowest remaining quota of the current window, as responses of concurrent requests arrive
        # in any order, and a later reset time does not mean a new window: GitHub reports a reset time
        # moving along with the current time for responses that do not reflect any consumption yet.
        return rate_limit.remaining < current.remaining

    def merge(self, other: RequestStatistics) -> None:
        self.total_requests += other.total_requests
        self.retried_requests += other.retried_requests
        self.cached_responses += other.cached_responses
        self.interrupted_requests += other.interrupted_requests
        self.unpriced_requests += other.unpriced_requests
        self.errors.update(other.errors)
        self.quota_cost.update(other.quota_cost)

        for endpoint, endpoint_statistics in other.endpoints.items():
            current = self._endpoint(endpoint)
            current.requests += endpoint_statistics.requests
            current.quota_cost += endpoint_statistics.quota_cost

        for rate_limit in other.rate_limits.values():
            self.update_rate_limit(rate_limit)

    def summary(self) -> str:
        return (
            f"{self.total_requests} request(s) ({self.retried_requests} retries, {self.error_count} errors, "
            f"{self.cached_responses} cached)"
        )

    def to_json(self, include_endpoints: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "requests": self.total_requests,
            "retries": self.retried_requests,
            "errors": dict(sorted(self.errors.items())),
            "cached": self.cached_responses,
            "interrupted": self.interrupted_requests,
            "quota_cost": dict(sorted(self.quota_cost.items())),
            "unpriced_requests": self.unpriced_requests,
        }

        if include_endpoints:
            result["endpoints"] = {
                endpoint: dataclasses.asdict(endpoint_statistics)
                for endpoint, endpoint_statistics in sorted(
                    self.endpoints.items(), key=lambda x: (-x[1].requests, x[0])
                )
            }

        return result

    def _endpoint(self, endpoint: str) -> EndpointStatistics:
        return self.endpoints.setdefault(endpoint, EndpointStatistics())


@dataclasses.dataclass
class ApiUsage:
    """The statistics of the requests sent to GitHub, per api."""

    rest: RequestStatistics = dataclasses.field(default_factory=RequestStatistics)
    graphql: RequestStatistics = dataclasses.field(default_factory=RequestStatistics)
    # page loads of the web interface, they do not count against any api quota
    web: RequestStatistics = dataclasses.field(default_factory=RequestStatistics)

    def of(self, api: str) -> RequestStatistics:
        match api:
            case "rest":
                return self.rest
            case "graphql":
                return self.graphql
            case "web":
                return self.web
            case _:
                raise ValueError(f"unknown api '{api}'")

    def items(self) -> Iterator[tuple[str, RequestStatistics]]:
        yield "rest", self.rest
        yield "graphql", self.graphql
        yield "web", self.web

    def combined(self) -> RequestStatistics:
        result = RequestStatistics()
        for statistics in (self.rest, self.graphql, self.web):
            result.merge(statistics)
        return result

    def summary(self) -> str:
        used_apis = [
            f"{api}: {statistics.summary()}" for api, statistics in self.items() if statistics.total_requests > 0
        ]
        return ", ".join(used_apis) if len(used_apis) > 0 else "no requests"


_active_usages: ContextVar[tuple[ApiUsage, ...]] = ContextVar("otterdog_github_api_usages", default=())


@contextlib.contextmanager
def collect_api_usage(usage: ApiUsage) -> Iterator[ApiUsage]:
    """
    Records every request sent to GitHub within the current context into the given usage, in
    addition to the usages collected by any enclosing context.

    Tasks created within the context, including the one run by asyncio.run, inherit it.
    """
    token = _active_usages.set((*_active_usages.get(), usage))
    try:
        yield usage
    finally:
        _active_usages.reset(token)


def is_proxy_cached(headers: Mapping[str, str]) -> bool:
    """Returns whether a response has been served from its cache by a caching proxy, e.g. ghproxy."""
    return headers.get("X-From-Cache") == "1"


def _classify_failure(exception: BaseException) -> tuple[str | None, bool]:
    """Returns the error of a request that failed with the given exception, and whether it was interrupted."""
    if isinstance(exception, CancelledError | KeyboardInterrupt):
        return None, True
    elif isinstance(exception, TimeoutError):
        return "timeout", False
    else:
        return "network", False


class RequestRecorder:
    """
    Records the requests of a client into its own statistics and into the usages collected by
    the current context, see collect_api_usage.

    All updates happen synchronously on the thread running the event loop, so requests that are
    executed concurrently on that loop do not need any further synchronization.
    """

    def __init__(
        self,
        api: str,
        statistics: RequestStatistics,
        charge_responses: bool = False,
        default_resource: str | None = None,
    ) -> None:
        self._api = api
        self._statistics = statistics
        # whether every response that is not cached costs one point of its rate limit resource
        self._charge_responses = charge_responses
        # the rate limit resource used if a response does not specify it
        self._default_resource = default_resource

    def trace_config(self) -> TraceConfig:
        from aiohttp import TraceConfig

        trace_config = TraceConfig()
        trace_config.on_request_start.append(self._on_request_start)
        trace_config.on_request_redirect.append(self._on_request_response)
        trace_config.on_request_end.append(self._on_request_response)
        trace_config.on_request_exception.append(self._on_request_exception)
        return trace_config

    def record(self, outcome: RequestOutcome) -> None:
        for statistics in self._targets():
            statistics.record(outcome)

    def record_retry(self) -> None:
        for statistics in self._targets():
            statistics.record_retry()

    def record_error(self, error: str) -> None:
        for statistics in self._targets():
            statistics.record_error(error)

    def record_unpriced_request(self) -> None:
        for statistics in self._targets():
            statistics.record_unpriced_request()

    def add_quota_cost(self, resource: str, cost: int, endpoint: str) -> None:
        for statistics in self._targets():
            statistics.add_quota_cost(resource, cost, endpoint)

    @contextlib.contextmanager
    def recording_body_failures(self, status: int) -> Iterator[None]:
        """
        Records a failure while reading the body of a response, as its request has already been
        recorded once its headers were received.
        """
        try:
            yield
        except GeneratorExit:
            # the consumer of a streamed body stopped reading it, which is not a failure
            raise
        except BaseException as ex:
            # a failed status has already been recorded as error
            if status < 400:
                error, interrupted = _classify_failure(ex)
                for statistics in self._targets():
                    statistics.record_failure(error, interrupted)
            raise

    def _targets(self) -> Iterator[RequestStatistics]:
        yield self._statistics
        for usage in _active_usages.get():
            yield usage.of(self._api)

    # recording statistics must never interfere with the request itself,
    # thus none of the trace callbacks lets an exception escape.
    # aiohttp awaits trace callbacks, so they are coroutines even though they do not await anything.

    async def _on_request_start(  # NOSONAR - aiohttp requires coroutines as trace callbacks
        self,
        session: ClientSession,
        context: SimpleNamespace,
        params: TraceRequestStartParams,
    ) -> None:
        try:
            request_context = context.trace_request_ctx if isinstance(context.trace_request_ctx, dict) else {}
            context.endpoint = request_context.get("endpoint") or rest_endpoint(params.method, params.url.path)
            # attempts are counted by aiohttp_retry starting with 1
            context.retry = request_context.get("current_attempt", 1) > 1
        except Exception:
            _logger.debug("failed to prepare recording of request statistics", exc_info=True)

    async def _on_request_response(  # NOSONAR - aiohttp requires coroutines as trace callbacks
        self,
        session: ClientSession,
        context: SimpleNamespace,
        params: TraceRequestEndParams | TraceRequestRedirectParams,
    ) -> None:
        try:
            response = params.response
            cached = response.status == 304 or is_proxy_cached(response.headers)
            rate_limit = self._rate_limit(response.headers)

            if self._charge_responses and rate_limit is not None and not cached:
                quota_resource = rate_limit.resource
            else:
                quota_resource = None

            self.record(
                RequestOutcome(
                    self._endpoint(context, params),
                    retry=self._is_retry(context),
                    error=str(response.status) if response.status >= 400 else None,
                    cached=cached,
                    quota_resource=quota_resource,
                    rate_limit=rate_limit,
                )
            )
        except Exception:
            _logger.debug("failed to record request statistics", exc_info=True)

    async def _on_request_exception(  # NOSONAR - aiohttp requires coroutines as trace callbacks
        self,
        session: ClientSession,
        context: SimpleNamespace,
        params: TraceRequestExceptionParams,
    ) -> None:
        try:
            error, interrupted = _classify_failure(params.exception)
            self.record(
                RequestOutcome(
                    self._endpoint(context, params),
                    retry=self._is_retry(context),
                    error=error,
                    interrupted=interrupted,
                )
            )
        except Exception:
            _logger.debug("failed to record request statistics", exc_info=True)

    @staticmethod
    def _endpoint(
        context: SimpleNamespace,
        params: TraceRequestEndParams | TraceRequestRedirectParams | TraceRequestExceptionParams,
    ) -> str:
        # redirects keep the endpoint of the original request
        endpoint = getattr(context, "endpoint", None)
        return endpoint if endpoint is not None else rest_endpoint(params.method, params.url.path)

    @staticmethod
    def _is_retry(context: SimpleNamespace) -> bool:
        # only the first request of a retried attempt is a retry, not the redirects it follows
        retry = getattr(context, "retry", False)
        context.retry = False
        return retry

    def _rate_limit(self, headers: Mapping[str, str]) -> RateLimit | None:
        remaining = headers.get("x-ratelimit-remaining")
        resource = headers.get("x-ratelimit-resource", self._default_resource)

        if remaining is None or resource is None:
            return None

        return RateLimit(
            resource,
            int(headers.get("x-ratelimit-limit", -1)),
            int(remaining),
            int(headers.get("x-ratelimit-reset", 0)),
        )


# collections whose next path segment identifies one of their items, e.g. /environments/{name}
_ITEM_COLLECTIONS = frozenset(
    {
        "apps",
        "artifacts",
        "blocks",
        "collaborators",
        "comments",
        "configurations",
        "deployment-branch-policies",
        "environments",
        "hooks",
        "installations",
        "invitations",
        "issues",
        "labels",
        "members",
        "memberships",
        "organization-roles",
        "outside_collaborators",
        "public_members",
        "pulls",
        "repositories",
        "rulesets",
        "runs",
        "schema",
        "secrets",
        "statuses",
        "teams",
        "variables",
        "workflows",
    }
)

# literal segments that may directly follow an item collection, e.g. /secrets/public-key
_COLLECTION_LITERALS = frozenset({"defaults", "public-key", "teams"})

_ID_PLACEHOLDER = "{id}"
_NAME_PLACEHOLDER = "{name}"
_REF_PLACEHOLDER = "{ref}"

# collections whose items have dedicated placeholders, e.g. /repos/{owner}/{repo}
_NAMED_ITEMS = {
    "orgs": ("{org}",),
    "repos": ("{owner}", "{repo}"),
    "users": ("{user}",),
}

# collections whose remaining path identifies one of their items, e.g. /contents/{path}
_PATH_COLLECTIONS = {
    "contents": "{path}",
    "tarball": _REF_PLACEHOLDER,
    "zipball": _REF_PLACEHOLDER,
}

# collections whose items may contain slashes, with the routes that may follow an item and their
# method, e.g. POST /branches/feature/x/rename. A route only follows an item if the remaining path
# matches it completely, any other path is replaced together with the item.
_SLASHED_ITEM_ROUTES: dict[str, dict[tuple[str, ...], str]] = {
    "branches": {("rename",): "POST"},
    "commits": {("pulls",): "GET", ("statuses",): "GET"},
}


def rest_endpoint(method: str, path: str) -> str:
    """
    Returns the endpoint of a REST request, i.e. its method and path with any segment that
    identifies a resource replaced by a placeholder.

    Requests to the same endpoint for different organizations, repositories or other resources
    are thus accounted together, and no names or ids end up in the statistics.
    """

    method = method.upper()
    segments = [x for x in path.split("/") if len(x) > 0]
    result = []

    index = 0
    while index < len(segments):
        segment = segments[index]
        index += 1

        result.append(_ID_PLACEHOLDER if segment.isdigit() else segment)

        placeholders, replaced_segments = _item_placeholders(method, segment, segments[index:])
        result.extend(placeholders)
        index += replaced_segments

    return f"{method} /{'/'.join(result)}"


def _item_placeholders(method: str, segment: str, following_segments: list[str]) -> tuple[list[str], int]:
    """
    Returns the placeholders for the segments that follow the given one and identify an item
    of it, together with the number of segments they replace.
    """

    if segment.isdigit() or len(following_segments) == 0:
        return [], 0

    if segment in _PATH_COLLECTIONS:
        return [_PATH_COLLECTIONS[segment]], len(following_segments)

    if segment == "git":
        # e.g. git/refs/heads/main or git/matching-refs/tags/v1
        placeholders = following_segments[:1] + ([_REF_PLACEHOLDER] if len(following_segments) > 1 else [])
        return placeholders, len(following_segments)

    if segment in _SLASHED_ITEM_ROUTES:
        return [_NAME_PLACEHOLDER], _slashed_item_length(method, following_segments, _SLASHED_ITEM_ROUTES[segment])

    if segment in _NAMED_ITEMS:
        placeholders = list(_NAMED_ITEMS[segment][: len(following_segments)])
        return placeholders, len(placeholders)

    item = following_segments[0]
    if segment in _ITEM_COLLECTIONS and item not in _COLLECTION_LITERALS:
        return [_ID_PLACEHOLDER if item.isdigit() else _NAME_PLACEHOLDER], 1

    return [], 0


def _slashed_item_length(method: str, following_segments: list[str], routes: dict[tuple[str, ...], str]) -> int:
    """
    Returns the number of segments of an item that may contain slashes: all of them, unless the
    path following one segment at least is a route used with the given method.
    """
    for length in range(1, len(following_segments)):
        if routes.get(tuple(following_segments[length:])) == method:
            return length

    return len(following_segments)
