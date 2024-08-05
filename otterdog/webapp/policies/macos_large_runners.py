#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses
from typing import Any

from . import Policy, PolicyType


@dataclasses.dataclass
class MacOSLargeRunnersUsagePolicy(Policy):

    allowed: bool

    @property
    def type(self) -> PolicyType:
        return PolicyType.MACOS_LARGE_RUNNERS_USAGE

    @property
    def config(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def is_workflow_job_permitted(self, labels: list[str]) -> bool:
        if self.allowed is True:
            return True
        else:

            def larger_runner(label: str) -> bool:
                return label.startswith("macos") and label.endswith("large")

            return not any(map(larger_runner, labels))
