#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.providers.github.exception import GitHubException
from otterdog.utils import print_debug

from . import RestApi, RestClient


class IssueClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    def create_comment(self, org_id: str, repo_name: str, issue_number: str, body: str) -> None:
        print_debug(f"creating issue comment for issue '{issue_number}' at '{org_id}/{repo_name}'")

        try:
            data = {"body": body}
            return self.requester.request_json(
                "POST", f"/repos/{org_id}/{repo_name}/issues/{issue_number}/comments", data=data
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed creating issue comment:\n{ex}").with_traceback(tb)
