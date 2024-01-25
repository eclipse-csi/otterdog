#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any, Optional

from aiohttp_client_cache.backends import FileBackend
from aiohttp_client_cache.session import CachedSession as AsyncCachedSession
from requests import Response
from requests_cache import CachedSession

from otterdog.providers.github.auth import AuthStrategy
from otterdog.providers.github.exception import BadCredentialsException, GitHubException
from otterdog.utils import is_debug_enabled, is_trace_enabled, print_debug, print_trace

_AIOHTTP_CACHE_DIR = ".cache/async_http"
_REQUESTS_CACHE_DIR = ".cache/http"


class Requester:
    def __init__(self, auth_strategy: AuthStrategy, base_url: str, api_version: str):
        self._base_url = base_url
        self._auth = auth_strategy.get_auth()

        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
            "X-Github-Next-Global-ID": "1",
        }

        # enable logging for requests_cache
        # import logging
        #
        #
        # logging.basicConfig(level='DEBUG')

        self._session: CachedSession = CachedSession(
            _REQUESTS_CACHE_DIR,
            backend="filesystem",
            use_cache_dir=False,
            cache_control=True,
            allowable_methods=["GET"],
        )
        self._session.auth = self._auth

    def close(self) -> None:
        self._session.close()

    def _build_url(self, url_path: str) -> str:
        return f"{self._base_url}{url_path}"

    def request_paged_json(
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

            response: list[dict[str, Any]] = self.request_json(method, url_path, data, query_params)

            if len(response) == 0:
                current_page = -1
            else:
                for item in response:
                    result.append(item)

                current_page += 1

        return result

    async def async_request_paged_json(
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

            response: list[dict[str, Any]] = await self.async_request_json(method, url_path, data, query_params)

            if len(response) == 0:
                current_page = -1
            else:
                for item in response:
                    result.append(item)

                current_page += 1

        return result

    def request_json(
        self,
        method: str,
        url_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        input_data = None
        if data is not None:
            input_data = json.dumps(data)

        response = self.request_raw(method, url_path, input_data, params)
        self._check_response(response.url, response.status_code, response.text)
        return response.json()

    async def async_request_json(
        self,
        method: str,
        url_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        input_data = None
        if data is not None:
            input_data = json.dumps(data)

        status, body = await self.async_request_raw(method, url_path, input_data, params)
        self._check_response(url_path, status, body)
        return json.loads(body)

    def request_raw(
        self,
        method: str,
        url_path: str,
        data: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        stream: bool = False,
        force_refresh: bool = False,
    ) -> Response:
        print_trace(f"'{method}' url = {url_path}, data = {data}, headers = {self._headers}")

        response = self._session.request(
            method,
            url=self._build_url(url_path),
            headers=self._headers,
            refresh=True,
            force_refresh=force_refresh,
            params=params,
            data=data,
            stream=stream,
        )

        if is_debug_enabled():
            print_debug(f"'{method}' {url_path}: rate-limit-used = {response.headers.get('x-ratelimit-used', None)}")

        if is_trace_enabled():
            print_trace(f"'{method}' result = ({response.status_code}, {response.text})")

        return response

    async def async_request_raw(
        self,
        method: str,
        url_path: str,
        data: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> tuple[int, str]:
        print_trace(f"async '{method}' url = {url_path}, data = {data}, headers = {self._headers}")

        headers = self._headers.copy()
        self._auth.update_headers_with_authorization(headers)

        async with AsyncCachedSession(cache=FileBackend(cache_name=_AIOHTTP_CACHE_DIR, use_temp=False)) as session:
            url = self._build_url(url_path)
            async with session.request(
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

    def _check_response(self, url_path: str, status_code: int, body: str) -> None:
        if status_code >= 400:
            self._create_exception(self._build_url(url_path), status_code, body)

    @staticmethod
    def _create_exception(url: str, status_code: int, body: str):
        if status_code == 401:
            raise BadCredentialsException(url, status_code, body)
        else:
            raise GitHubException(url, status_code, body)
