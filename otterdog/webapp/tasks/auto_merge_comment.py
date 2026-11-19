#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING

from quart import render_template

from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import find_pull_request
from otterdog.webapp.lease import RedisLease
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import (
    describe_admin_teams,
    describe_approval_teams,
    get_teams_matching_approval_pattern,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from otterdog.webapp.db.models import PullRequestModel

# the header of the separate comment added by previous versions, hidden by the next validation
LEGACY_AUTO_MERGE_COMMENT_HEADER = "<!-- Otterdog Comment: automerge -->"

# the section of the validation comment showing whether the pull request can be auto-merged, see validation_comment.txt
_STATUS_START = "<!-- otterdog:auto-merge-status -->"
_STATUS_END = "<!-- /otterdog:auto-merge-status -->"
_STATUS_SECTION = re.compile(f"{re.escape(_STATUS_START)}.*?{re.escape(_STATUS_END)}", re.DOTALL)

_LEASE_TTL_IN_SECONDS = 60
_LEASE_MAX_WAIT_IN_SECONDS = 60
_LEASE_RETRY_DELAY_IN_SECONDS = 0.5

_logger = getLogger(__name__)


def with_auto_merge_status(comment_body: str, status: str) -> str | None:
    """Returns the body of a validation comment showing the given status, None if it has no section for it."""
    status = status.strip()
    section = f"{_STATUS_START}\n{status}\n\n{_STATUS_END}" if status else f"{_STATUS_START}{_STATUS_END}"
    updated_body, count = _STATUS_SECTION.subn(lambda _: section, comment_body, count=1)
    return updated_body if count == 1 else None


@asynccontextmanager
async def auto_merge_comment_lease(org_id: str, repo_name: str, pull_request_number: int) -> AsyncIterator[None]:
    """
    Updates the auto-merge status of a pull request in one worker process at a time: the tasks scheduled at about the
    same time, e.g. by the validation and an approval, would otherwise overwrite each other with outdated states.

    The status is updated anyway if the lease cannot be acquired, e.g. if redis is not available.
    """
    lease = RedisLease(f"otterdog:auto-merge-comment:{org_id}/{repo_name}#{pull_request_number}", _LEASE_TTL_IN_SECONDS)

    acquired = False
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _LEASE_MAX_WAIT_IN_SECONDS
        while not (acquired := await lease.acquire()) and loop.time() < deadline:
            await asyncio.sleep(_LEASE_RETRY_DELAY_IN_SECONDS)
    except Exception as ex:
        _logger.warning("failed acquiring the lease '%s': %r", lease.key, ex)

    if not acquired:
        _logger.warning("updating the auto-merge status without holding the lease '%s'", lease.key)
        yield
        return

    async with lease.held():
        yield


@dataclass(repr=False)
class AutoMergeCommentTask(InstallationBasedTask, Task[None]):
    """
    Shows in the comment of the last validation whether the pull request can be auto-merged, updated in place
    whenever the conditions may have changed.
    """

    installation_id: int
    org_id: str
    repo_name: str
    pull_request_number: int

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _execute(self) -> None:
        self.logger.info(
            "updating the auto merge status of pull request #%d of repo '%s/%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )

        async with auto_merge_comment_lease(self.org_id, self.repo_name, self.pull_request_number):
            pr_model = await find_pull_request(self.org_id, self.repo_name, self.pull_request_number)
            if pr_model is None or pr_model.validation_comment_id is None:
                # not validated yet, or by a previous version
                return

            graphql_api = await self.graphql_api
            comment = await graphql_api.get_issue_comment(pr_model.validation_comment_id)
            if comment is None or comment["isMinimized"]:
                # replaced by the comment of a newer validation, which updates the status once recorded
                return

            status = await self._render_status() if await self._is_eligible(pr_model) else ""
            body = with_auto_merge_status(comment["body"], status)
            if body is not None and body != comment["body"]:
                await graphql_api.update_issue_comment(pr_model.validation_comment_id, body)

    async def _is_eligible(self, pr_model: PullRequestModel) -> bool:
        # the task is scheduled with the state its caller started with, e.g. a newer commit may have been pushed since
        rest_api = await self.rest_api
        pull_request = await rest_api.pull_request.get_pull_request(
            self.org_id, self.repo_name, str(self.pull_request_number)
        )
        return await pr_model.can_be_automerged(pull_request["head"]["sha"])

    async def _render_status(self) -> str:
        rest_api = await self.rest_api
        matching_teams = await get_teams_matching_approval_pattern(rest_api, self.org_id)
        return await render_template(
            "comment/auto_merge_status.txt",
            team_description=await describe_approval_teams(matching_teams, self.org_id),
            admin_team_description=await describe_admin_teams(self.org_id),
        )

    def __repr__(self) -> str:
        return f"AutoMergeCommentTask(repo='{self.org_id}/{self.repo_name}', pull_request=#{self.pull_request_number})"
