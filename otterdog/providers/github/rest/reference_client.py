#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from otterdog.providers.github.exception import GitHubException
from otterdog.utils import print_debug

from . import RestApi, RestClient


class ReferenceClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_branch_reference(self, org_id: str, repo_name: str, branch_name: str) -> dict[str, Any]:
        print_debug(f"getting branch reference with name '{branch_name}' from repo '{org_id}/{repo_name}'")

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/git/ref/heads/{branch_name}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving reference:\n{ex}").with_traceback(tb)

    async def create_reference(self, org_id: str, repo_name: str, ref: str, sha: str) -> str:
        print_debug(f"creating reference with name '{ref}' and sha '{sha}' for repo '{org_id}/{repo_name}'")

        try:
            data = {
                "ref": f"refs/heads/{ref}",
                "sha": sha,
            }

            await self.requester.request_json("POST", f"/repos/{org_id}/{repo_name}/git/refs", data=data)
            return data["ref"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed creating reference:\n{ex}").with_traceback(tb)
