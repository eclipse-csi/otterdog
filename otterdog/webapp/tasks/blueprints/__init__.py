#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from quart import render_template

from otterdog.webapp.db.models import BlueprintStatus, TaskModel
from otterdog.webapp.db.service import find_blueprint_status, update_or_create_blueprint_status
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import get_base_url

if TYPE_CHECKING:
    from otterdog.webapp.blueprints import Blueprint


@dataclass
class CheckResult:
    remediation_needed: bool
    remediation_pr: int | None = None
    check_failed: bool = False


class BlueprintTask(InstallationBasedTask, Task[CheckResult], ABC):
    org_id: str
    repo_name: str
    blueprint: Blueprint

    @cached_property
    def branch_name(self) -> str:
        return f"otterdog/blueprint/{self.blueprint.id}"

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _pre_execute(self) -> bool:
        blueprint_status = await find_blueprint_status(self.org_id, self.repo_name, self.blueprint.id)
        if blueprint_status is None:
            return True

        match blueprint_status.status:
            case BlueprintStatus.DISMISSED:
                self.logger.debug(
                    f"Blueprint '{self.blueprint.id}' dismissed for repo '{self.org_id}/{self.repo_name}', skipping"
                )
                return False

            case _:
                return True

    async def _post_execute(self, result_or_exception: CheckResult | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            await update_or_create_blueprint_status(
                self.org_id,
                self.repo_name,
                self.blueprint.id,
                BlueprintStatus.FAILURE,
            )
        else:
            if result_or_exception.check_failed is True:
                status = BlueprintStatus.FAILURE
            elif result_or_exception.remediation_needed is False:
                status = BlueprintStatus.SUCCESS
            else:
                status = BlueprintStatus.REMEDIATION_PREPARED

            await update_or_create_blueprint_status(
                self.org_id,
                self.repo_name,
                self.blueprint.id,
                status,
                result_or_exception.remediation_pr,
            )

    async def _create_branch_if_needed(self, default_branch: str) -> bool:
        """
        Create a new branch for the associated blueprint if it does not exist yet.

        :param default_branch: the name of the default branch
        :return: True if a branch was created, False otherwise
        """
        rest_api = await self.rest_api

        try:
            await rest_api.reference.get_branch_reference(self.org_id, self.repo_name, self.branch_name)
            branch_exists = True
        except RuntimeError:
            branch_exists = False

        if branch_exists is False:
            # branch does not yet exist, create it
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

            return True
        else:
            return False

    async def _find_existing_pull_request(self, default_branch: str) -> int | None:
        rest_api = await self.rest_api
        open_pull_requests = await rest_api.pull_request.get_pull_requests(
            self.org_id, self.repo_name, "open", default_branch
        )

        for pr in open_pull_requests:
            if pr["head"]["ref"] == self.branch_name:
                self.logger.debug(f"PR#{pr['number']} already exists for branch '{self.branch_name}', skipping")
                return pr["number"]

        return None

    async def _create_pull_request(
        self,
        pr_title: str,
        default_branch: str,
        team_reviewers: list[str] | None = None,
    ) -> int:
        self.logger.debug(
            f"creating pull request for blueprint '{self.blueprint.id}' in repo '{self.org_id}/{self.repo_name}'"
        )

        if self.blueprint.description is not None:
            description_lines = self.blueprint.description.rstrip().split("\n")
            description = " ".join(description_lines)
        else:
            description = None

        dashboard_url = get_base_url() + f"/organizations/{self.org_id}#blueprint-{self.blueprint.id}"

        pr_body = await render_template(
            "comment/blueprint_pr_body.txt",
            blueprint=self.blueprint,
            description=description,
            dashboard_url=dashboard_url,
        )

        rest_api = await self.rest_api
        created_pr = await rest_api.pull_request.create_pull_request(
            self.org_id,
            self.repo_name,
            pr_title,
            self.branch_name,
            default_branch,
            pr_body,
        )

        pull_request_number = created_pr["number"]

        if team_reviewers is not None and len(team_reviewers) > 0:
            await rest_api.pull_request.request_reviews(
                self.org_id, self.repo_name, pull_request_number, team_reviewers=team_reviewers
            )

        return pull_request_number
