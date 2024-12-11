#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from datetime import datetime
from typing import Any

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException

from . import RestApi, RestClient, parse_iso_date_string

_logger = get_logger(__name__)


class AppClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_authenticated_app(self) -> dict[str, Any]:
        _logger.debug("retrieving authenticated app")

        try:
            return await self.requester.request_json("GET", "/app")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving authenticated app:\n{ex}") from ex

    async def get_app_installations(self) -> list[dict[str, Any]]:
        _logger.debug("retrieving app installations")

        try:
            return await self.requester.request_paged_json("GET", "/app/installations")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving app installations:\n{ex}") from ex

    async def get_app_installation(self, installation_id: int) -> dict[str, Any]:
        _logger.debug("retrieving app installation for id '%d'", installation_id)

        try:
            return await self.requester.request_json("GET", f"/app/installations/{installation_id}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving app installation:\n{ex}") from ex

    async def create_installation_access_token(self, installation_id: str) -> tuple[str, datetime]:
        _logger.debug("creating an installation access token for installation '%s'", installation_id)

        try:
            response = await self.requester.request_json("POST", f"/app/installations/{installation_id}/access_tokens")
            return response["token"], parse_iso_date_string(response["expires_at"])
        except GitHubException as ex:
            raise RuntimeError(f"failed creating installation access token:\n{ex}") from ex

    async def get_app_ids(self, app_slug: str) -> tuple[int, str]:
        _logger.debug("retrieving app node id")

        try:
            response = await self.requester.request_json("GET", f"/apps/{app_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving app node id:\n{ex}") from ex
