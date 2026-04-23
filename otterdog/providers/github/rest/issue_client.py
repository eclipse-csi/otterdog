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


class IssueClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def create_issue(self, org_id: str, repo_name: str, title: str, body: str) -> dict[str, Any]:
        _logger.debug("creating issue '%s' in repo '%s/%s'", title, org_id, repo_name)

        try:
            data = {"title": title, "body": body}
            return await self.requester.request_json("POST", f"/repos/{org_id}/{repo_name}/issues", data=data)
        except GitHubException as ex:
            raise RuntimeError(f"failed creating issue:\n{ex}") from ex

    async def list_issues(
        self, org_id: str, repo_name: str, state: str = "open", labels: str | None = None
    ) -> list[dict[str, Any]]:
        _logger.debug("listing issues in repo '%s/%s' with state '%s'", org_id, repo_name, state)

        try:
            params = {"state": state, "per_page": "100"}
            if labels:
                params["labels"] = labels

            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/issues", params=params)
        except GitHubException as ex:
            raise RuntimeError(f"failed listing issues:\n{ex}") from ex

    async def create_comment(self, org_id: str, repo_name: str, issue_number: str, body: str) -> None:
        _logger.debug("creating issue comment for issue '%s' in repo '%s/%s'", issue_number, org_id, repo_name)

        try:
            data = {"body": body}
            await self.requester.request_json(
                "POST", f"/repos/{org_id}/{repo_name}/issues/{issue_number}/comments", data=data
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed creating issue comment:\n{ex}") from ex
