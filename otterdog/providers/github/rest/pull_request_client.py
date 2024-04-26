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


class PullRequestClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_pull_request(self, org_id: str, repo_name: str, pull_request_number: str) -> dict[str, Any]:
        print_debug(f"getting pull request with number '{pull_request_number}' from repo '{org_id}/{repo_name}'")

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving pull request:\n{ex}").with_traceback(tb)

    async def create_pull_request(
        self, org_id: str, repo_name: str, title: str, head: str, base: str, body: str | None = None
    ) -> dict[str, Any]:
        print_debug(f"creating pull request for repo '{org_id}/{repo_name}'")

        try:
            data = {
                "title": title,
                "head": head,
                "base": base,
            }

            if body is not None:
                data["body"] = body

            return await self.requester.request_json("POST", f"/repos/{org_id}/{repo_name}/pulls", data=data)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed creating pull request:\n{ex}").with_traceback(tb)

    async def get_pull_requests(
        self, org_id: str, repo_name: str, state: str = "all", base_ref: str | None = None
    ) -> list[dict[str, Any]]:
        print_debug(f"getting pull requests from repo '{org_id}/{repo_name}'")

        try:
            params = {"state": state}

            if base_ref is not None:
                params.update({"base": base_ref})

            return await self.requester.request_paged_json("GET", f"/repos/{org_id}/{repo_name}/pulls", params=params)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving pull requests:\n{ex}").with_traceback(tb)

    async def get_commits(self, org_id: str, repo_name: str, pull_request_number: str) -> list[dict[str, Any]]:
        print_debug(f"getting commits for pull request #{pull_request_number} from repo '{org_id}/{repo_name}'")

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}/commits"
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving pull request commits:\n{ex}").with_traceback(tb)

    async def get_reviews(self, org_id: str, repo_name: str, pull_request_number: str) -> list[dict[str, Any]]:
        print_debug(f"getting reviews for pull request #{pull_request_number} from repo '{org_id}/{repo_name}'")

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}/reviews"
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving pull request reviews:\n{ex}").with_traceback(tb)

    async def get_files(self, org_id: str, repo_name: str, pull_request_number: str) -> list[dict[str, Any]]:
        print_debug(f"getting files for pull request #{pull_request_number} from repo '{org_id}/{repo_name}'")

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}/files"
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving pull request files:\n{ex}").with_traceback(tb)

    async def merge(
        self,
        org_id: str,
        repo_name: str,
        pull_request_number: str,
        commit_message: str | None = None,
        merge_method: str = "squash",
    ) -> bool:
        print_debug(f"merging pull request #{pull_request_number} from repo '{org_id}/{repo_name}'")

        try:
            data = {
                "merge_method": merge_method,
            }

            if commit_message is not None:
                data.update({"commit_message": commit_message})

            response = await self.requester.request_json(
                "PUT",
                f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}/merge",
                data=data,
            )
            return response["merged"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed merging pull request:\n{ex}").with_traceback(tb)
