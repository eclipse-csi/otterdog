#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException

from . import RestApi, RestClient

_logger = get_logger(__name__)


class CommitClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_commit(self, org_id: str, repo_name: str, ref: str) -> dict[str, Any]:
        _logger.debug("getting commit for ref '%s' from repo '%s/%s'", ref, org_id, repo_name)

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/commits/{ref}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving commit:\n{ex}") from ex

    async def get_commit_statuses(self, org_id: str, repo_name: str, ref: str) -> list[dict[str, Any]]:
        _logger.debug("getting commit statuses for ref '%s' from repo '%s/%s'", ref, org_id, repo_name)

        try:
            return await self.requester.request_paged_json("GET", f"/repos/{org_id}/{repo_name}/commits/{ref}/statuses")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving commit statuses:\n{ex}") from ex

    async def create_commit_status(
        self,
        org_id: str,
        repo_name: str,
        sha: str,
        state: str,
        context: str,
        description: str | None = None,
        target_url: str | None = None,
    ) -> None:
        _logger.debug("creating a commit status for sha '%s' in repo '%s/%s'", sha, org_id, repo_name)

        data = {"state": state, "target_url": target_url, "description": description, "context": context}
        status, body = await self.requester.request_raw(
            "POST", f"/repos/{org_id}/{repo_name}/statuses/{sha}", data=json.dumps(data)
        )

        if status != 201:
            raise RuntimeError(f"failed creating commit status for '{org_id}/{repo_name}/{sha}'\n{status}: {body}")

        _logger.debug("created commit status for sha '%s' in repo '%s/%s'", sha, org_id, repo_name)
