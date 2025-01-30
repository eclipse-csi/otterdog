#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from collections.abc import AsyncIterable, Mapping
from typing import Any

from aiohttp import ClientSession, ClientTimeout, TCPConnector
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
from otterdog.providers.github.stats import RequestStatistics
from otterdog.utils import get_logger

_logger = get_logger(__name__)


class Requester:
    def __init__(
        self,
        auth_strategy: AuthStrategy | None,
        cache_strategy: CacheStrategy,
        base_url: str,
        api_version: str,
    ):
        self._auth = auth_strategy.get_auth() if auth_strategy is not None else None

        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
            "X-Github-Next-Global-ID": "1",
        }

        self._statistics = RequestStatistics()
        self._cache_strategy = cache_strategy

        if self._cache_strategy.is_external():
            self._base_url = cache_strategy.replace_base_url(f"https://{base_url}")
            self._session = ClientSession()
        else:
            self._base_url = f"https://{base_url}"
            self._session = AsyncCachedSession(
                cache=self._cache_strategy.get_cache_backend(),
                timeout=ClientTimeout(connect=3, sock_connect=3),
                connector=TCPConnector(
                    limit=30,
                ),
            )

        self._client = RetryClient(
            retry_options=ExponentialRetry(3, exceptions={Exception}),
            client_session=self._session,
        )

    @property
    def statistics(self) -> RequestStatistics:
        return self._statistics

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
        from urllib import parse

        json_data = None
        if data is not None:
            json_data = json.dumps(data)

        result = []
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

            for item in entries:
                result.append(item)

        return result

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
            self._statistics.sent_request()

            text = await response.text()
            status = response.status
            links = response.links
            next_link = links.get("next", None) if links is not None else None
            next_url = next_link.get("url", None) if next_link is not None else None

            self._check_permissions(url_path, status, text, response.headers)

            if (hasattr(response, "from_cache") and response.from_cache) or response.headers.get(
                "X-From-Cache", 0
            ) == "1":
                self._statistics.received_cached_response()
            else:
                self._statistics.update_remaining_rate_limit(int(response.headers.get("x-ratelimit-remaining", -1)))

            return (
                status,
                text,
                str(next_url) if next_url is not None else None,
                response.headers.get("X-OAuth-Scopes", ""),
            )

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
