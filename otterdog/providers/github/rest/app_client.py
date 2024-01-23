#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from otterdog.utils import print_debug

from ..exception import GitHubException
from . import RestApi, RestClient


class AppClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    def get_authenticated_app(self) -> dict[str, Any]:
        print_debug("retrieving authenticated app")

        try:
            return self.requester.request_json("GET", "/app")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving authenticated app:\n{ex}").with_traceback(tb)

    def get_app_ids(self, app_slug: str) -> tuple[int, str]:
        print_debug("retrieving app node id")

        try:
            response = self.requester.request_json("GET", f"/apps/{app_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving app node id:\n{ex}").with_traceback(tb)
