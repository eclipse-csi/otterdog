#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator, Mapping
from typing import Any

from aiohttp import ClientResponse, ClientSession, ClientTimeout, TCPConnector
from aiohttp_client_cache import CacheBackend
from aiohttp_client_cache.session import CachedSession as AsyncCachedSession
from aiohttp_retry import ExponentialRetry, RetryClient

from otterdog.logging import is_trace_enabled
from otterdog.providers.github.auth import AuthStrategy
from otterdog.providers.github.cache import CacheStrategy
from otterdog.providers.github.exception import (
    BadCredentialsException,
    GitHubException,
    InsufficientPermissionsException,
)
from otterdog.providers.github.stats import RequestRecorder, RequestStatistics
from otterdog.utils import get_logger

_logger = get_logger(__name__)

# the maximum number of requests sent concurrently, GitHub answers too many concurrent requests
# with a secondary rate limit
DEFAULT_MAX_CONCURRENT_REQUESTS = 30

# how many times a request that hit a rate limit is sent again
_MAX_RATE_LIMIT_RETRIES = 3
# the wait before sending again a request that hit a secondary rate limit, when GitHub does not tell it,
# doubled for every further retry
_DEFAULT_RATE_LIMIT_WAIT_SECONDS = 60
# the longest wait before sending a request again, a longer one, e.g. until an exhausted primary rate limit
# is reset, fails the request instead
_MAX_RATE_LIMIT_WAIT_SECONDS = 300


def is_rate_limited(status: int, body: str) -> bool:
    """
    Whether a response is due to a primary or secondary rate limit, returned by GitHub with status 403 or 429,
    and a message like 'API rate limit exceeded for ...' or 'You have exceeded a secondary rate limit ...'.
    """
    return status in (403, 429) and "rate limit" in body.lower()


def get_rate_limit_wait(status: int, body: str, headers: Mapping[str, str], retries: int) -> float | None:
    """
    Returns how many seconds to wait before sending again a request whose response hit a rate limit, as recommended
    by GitHub: the time given by the header 'retry-after', or until the reset of an exhausted rate limit, otherwise
    one minute, doubled for every retry.

    Returns None if the response did not hit a rate limit, or if the wait would exceed 5 minutes.
    """
    if not is_rate_limited(status, body):
        return None

    retry_after = headers.get("retry-after", "")
    reset = headers.get("x-ratelimit-reset", "")

    if retry_after.isdigit():
        wait = float(retry_after)
    elif headers.get("x-ratelimit-remaining") == "0" and reset.isdigit():
        wait = max(int(reset) - time.time(), 0) + 1
    else:
        wait = float(_DEFAULT_RATE_LIMIT_WAIT_SECONDS * 2**retries)

    return wait if wait <= _MAX_RATE_LIMIT_WAIT_SECONDS else None


class Requester:
    def __init__(
        self,
        auth_strategy: AuthStrategy | None,
        cache_strategy: CacheStrategy,
        base_url: str,
        api_version: str,
        max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
    ):
        self._auth = auth_strategy.get_auth() if auth_strategy is not None else None

        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
            "X-Github-Next-Global-ID": "1",
        }

        self._statistics = RequestStatistics()
        # every response that is not cached costs one point of the core rate limit, unless stated otherwise
        self._recorder = RequestRecorder("rest", self._statistics, charge_responses=True, default_resource="core")
        self._cache_strategy = cache_strategy

        # requests wait for a slot rather than for a connection of the session, as the wait for a connection
        # counts against the connect timeout
        self._max_concurrent_requests = max_concurrent_requests
        self._request_slots = asyncio.Semaphore(max_concurrent_requests)
        # the monotonic time until which no request is sent, set when a request hits a rate limit
        self._paused_until = 0.0

        if self._cache_strategy.is_external():
            self._base_url = cache_strategy.replace_base_url(f"https://{base_url}")
            self._session = ClientSession(trace_configs=[self._recorder.trace_config()])
        else:
            self._base_url = f"https://{base_url}"
            self._session = AsyncCachedSession(
                cache=self._record_body_failures_while_caching(self._cache_strategy.get_cache_backend()),
                timeout=ClientTimeout(connect=3, sock_connect=3),
                connector=TCPConnector(
                    limit=max_concurrent_requests,
                ),
                trace_configs=[self._recorder.trace_config()],
            )

        self._client = RetryClient(
            retry_options=ExponentialRetry(3, exceptions={Exception}),
            client_session=self._session,
        )

    @property
    def statistics(self) -> RequestStatistics:
        return self._statistics

    @property
    def max_concurrent_requests(self) -> int:
        return self._max_concurrent_requests

    def _record_body_failures_while_caching(self, backend: CacheBackend | None) -> CacheBackend | None:
        """
        A cached session reads the body of a response to cache it before returning the response, i.e. after
        its request has been recorded on receiving the headers, thus a failure while doing so is recorded here.
        """
        if backend is None:
            return None

        save_response = backend.save_response

        async def recording_save_response(response: ClientResponse, *args: Any, **kwargs: Any) -> None:
            with self._recorder.recording_body_failures(response):
                await save_response(response, *args, **kwargs)

        backend.save_response = recording_save_response  # type: ignore[method-assign]
        return backend

    async def close(self) -> None:
        await self._session.close()

    def _build_url(self, url_path: str) -> str:
        return f"{self._base_url}{url_path}"

    async def request_paged_json(
        self,
        method: str,
        url_path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        entries_key: str | None = None,
    ) -> list[dict[str, Any]]:
        return [entry async for entry in self.iter_paged_json(method, url_path, data, params, entries_key)]

    async def iter_paged_json(
        self,
        method: str,
        url_path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        entries_key: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yields the entries of each page in turn, the next page is only requested once all previous are consumed."""
        from urllib import parse

        json_data = None
        if data is not None:
            json_data = json.dumps(data)

        query_params: dict[str, str] | None = {"per_page": "100"}

        while query_params is not None:
            if params is not None:
                query_params.update(params)

            status, body, next_url, _ = await self._request_raw_with_next_link(
                method, url_path, json_data, query_params
            )
            self._check_response(url_path, status, body)
            response = json.loads(body)

            entries = response[entries_key] if entries_key is not None else response

            if next_url is None:
                query_params = None
            else:
                query_params = {k: v[0] for k, v in parse.parse_qs(parse.urlparse(next_url).query).items()}

            for entry in entries:
                yield entry

    async def request_json(
        self,
        method: str,
        url_path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        input_data = None
        if data is not None:
            input_data = json.dumps(data)

        status, body = await self.request_raw(method, url_path, input_data, params)
        self._check_response(url_path, status, body)
        json_result = json.loads(body)
        if is_trace_enabled():
            _logger.trace("'%s' url = %s, json = %s", method, url_path, json.dumps(json_result, indent=2))
        return json_result

    async def request_raw(
        self,
        method: str,
        url_path: str,
        data: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, str]:
        status, body, _, _ = await self._request_raw_with_next_link(method, url_path, data, params)
        _logger.trace("'%s' url = %s, result = (%d)", method, url_path, status)
        return status, body

    async def request_raw_with_scopes(
        self,
        method: str,
        url_path: str,
        data: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, str, str]:
        status, body, _, scopes = await self._request_raw_with_next_link(method, url_path, data, params)
        _logger.trace("'%s' url = %s, result = (%d)", method, url_path, status)
        return status, body, scopes

    async def _request_raw_with_next_link(
        self,
        method: str,
        url_path: str,
        data: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, str, str | None, str]:
        _logger.trace("'%s' url = %s, data = %s, params = %s", method, url_path, data, params)

        retries = 0
        while True:
            async with self._request_slot():
                status, text, next_url, response_headers = await self._send(method, url_path, data, params)

                wait = (
                    get_rate_limit_wait(status, text, response_headers, retries)
                    if retries < _MAX_RATE_LIMIT_RETRIES
                    else None
                )
                if wait is None:
                    break

                # all requests are paused, sending others would only hit the rate limit as well
                self._paused_until = max(self._paused_until, time.monotonic() + wait)

            retries += 1
            _logger.warning(
                "'%s %s' hit a rate limit of GitHub (status=%d), sending it again in %ds (retry %d of %d)",
                method,
                url_path,
                status,
                wait,
                retries,
                _MAX_RATE_LIMIT_RETRIES,
            )
            self._recorder.record_retry()

        self._check_permissions(url_path, status, text, response_headers)

        return (
            status,
            text,
            next_url,
            response_headers.get("X-OAuth-Scopes", ""),
        )

    @contextlib.asynccontextmanager
    async def _request_slot(self) -> AsyncIterator[None]:
        async with self._request_slots:
            while (pause := self._paused_until - time.monotonic()) > 0:
                await asyncio.sleep(pause)

            yield

    async def _send(
        self,
        method: str,
        url_path: str,
        data: str | None,
        params: dict[str, Any] | None,
    ) -> tuple[int, str, str | None, Mapping[str, str]]:
        headers = self._headers.copy()
        if self._auth is not None:
            self._auth.update_headers_with_authorization(headers)

        async with self._client.request(
            method,
            url=self._build_url(url_path),
            headers=headers,
            params=params,
            data=data,
            **self._cache_strategy.get_request_parameters(),
        ) as response:
            with self._recorder.recording_body_failures(response):
                text = await response.text()

            links = response.links
            next_link = links.get("next", None) if links is not None else None
            next_url = next_link.get("url", None) if next_link is not None else None

            return response.status, text, str(next_url) if next_url is not None else None, response.headers

    async def request_stream(
        self,
        method: str,
        url_path: str,
        data: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterable[bytes]:
        _logger.trace(
            "stream '%s' url = %s, data = %s, headers = %s",
            method,
            url_path,
            data,
            self._headers,
        )

        headers = self._headers.copy()
        if self._auth is not None:
            self._auth.update_headers_with_authorization(headers)

        url = self._build_url(url_path)
        async with self._client.request(
            method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            **self._cache_strategy.get_request_parameters(),
        ) as response:
            with self._recorder.recording_body_failures(response):
                async for chunk, _ in response.content.iter_chunks():
                    yield chunk

    def _check_response(self, url_path: str, status_code: int, body: str) -> None:
        if status_code >= 400:
            self._create_exception(self._build_url(url_path), status_code, body)

    @staticmethod
    def _check_permissions(url_path: str, status_code: int, body: str, headers: Mapping[str, str]):
        if status_code == 403:
            existing_scopes = {x.strip() for x in headers.get("X-OAuth-Scopes", "").split(",") if len(x) > 0}
            required_scopes = {x.strip() for x in headers.get("X-Accepted-OAuth-Scopes", "").split(",") if len(x) > 0}

            missing_scopes = required_scopes - existing_scopes
            if len(missing_scopes) > 0:
                raise InsufficientPermissionsException(url_path, status_code, body, list(missing_scopes))

    @staticmethod
    def _create_exception(url: str, status_code: int, body: str):
        if status_code == 401:
            raise BadCredentialsException(url, body)
        else:
            raise GitHubException(url, status_code, body)
