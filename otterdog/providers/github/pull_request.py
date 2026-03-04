#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************
import json
from typing import Any

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.requester import Requester

_logger = get_logger(__name__)


class PullRequest:
    def __init__(self, rest_api_requester: Requester, org_id: str, repo_name: str, pr_number: int) -> None:
        self.requester = rest_api_requester
        self.org_id = org_id
        self.repo_name = repo_name
        self.pr_number = pr_number

    def __str__(self) -> str:
        return f"PullRequest(org_id={self.org_id}, repo_name={self.repo_name}, pr_number={self.pr_number})"

    def _base_path(self) -> str:
        return f"/repos/{self.org_id}/{self.repo_name}/pulls/{self.pr_number}"

    async def get_data(
        self,
    ) -> dict[str, Any]:
        _logger.debug("getting live data for %s", self)

        try:
            return await self.requester.request_json("GET", self._base_path())
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving {self}") from ex

    async def merge_pull_request(
        self,
        method: str,
    ) -> dict[str, Any]:
        _logger.debug("merging %s", self)

        try:
            data = {"merge_method": method}
            return await self.requester.request_json("PUT", self._base_path() + "/merge", data=data)
        except GitHubException as ex:
            raise RuntimeError(f"failed merging {self}") from ex

    async def get_commits(
        self,
    ) -> list[dict[str, Any]]:
        _logger.debug("getting commits for %s", self)

        try:
            return await self.requester.request_paged_json("GET", self._base_path() + "/commits")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving commits for {self}") from ex

    async def get_reviews(
        self,
    ) -> list[dict[str, Any]]:
        _logger.debug("getting reviews for %s", self)

        try:
            return await self.requester.request_paged_json("GET", self._base_path() + "/reviews")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving reviews for {self}") from ex

    async def request_reviews(
        self,
        reviewers: list[str] | None = None,
        team_reviewers: list[str] | None = None,
    ) -> bool:
        _logger.debug(
            "requesting reviews for %s: %s, %s",
            self,
            reviewers,
            team_reviewers,
        )

        if (reviewers is None or len(reviewers) == 0) and (team_reviewers is None or len(team_reviewers) == 0):
            _logger.error("requesting reviews for %s without any reviewer specified", self)
            return False

        try:
            data = {}

            if reviewers is not None:
                data["reviewers"] = reviewers

            if team_reviewers is not None:
                data["team_reviewers"] = team_reviewers

            status, body = await self.requester.request_raw(
                "POST",
                self._base_path() + "/requested_reviewers",
                data=json.dumps(data),
            )

            if status == 201:
                return True
            elif status == 422:
                _logger.warning("failed to request reviews for %s: %s", self, body)
                return False
            else:
                raise RuntimeError(f"failed requesting reviews for {self}\n{status}: {body}")

        except GitHubException as ex:
            raise RuntimeError(f"failed requesting reviews for {self}") from ex

    async def get_files(
        self,
    ) -> list[dict[str, Any]]:
        _logger.debug("getting files for %s", self)

        try:
            return await self.requester.request_paged_json("GET", self._base_path() + "/files")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving files for {self}") from ex

    async def merge(
        self,
        commit_message: str | None = None,
        merge_method: str = "squash",
    ) -> bool:
        """
        @param commit_message is only used for "squash" and "merge" merge methods, and ignored for "rebase" method
        @param merge_method can be one of "merge", "squash", or "rebase"
        """
        # https://docs.github.com/en/enterprise-cloud@latest/rest/pulls/pulls?apiVersion=2022-11-28#merge-a-pull-request

        _logger.debug("merging %s", self)

        try:
            data = {
                "merge_method": merge_method,
            }

            if commit_message is not None:
                data.update({"commit_message": commit_message})

            response = await self.requester.request_json(
                "PUT",
                self._base_path() + "/merge",
                data=data,
            )
            return response["merged"]
        except GitHubException as ex:
            raise RuntimeError(f"failed merging {self}") from ex
