#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.utils import print_debug

from ..exception import GitHubException
from . import RestApi, RestClient


class UserClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_user_ids(self, login: str) -> tuple[int, str]:
        print_debug(f"retrieving user ids for user '{login}'")

        try:
            response = await self.requester.async_request_json("GET", f"/users/{login}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving user node id:\n{ex}").with_traceback(tb)
