#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import render_chevron
from otterdog.webapp.tasks.blueprints import BlueprintTask, CheckResult
from otterdog.webapp.tasks.blueprints.pinning.actions import ActionRef, GitHubAction
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
                workflow = WorkflowFile(workflow_content)
                referenced_actions = set(workflow.get_used_actions())
                for action in referenced_actions:
                    action_ref = ActionRef.of_pattern(action)
                    if isinstance(action_ref, GitHubAction):
                        referenced_action = f"{action_ref.owner}/{action_ref.repo}"
                        if referenced_action == self.blueprint.scorecard_action:
                            return True
            except RuntimeError:
                continue

        return False

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
