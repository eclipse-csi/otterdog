#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from otterdog.providers.github.rest import RestApi
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.tasks.pin_workflow.actions import ActionRef
from otterdog.webapp.tasks.pin_workflow.workflow_file import WorkflowFile


@dataclass(repr=False)
class PinWorkflowTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    pr_title: str
    pr_body: str
    branch_prefix: str = field(default="pin_workflow")

    @property
    def branch_name(self) -> str:
        return f"otterdog/{self.branch_prefix}"

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _execute(self) -> None:
        self.logger.info(
            "pinning workflows in repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        rest_api = await self.rest_api

        default_branch = await rest_api.repo.get_default_branch(self.org_id, self.repo_name)

        pr = await self._get_pull_request_if_already_exists(rest_api, default_branch)
        if pr is not None:
            self.logger.debug(f"PR#{pr['number']} already exists, skipping")
            return

        pinned_workflows = {}
        workflows = await rest_api.action.get_workflows(self.org_id, self.repo_name)
        for workflow in workflows:
            workflow_path: str = workflow["path"]
            if not workflow_path.startswith(".github"):
                continue

            try:
                workflow_content = await rest_api.content.get_content(self.org_id, self.repo_name, workflow_path)
                workflow = WorkflowFile(workflow_content)
                pinned, pinned_lines = await self._pin_workflow(rest_api, workflow)
                if pinned:
                    self.logger.debug(f"pinning workflow '{workflow_path}'")
                    pinned_workflows[workflow_path] = (workflow, pinned_lines)
            except RuntimeError:
                continue

        if len(pinned_workflows) > 0:
            await self._create_pull_request(rest_api, default_branch, pinned_workflows)

    async def _get_pull_request_if_already_exists(
        self,
        rest_api: RestApi,
        default_branch: str,
    ) -> dict[str, Any] | None:
        open_pull_requests = await rest_api.pull_request.get_pull_requests(
            self.org_id, self.repo_name, "open", default_branch
        )

        branch_name = self.branch_name
        for pr in open_pull_requests:
            if pr["head"]["ref"] == branch_name:
                return pr

        return None

    @staticmethod
    async def _pin_workflow(rest_api: RestApi, workflow: WorkflowFile) -> tuple[bool, list[str]]:
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
            return m.group(2) + pinned_actions[m.group(3)]

        pinned_lines = []
        pinned_any_action = False
        for line in workflow.lines:
            pinned_line = re.sub(r"((uses:\s+)([^\s#]+)((\s+#)([^\n]+))?)(?=\n?)", pin, line)

            if pinned_line != line:
                pinned_any_action = True

            pinned_lines.append(pinned_line)

        return pinned_any_action, pinned_lines

    async def _create_pull_request(
        self,
        rest_api: RestApi,
        default_branch: str,
        pinned_workflows: dict[str, tuple[dict, list[str]]],
    ) -> None:
        default_branch_data = await rest_api.reference.get_branch_reference(
            self.org_id,
            self.repo_name,
            default_branch,
        )
        default_branch_sha = default_branch_data["object"]["sha"]

        await rest_api.reference.create_reference(
            self.org_id,
            self.repo_name,
            self.branch_name,
            default_branch_sha,
        )

        # FIXME: once the otterdog-app is added to the ECA allow list, this can be removed again
        short_name = self.org_id if "-" not in self.org_id else self.org_id.partition("-")[2]

        for workflow_path, (_, pinned_lines) in pinned_workflows.items():
            content = "".join(pinned_lines)
            await rest_api.content.update_content(
                self.org_id,
                self.repo_name,
                workflow_path,
                content,
                self.branch_name,
                f"Pinning workflow {workflow_path}",
                f"{self.org_id}-bot",
                f"{short_name}-bot@eclipse.org",
                author_is_committer=True,
            )

        self.logger.debug("creating pull request")

        await rest_api.pull_request.create_pull_request(
            self.org_id,
            self.repo_name,
            self.pr_title,
            self.branch_name,
            default_branch,
            self.pr_body,
        )

    def __repr__(self) -> str:
        return f"PinWorkflowTask(repo='{self.org_id}/{self.repo_name}')"
