#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from logging import getLogger
from typing import Any, Self

from otterdog.webapp.db.service import increment_or_create_policy_status
from otterdog.webapp.webhook.github_models import WorkflowJob

from . import Policy, PolicyType

logger = getLogger(__name__)


class MacOSLargeRunnersUsagePolicy(Policy):
    """
    A policy to check whether workflow jobs are permitted to run on restricted macOS large runners.
    """

    allowed: bool

    @property
    def type(self) -> PolicyType:
        return PolicyType.MACOS_LARGE_RUNNERS_USAGE

    @property
    def requires_regular_check(self) -> bool:
        return False

    def merge(self, other: Self) -> Self:
        copy = super().merge(other)
        copy.allowed = other.allowed
        return copy

    async def evaluate(
        self, installation_id: int, github_id: str, repo_name: str | None = None, payload: Any | None = None
    ) -> None:
        assert repo_name is not None
        assert isinstance(payload, WorkflowJob)

        uses_restricted_runner, permitted = self._is_workflow_job_permitted(payload.labels)
        if not permitted:
            from otterdog.webapp.utils import get_rest_api_for_installation

            run_id = payload.run_id

            rest_api = await get_rest_api_for_installation(installation_id)
            cancelled = await rest_api.action.cancel_workflow_run(github_id, repo_name, run_id)
            logger.info(f"cancelled workflow run #{run_id} in repo '{github_id}/{repo_name}': success={cancelled}")

        await self._update_status(github_id, uses_restricted_runner, permitted)

    def _is_workflow_job_permitted(self, labels: list[str]) -> tuple[bool, bool]:
        """
        Returns whether a given workflow job is permitted to run.

        :param labels: a list of labels attached to the workflow job.
        :returns: returns a tuple (uses_restricted_runner, permitted_to_run).
        """

        def larger_runner(label: str) -> bool:
            return label.startswith("macos") and label.endswith("large")

        uses_restricted_runner = any(map(larger_runner, labels))
        return uses_restricted_runner, self.allowed or not uses_restricted_runner

    async def _update_status(self, owner: str, uses_restricted_runner: bool, job_permitted: bool) -> None:
        permitted_increment = 1 if uses_restricted_runner and job_permitted else 0
        cancelled_increment = 0 if job_permitted else 1

        status_diff = {
            "total_workflow_jobs": 1,
            "permitted_on_restricted_runners": permitted_increment,
            "cancelled_on_restricted_runners": cancelled_increment,
        }

        await increment_or_create_policy_status(owner, self, status_diff)
