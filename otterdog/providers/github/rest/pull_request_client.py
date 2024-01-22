#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from typing import Any

from otterdog.providers.github.exception import GitHubException
from otterdog.utils import print_debug

from . import RestApi, RestClient


class PullRequestClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    def get_pull_request(self, org_id: str, repo_name: str, pull_request_number: str) -> dict[str, Any]:
        print_debug(f"getting pull request with number '{pull_request_number}' from repo '{org_id}/{repo_name}'")

        try:
            return self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving pull request:\n{ex}").with_traceback(tb)
