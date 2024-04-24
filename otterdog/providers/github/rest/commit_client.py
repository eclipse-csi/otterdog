#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

from otterdog.providers.github.exception import GitHubException
from otterdog.utils import print_debug

from . import RestApi, RestClient


class CommitClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_commit_statuses(self, org_id: str, repo_name: str, ref: str) -> list[dict[str, Any]]:
        print_debug(f"getting commit statuses for ref '{ref}' from repo '{org_id}/{repo_name}'")

        try:
            return await self.requester.request_paged_json("GET", f"/repos/{org_id}/{repo_name}/commits/{ref}/statuses")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving commit statuses:\n{ex}").with_traceback(tb)

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
        print_debug(f"creating a commit status for sha '{sha}'")

        data = {"state": state, "target_url": target_url, "description": description, "context": context}
        status, body = await self.requester.request_raw(
            "POST", f"/repos/{org_id}/{repo_name}/statuses/{sha}", data=json.dumps(data)
        )

        if status != 201:
            raise RuntimeError(f"failed creating commit status for '{org_id}/{repo_name}/{sha}'\n{status}: {body}")

        print_debug(f"created commit status for sha '{org_id}/{repo_name}/{sha}'")
