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

    async def get_branch_reference(self, owner: str, repo: str, branch_name: str) -> dict[str, Any]:
        print_debug(f"getting branch reference with name '{branch_name}' from repo '{owner}/{repo}'")

        try:
            return await self.requester.request_json("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch_name}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving reference for repo '{owner}/{repo}':\n{ex}") from ex

    async def get_matching_references(self, owner: str, repo: str, ref_pattern: str) -> list[dict[str, Any]]:
        print_debug(f"getting matching references with pattern '{ref_pattern}' from repo '{owner}/{repo}'")

        try:
            return await self.requester.request_json("GET", f"/repos/{owner}/{repo}/git/matching-refs/{ref_pattern}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving matching references for repo '{owner}/{repo}':\n{ex}") from ex

    async def create_reference(self, owner: str, repo: str, ref: str, sha: str) -> str:
        print_debug(f"creating reference with name '{ref}' and sha '{sha}' in repo '{owner}/{repo}'")

        try:
            data = {
                "ref": f"refs/heads/{ref}",
                "sha": sha,
            }

            await self.requester.request_json("POST", f"/repos/{owner}/{repo}/git/refs", data=data)
            return data["ref"]
        except GitHubException as ex:
            raise RuntimeError(f"failed creating reference in repo '{owner}/{repo}':\n{ex}") from ex

    async def delete_reference(self, owner: str, repo: str, ref: str) -> bool:
        print_debug(f"deleting reference with name '{ref}' in repo '{owner}/{repo}'")

        full_ref = f"refs/heads/{ref}"
        status, body = await self.requester.request_raw("DELETE", f"/repos/{owner}/{repo}/git/{full_ref}")
        if status == 204:
            return True
        elif status in (409, 422):
            return False
        else:
            raise RuntimeError(f"failed deleting reference '{ref}' in repo '{owner}/{repo}'" f"\n{status}: {body}")
