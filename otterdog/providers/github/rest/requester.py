#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any, AsyncIterable, Optional

from aiohttp_client_cache.backends import FileBackend
from aiohttp_client_cache.session import CachedSession as AsyncCachedSession

from otterdog.providers.github.auth import AuthStrategy
from otterdog.providers.github.exception import BadCredentialsException, GitHubException
from otterdog.utils import is_debug_enabled, is_trace_enabled, print_debug, print_trace

_AIOHTTP_CACHE_DIR = ".cache/async_http"


class Requester:
    def __init__(self, auth_strategy: Optional[AuthStrategy], base_url: str, api_version: str):
        self._base_url = base_url
        self._auth = auth_strategy.get_auth() if auth_strategy is not None else None

        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
            "X-Github-Next-Global-ID": "1",
        }

        self._async_session = AsyncCachedSession(
            cache=FileBackend(
                cache_name=_AIOHTTP_CACHE_DIR,
                use_temp=False,
            ),
        )

    async def close(self) -> None:
        await self._async_session.close()

    def _build_url(self, url_path: str) -> str:
        return f"{self._base_url}{url_path}"

    async def request_paged_json(
        self,
        method: str,
        url_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> list[dict[str, Any]]:
        result = []
        current_page = 1
        while current_page > 0:
            query_params = {"per_page": "100", "page": current_page}
            if params is not None:
                query_params.update(params)

            response: list[dict[str, Any]] = await self.request_json(method, url_path, data, query_params)

            if len(response) == 0:
                current_page = -1
            else:
                for item in response:
                    result.append(item)

                current_page += 1

        return result

    async def request_json(
        self,
        method: str,
        url_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        input_data = None
        if data is not None:
            input_data = json.dumps(data)

        status, body = await self.request_raw(method, url_path, input_data, params)
        self._check_response(url_path, status, body)
        return json.loads(body)

    async def request_raw(
        self,
        method: str,
        url_path: str,
        data: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> tuple[int, str]:
        print_trace(f"'{method}' url = {url_path}, data = {data}, headers = {self._headers}")

        headers = self._headers.copy()
        if self._auth is not None:
            self._auth.update_headers_with_authorization(headers)

        url = self._build_url(url_path)
        async with self._async_session.request(
            method, url=url, headers=headers, params=params, data=data, refresh=True
        ) as response:
            text = await response.text()
            status = response.status

            if is_debug_enabled():
                if not response.from_cache:  # type: ignore
                    print_debug(
                        f"'{method}' {url_path}: rate-limit-used = {response.headers.get('x-ratelimit-used', None)}"
                    )

            if is_trace_enabled():
                print_trace(f"async '{method}' result = ({status}, {text})")

            return status, text

    async def request_stream(
        self,
        method: str,
        url_path: str,
        data: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterable[bytes]:
        print_trace(f"stream '{method}' url = {url_path}, data = {data}, headers = {self._headers}")

        headers = self._headers.copy()
        if self._auth is not None:
            self._auth.update_headers_with_authorization(headers)

        url = self._build_url(url_path)
        async with self._async_session.request(
            method, url=url, headers=headers, params=params, data=data, refresh=True
        ) as response:
            async for chunk, _ in response.content.iter_chunks():
                yield chunk

    def _check_response(self, url_path: str, status_code: int, body: str) -> None:
        if status_code >= 400:
            self._create_exception(self._build_url(url_path), status_code, body)

    @staticmethod
    def _create_exception(url: str, status_code: int, body: str):
        if status_code == 401:
            raise BadCredentialsException(url, status_code, body)
        else:
            raise GitHubException(url, status_code, body)
