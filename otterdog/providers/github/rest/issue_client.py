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

    async def create_comment(self, org_id: str, repo_name: str, issue_number: str, body: str) -> None:
        _logger.debug("creating issue comment for issue '%s' in repo '%s/%s'", issue_number, org_id, repo_name)

        try:
            data = {"body": body}
            await self.requester.request_json(
                "POST", f"/repos/{org_id}/{repo_name}/issues/{issue_number}/comments", data=data
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed creating issue comment:\n{ex}") from ex

    async def get_comments(self, org_id: str, repo_name: str, issue_number: int) -> list[dict[str, Any]]:
        _logger.debug("retrieving comments for issue '%s' in repo '%s/%s'", issue_number, org_id, repo_name)

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/issues/{issue_number}/comments"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving issue comments:\n{ex}") from ex

    async def update_comment(self, org_id: str, repo_name: str, comment_id: int, body: str) -> None:
        _logger.debug("updating issue comment '%s' in repo '%s/%s'", comment_id, org_id, repo_name)

        try:
            data = {"body": body}
            await self.requester.request_json(
                "PATCH", f"/repos/{org_id}/{repo_name}/issues/comments/{comment_id}", data=data
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed updating issue comment:\n{ex}") from ex
