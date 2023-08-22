# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from otterdog.utils import print_debug

from . import RestApi, RestClient
from ..exception import GitHubException


class AppClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    def get_app_ids(self, app_slug: str) -> tuple[int, str]:
        print_debug("retrieving app node id")

        try:
            response = self.requester.request_json("GET", f"/apps/{app_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving app node id:\n{ex}").with_traceback(tb)
