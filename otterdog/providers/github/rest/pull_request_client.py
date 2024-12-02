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


class PullRequestClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_pull_request(
        self,
        org_id: str,
        repo_name: str,
        pull_request_number: str,
    ) -> dict[str, Any]:
        _logger.debug("getting pull request with number '%s' from repo '%s/%s'", pull_request_number, org_id, repo_name)

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving pull request:\n{ex}") from ex

    async def create_pull_request(
        self,
        org_id: str,
        repo_name: str,
        title: str,
        head: str,
        base: str,
        body: str | None = None,
    ) -> dict[str, Any]:
        _logger.debug("creating pull request for repo '%s/%s'", org_id, repo_name)

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
            raise RuntimeError(f"failed creating pull request:\n{ex}") from ex

    async def get_pull_requests(
        self,
        org_id: str,
        repo_name: str,
        state: str = "all",
        base_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        _logger.debug("getting pull requests from repo '%s/%s'", org_id, repo_name)

        try:
            params = {"state": state}

            if base_ref is not None:
                params.update({"base": base_ref})

            return await self.requester.request_paged_json("GET", f"/repos/{org_id}/{repo_name}/pulls", params=params)
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving pull requests:\n{ex}") from ex

    async def get_commits(
        self,
        org_id: str,
        repo_name: str,
        pull_request_number: str,
    ) -> list[dict[str, Any]]:
        _logger.debug("getting commits for pull request #%s from repo '%s/%s'", pull_request_number, org_id, repo_name)

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}/commits"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving pull request commits:\n{ex}") from ex

    async def get_reviews(
        self,
        org_id: str,
        repo_name: str,
        pull_request_number: str,
    ) -> list[dict[str, Any]]:
        _logger.debug("getting reviews for pull request #%s from repo '%s/%s'", pull_request_number, org_id, repo_name)

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}/reviews"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving pull request reviews:\n{ex}") from ex

    async def get_files(
        self,
        org_id: str,
        repo_name: str,
        pull_request_number: str,
    ) -> list[dict[str, Any]]:
        _logger.debug("getting files for pull request #%s from repo '%s/%s'", pull_request_number, org_id, repo_name)

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_request_number}/files"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving pull request files:\n{ex}") from ex

    async def merge(
        self,
        org_id: str,
        repo_name: str,
        pull_request_number: str,
        commit_message: str | None = None,
        merge_method: str = "squash",
    ) -> bool:
        _logger.debug("merging pull request #%s from repo '%s/%s'", pull_request_number, org_id, repo_name)

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
            raise RuntimeError(f"failed merging pull request:\n{ex}") from ex
