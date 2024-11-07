#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.webapp.db.service import increment_or_create_policy_status

from . import Policy, PolicyType


class MacOSLargeRunnersUsagePolicy(Policy):
    allowed: bool

    @property
    def type(self) -> PolicyType:
        return PolicyType.MACOS_LARGE_RUNNERS_USAGE

    async def evaluate(self, github_id: str) -> None:
        # nothing to evaluate for this policy
        return

    def is_workflow_job_permitted(self, labels: list[str]) -> bool:
        if self.allowed is True:
            return True
        else:

            def larger_runner(label: str) -> bool:
                return label.startswith("macos") and label.endswith("large")

            return not any(map(larger_runner, labels))

    async def update_status(self, owner: str, job_permitted: bool) -> None:
        cancelled_increment = 0 if job_permitted else 1
        status_diff = {"total_workflow_jobs": 1, "cancelled_workflow_jobs": cancelled_increment}
        await increment_or_create_policy_status(owner, self, status_diff)
