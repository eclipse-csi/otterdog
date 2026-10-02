#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import render_chevron
from otterdog.webapp.tasks.blueprints import BlueprintTask, CheckResult
from otterdog.webapp.tasks.blueprints.pinning.actions import ActionRef, GitHubAction, ReusableWorkflow
from otterdog.webapp.tasks.blueprints.pinning.workflow_file import WorkflowFile

if TYPE_CHECKING:
    from otterdog.webapp.blueprints.scorecard_integration import ScorecardIntegrationBlueprint
    from otterdog.webapp.db.models import ConfigurationModel


@dataclass(repr=False)
class CheckScorecardIntegrationTask(BlueprintTask):
    installation_id: int
    org_id: str
    repo_name: str
    blueprint: ScorecardIntegrationBlueprint
    config_model: ConfigurationModel

    @cached_property
    def github_organization_configuration(self) -> GitHubOrganization:
        return GitHubOrganization.from_model_data(self.config_model.config)

    async def _execute(self) -> CheckResult:
        self.logger.info(
            "checking scorecard integration in repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        result = CheckResult(remediation_needed=False)

        try:
            if not await self._find_scorecard_integration():
                await self._add_scorecard_workflow(result)
        except RuntimeError:
            result.check_failed = True
            return result

        return result

    async def _find_scorecard_integration(self) -> bool:
        rest_api = await self.rest_api

        workflows = await rest_api.action.get_workflows(self.org_id, self.repo_name)

        for workflow in workflows:
            workflow_path: str = workflow["path"]
            if not workflow_path.startswith(".github"):
                continue

            try:
                workflow_content = await rest_api.content.get_content(self.org_id, self.repo_name, workflow_path)
                if await self._uses_scorecard_action(WorkflowFile(workflow_content), follow_reusable=True):
                    return True
            except RuntimeError:
                continue

        return False

    async def _uses_scorecard_action(self, workflow: WorkflowFile, follow_reusable: bool) -> bool:
        """
        Checks whether the workflow uses the scorecard action directly, or via a reusable workflow
        that either is listed in `scorecard_workflow_refs` or itself uses the scorecard action.
        """
        for action in set(workflow.get_used_actions()):
            action_ref = ActionRef.of_pattern(action)
            if self._is_scorecard_action(action_ref):
                return True
            if follow_reusable and await self._is_scorecard_reusable_workflow(action_ref):
                return True

        return False

    def _is_scorecard_action(self, action_ref: ActionRef) -> bool:
        return (
            isinstance(action_ref, GitHubAction)
            and f"{action_ref.owner}/{action_ref.repo}" == self.blueprint.scorecard_action
        )

    async def _is_scorecard_reusable_workflow(self, action_ref: ActionRef) -> bool:
        if not isinstance(action_ref, ReusableWorkflow):
            return False

        if self._is_allowed_scorecard_workflow(action_ref):
            return True

        if action_ref.owner is None or action_ref.repo is None:
            return False

        referenced_workflow = await action_ref.get_workflow_file(await self.rest_api)

        # only follow one level of reusable workflows
        return referenced_workflow is not None and await self._uses_scorecard_action(
            referenced_workflow, follow_reusable=False
        )

    def _is_allowed_scorecard_workflow(self, action_ref: ReusableWorkflow) -> bool:
        reference = repr(action_ref)
        return any(re.fullmatch(pattern, reference) is not None for pattern in self.blueprint.scorecard_workflow_refs)

    def _render_content(self, content: str) -> str:
        context = {
            "project_name": self.config_model.project_name,
            "github_id": self.config_model.github_id,
            "repo_name": self.repo_name,
            "org": self.github_organization_configuration.settings,
            "repo": self.github_organization_configuration.get_repository(self.repo_name),
            "repo_url": f"https://github.com/{self.org_id}/{self.repo_name}",
            "blueprint_id": self.blueprint.id,
            "blueprint_url": self.blueprint.path,
        }

        return render_chevron(content, context)

    async def _add_scorecard_workflow(
        self,
        result: CheckResult,
    ) -> None:
        result.remediation_needed = True

        rest_api = await self.rest_api
        default_branch = await rest_api.repo.get_default_branch(self.org_id, self.repo_name)

        await self._create_branch_if_needed(default_branch)

        workflow_path = f".github/workflows/{self.blueprint.workflow_name}"
        await rest_api.content.update_content(
            self.org_id,
            self.repo_name,
            workflow_path,
            self._render_content(self.blueprint.workflow_content),
            self.branch_name,
            f"Adding scorecard analysis workflow {workflow_path}",
        )

        existing_pr_number = await self._find_existing_pull_request(default_branch)
        if existing_pr_number is not None:
            result.remediation_pr = existing_pr_number
            return

        pr_title = f"chore(otterdog): adding scorecard analysis workflow due to blueprint `{self.blueprint.id}`"
        result.remediation_pr = await self._create_pull_request(pr_title, default_branch)

    def __repr__(self) -> str:
        return f"CheckScorecardIntegrationTask(repo='{self.org_id}/{self.repo_name}')"
