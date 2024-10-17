#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from . import Policy, PolicyType


class MacOSLargeRunnersUsagePolicy(Policy):
    allowed: bool

    @classmethod
    def policy_type(cls) -> PolicyType:
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
