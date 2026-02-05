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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from otterdog.webapp.tasks.blueprints import BlueprintTask, CheckResult
from otterdog.webapp.tasks.blueprints.pinning.actions import ActionRef
from otterdog.webapp.tasks.blueprints.pinning.workflow_file import WorkflowFile

if TYPE_CHECKING:
    from otterdog.webapp.blueprints.pin_workflow import PinWorkflowBlueprint


@dataclass(repr=False)
class PinWorkflowTask(BlueprintTask):
    installation_id: int
    org_id: str
    repo_name: str
    blueprint: PinWorkflowBlueprint

    async def _execute(self) -> CheckResult:
        self.logger.info(
            "pinning workflows in repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        result = CheckResult(remediation_needed=False)
        rest_api = await self.rest_api

        pinned_workflows = {}
        try:
            workflows = await rest_api.action.get_workflows(self.org_id, self.repo_name)
        except RuntimeError:
            result.check_failed = True
            return result

        for workflow in workflows:
            workflow_path: str = workflow["path"]
            if not workflow_path.startswith(".github"):
                continue

            try:
                self.logger.info(f"pinning workflow '{workflow_path}' in repo '{self.org_id}/{self.repo_name}'")
                workflow_content = await rest_api.content.get_content(self.org_id, self.repo_name, workflow_path)
                workflow = WorkflowFile(workflow_content)
                pinned, pinned_lines = await self._pin_workflow(workflow)
                if pinned:
                    pinned_workflows[workflow_path] = (workflow, pinned_lines)
            except RuntimeError:
                continue

        if len(pinned_workflows) > 0:
            await self._process_workflows(pinned_workflows, result)

        return result

    async def _process_workflows(
        self,
        pinned_workflows: dict[str, tuple[WorkflowFile, list[str]]],
        result: CheckResult,
    ) -> None:
        result.remediation_needed = True

        rest_api = await self.rest_api
        default_branch = await rest_api.repo.get_default_branch(self.org_id, self.repo_name)

        await self._create_branch_if_needed(default_branch)

        for workflow_path, (_, pinned_lines) in pinned_workflows.items():
            content = "".join(pinned_lines)
            await rest_api.content.update_content(
                self.org_id,
                self.repo_name,
                workflow_path,
                content,
                self.branch_name,
                f"Pinning workflow {workflow_path}",
            )

        existing_pr_number = await self._find_existing_pull_request(default_branch)
        if existing_pr_number is not None:
            result.remediation_pr = existing_pr_number
            return

        pr_title = f"chore(otterdog): pinning workflows due to blueprint `{self.blueprint.id}`"
        result.remediation_pr = await self._create_pull_request(pr_title, default_branch)

    async def _pin_workflow(self, workflow: WorkflowFile) -> tuple[bool, list[str]]:
        rest_api = await self.rest_api
        referenced_actions = set(workflow.get_used_actions())
        pinned_actions = {}

        tasks = []
        for action in referenced_actions:
            action_ref = ActionRef.of_pattern(action)
            if action_ref.can_be_pinned():
                tasks.append(action_ref.pin(rest_api))
            else:
                pinned_actions[action] = action

        result = await asyncio.gather(*tasks)

        for orig_action, pinned_action, pinned_comment in result:
            if pinned_comment:
                pinned_actions[orig_action] = f"{pinned_action!r} # {pinned_comment}"
            else:
                pinned_actions[orig_action] = f"{pinned_action!r}"

        def pin(m):
            prefix = m.group(2)
            unpinned_action = m.group(3)
            comment = m.group(6)

            if comment is not None and "ignore" in comment:
                return m.group(0)

            pinned_action_with_comment = pinned_actions.get(unpinned_action)
            if pinned_action_with_comment is not None:
                return prefix + pinned_action_with_comment
            else:
                return m.group(0)

        pinned_lines = []
        pinned_any_action = False
        for line in workflow.lines:
            pinned_line = re.sub(r"((uses:\s+)([^\s#]+)((\s+#)([^\n]+))?)(?=\n?)", pin, line)

            if pinned_line != line:
                pinned_any_action = True

            pinned_lines.append(pinned_line)

        return pinned_any_action, pinned_lines

    def __repr__(self) -> str:
        return f"PinWorkflowTask(repo='{self.org_id}/{self.repo_name}')"
