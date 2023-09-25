# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Optional, Any

from requests import Response
from requests_cache import CachedSession

from otterdog.providers.github.exception import BadCredentialsException, GitHubException
from otterdog.utils import print_trace

from .auth import AuthStrategy


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
        # logging.basicConfig(level='DEBUG')

        self._session: CachedSession = CachedSession(
            "otterdog",
            backend="filesystem",
            use_cache_dir=True,
            cache_control=True,
            allowable_methods=["GET"],
        )

        self._session.auth = self._auth

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
        self._check_response(response)
        return response.json()

    def request_raw(
        self,
        method: str,
        url_path: str,
        data: Optional[str] = None,
        params: Optional[dict[str, str]] = None,
        stream: bool = False,
    ) -> Response:
        assert method in ["GET", "PATCH", "POST", "PUT", "DELETE"]

        print_trace(f"'{method}' url = {url_path}, data = {data}, headers = {self._headers}")

        response = self._session.request(
            method,
            url=self._build_url(url_path),
            headers=self._headers,
            refresh=True,
            params=params,
            data=data,
            stream=stream,
        )

        print_trace(f"'{method}' result = ({response.status_code}, {response.text})")

        return response

    def _check_response(self, response: Response) -> None:
        if response.status_code >= 400:
            self._create_exception(response)

    @staticmethod
    def _create_exception(response: Response):
        status = response.status_code
        url = response.request.url

        if status == 401:
            raise BadCredentialsException(url, status, response.text)
        else:
            raise GitHubException(url, status, response.text)
