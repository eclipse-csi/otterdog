#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
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


class ActionClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_workflows(self, org_id: str, repo: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving workflows for repo '%s/%s'", org_id, repo)

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo}/actions/workflows", entries_key="workflows"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving workflows for '{org_id}/{repo}':\n{ex}") from ex

    async def get_workflow_runs(
        self,
        org_id: str,
        repo: str,
        branch: str | None = None,
        per_page: int = 100,
        workflow_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Returns the most recent workflow runs of a repository (first page only, newest first),
        optionally restricted to a branch and / or a single workflow.
        """
        _logger.debug(
            "retrieving workflow runs for repo '%s/%s' (branch=%s, workflow=%s)", org_id, repo, branch, workflow_id
        )

        params: dict[str, Any] = {"per_page": per_page}
        if branch is not None:
            params["branch"] = branch

        if workflow_id is not None:
            url = f"/repos/{org_id}/{repo}/actions/workflows/{workflow_id}/runs"
        else:
            url = f"/repos/{org_id}/{repo}/actions/runs"

        try:
            response = await self.requester.request_json("GET", url, params=params)
            return response.get("workflow_runs", [])
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving workflow runs for '{org_id}/{repo}':\n{ex}") from ex

    async def get_workflow_run_jobs(self, org_id: str, repo: str, run_id: int) -> list[dict[str, Any]]:
        _logger.debug("retrieving jobs of workflow run #%d in repo '%s/%s'", run_id, org_id, repo)

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo}/actions/runs/{run_id}/jobs", entries_key="jobs"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving jobs of workflow run #{run_id} in '{org_id}/{repo}':\n{ex}") from ex

    async def cancel_workflow_run(self, org_id: str, repo_name: str, run_id: str) -> bool:
        _logger.debug("cancelling workflow run #%s in repo '%s/%s'", run_id, org_id, repo_name)

        status, body = await self.requester.request_raw(
            "POST", f"/repos/{org_id}/{repo_name}/actions/runs/{run_id}/cancel"
        )

        if status == 202:
            return True
        elif status == 409:
            return False
        else:
            raise RuntimeError(
                f"failed cancelling workflow run #{run_id} in repo '{org_id}/{repo_name}'\n{status}: {body}"
            )

    async def get_artifacts(self, org_id: str, repo: str, run_id: int) -> list[dict[str, Any]]:
        _logger.debug("list artifacts for workflow run #%d in repo '%s/%s'", run_id, org_id, repo)

        try:
            return await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo}/actions/runs/{run_id}/artifacts", entries_key="artifacts"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving artifacts for '{org_id}/{repo}':\n{ex}") from ex

    async def download_artifact(self, file, org_id: str, repo_name: str, artifact_id: int) -> None:
        _logger.debug("downloading workflow artifact in repo '%s/%s'", org_id, repo_name)

        try:
            async for data in self.requester.request_stream(
                "GET", f"/repos/{org_id}/{repo_name}/actions/artifacts/{artifact_id}/zip"
            ):
                await file.write(data)

        except GitHubException as ex:
            raise RuntimeError(f"failed downloading workflow artifact from repo '{org_id}/{repo_name}':\n{ex}") from ex
