#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException

from . import RestApi, RestClient

_logger = get_logger(__name__)


class UserClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_user_ids(self, login: str) -> tuple[int, str]:
        _logger.debug("retrieving user ids for user '%s'", login)

        try:
            response = await self.requester.request_json("GET", f"/users/{login}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving user node id:\n{ex}") from ex
