#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException

from . import RestApi, RestClient

_logger = get_logger(__name__)


class ReferenceClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_branch_reference(self, org_id: str, repo_name: str, branch_name: str) -> dict[str, Any]:
        _logger.debug("getting branch reference with name '%s' from repo '%s/%s'", branch_name, org_id, repo_name)

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/git/ref/heads/{branch_name}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving reference:\n{ex}") from ex

    async def get_matching_references(self, org_id: str, repo_name: str, ref_pattern: str) -> list[dict[str, Any]]:
        _logger.debug("getting matching references with pattern '%s' from repo '%s/%s'", ref_pattern, org_id, repo_name)

        try:
            return await self.requester.request_json(
                "GET",
                f"/repos/{org_id}/{repo_name}/git/matching-refs/{ref_pattern}",
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving matching references for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def create_reference(self, org_id: str, repo_name: str, ref: str, sha: str) -> str:
        _logger.debug("creating reference with name '%s' and sha '%s' for repo '%s/%s'", ref, sha, org_id, repo_name)

        try:
            data = {
                "ref": f"refs/heads/{ref}",
                "sha": sha,
            }

            await self.requester.request_json("POST", f"/repos/{org_id}/{repo_name}/git/refs", data=data)
            return data["ref"]
        except GitHubException as ex:
            raise RuntimeError(f"failed creating reference:\n{ex}") from ex

    async def delete_reference(self, org_id: str, repo_name: str, ref: str) -> bool:
        _logger.debug("deleting reference with name '%s' in repo '%s/%s'", ref, org_id, repo_name)

        full_ref = f"refs/heads/{ref}"
        status, body = await self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/git/{full_ref}")
        if status == 204:
            return True
        elif status in (409, 422):
            return False
        else:
            raise RuntimeError(
                f"failed deleting reference '{ref}' in repo '{org_id}/{repo_name}'" f"\n{status}: {body}"
            )
