#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class WorkflowFile:
    raw_content: str
    content: dict[str, Any] = field(init=False)
    lines: list[str] = field(init=False)

    def __post_init__(self):
        self.content = yaml.safe_load(self.raw_content)
        self.lines = self.raw_content.splitlines(keepends=True)

    def get_used_actions(self) -> list[str]:
        workflows = []

        # regular workflows
        for _k, v in self.content.get("jobs", {}).items():
            # jobs.<job_id>.steps[*].uses
            for step in v.get("steps", []):
                if "uses" in step:
                    workflows.append(step["uses"])

            # jobs.<job_id>.uses
            if "uses" in v:
                workflows.append(v["uses"])

        # composite actions
        if "runs" in self.content:
            # runs.steps[*].uses
            for step in self.content.get("runs", {}).get("steps", []):
                if "uses" in step:
                    workflows.append(step["uses"])

        return workflows
