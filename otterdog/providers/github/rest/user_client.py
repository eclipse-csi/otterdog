#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.utils import print_debug

from . import RestApi, RestClient
from ..exception import GitHubException


class UserClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    def get_user_ids(self, login: str) -> tuple[int, str]:
        print_debug(f"retrieving user ids for user '{login}'")

        try:
            response = self.requester.request_json("GET", f"/users/{login}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving user node id:\n{ex}").with_traceback(tb)
