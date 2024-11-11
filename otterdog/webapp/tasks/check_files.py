#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass
from textwrap import dedent

from otterdog.providers.github.rest import RestApi
from otterdog.webapp.blueprints.required_file import RequiredFile, RequiredFileBlueprint
from otterdog.webapp.db.models import BlueprintStatus, TaskModel
from otterdog.webapp.db.service import find_blueprint_status, update_or_create_blueprint_status
from otterdog.webapp.tasks import InstallationBasedTask, Task


@dataclass
class CheckResult:
    remediation_needed: bool
    remediation_pr: int | None = None


@dataclass(repr=False)
class CheckFilesTask(InstallationBasedTask, Task[CheckResult]):
    installation_id: int
    org_id: str
    repo_name: str
    blueprint: RequiredFileBlueprint

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

        match blueprint_status:
            case BlueprintStatus.DISMISSED:
                self.logger.info(
                    f"Blueprint '{self.blueprint.id}' dismissed for " f"repo '{self.org_id}/{self.repo_name}', skipping"
                )
                return False

            case _:
                return True

    async def _execute(self) -> CheckResult:
        self.logger.info(
            "checking files for blueprint '%s' in repo '%s/%s'",
            self.blueprint.id,
            self.org_id,
            self.repo_name,
        )

        result = CheckResult(remediation_needed=False)

        rest_api = await self.rest_api

        files_needing_update = []
        for file in self.blueprint.files:
            try:
                content = await rest_api.content.get_content(self.org_id, self.repo_name, file.path)
                if file.strict is False or file.content == content:
                    continue
            except RuntimeError:
                # file does not exist, so let's create it
                pass

            files_needing_update.append(file)

        if len(files_needing_update) > 0:
            self.logger.debug(
                f"creating pull request for blueprint '{self.blueprint.id}' in repo '{self.org_id}/{self.repo_name}'"
            )
            await self._create_or_update_pull_request_if_necessary(rest_api, files_needing_update, result)

        return result

    async def _create_or_update_pull_request_if_necessary(
        self,
        rest_api: RestApi,
        files_needing_update: list[RequiredFile],
        result: CheckResult,
    ) -> None:
        result.remediation_needed = True

        default_branch = await rest_api.repo.get_default_branch(self.org_id, self.repo_name)
        branch_name = f"otterdog/blueprint/{self.blueprint.id}"

        try:
            await rest_api.reference.get_branch_reference(self.org_id, self.repo_name, branch_name)
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
                branch_name,
                default_branch_sha,
            )

        # update content in the branch if necessary
        for file in files_needing_update:
            await rest_api.content.update_content(
                self.org_id,
                self.repo_name,
                file.path,
                file.content,
                branch_name,
                f"Updating file {file.path}",
            )

        open_pull_requests = await rest_api.pull_request.get_pull_requests(
            self.org_id, self.repo_name, "open", default_branch
        )

        for pr in open_pull_requests:
            if pr["head"]["ref"] == branch_name:
                self.logger.info(f"PR#{pr['number']} already exists for branch '{branch_name}', skipping")
                result.remediation_pr = pr["number"]
                return

        self.logger.debug("creating pull request")

        pr_title = f"chore(otterdog): adding / updating file(s) due to blueprint `{self.blueprint.id}`"
        pr_body = (
            f"This PR has automatically been created by Otterdog due to "
            f"configured blueprint [{self.blueprint.name}]({self.blueprint.path})."
        )

        if self.blueprint.description is not None:
            pr_body += dedent(f"""\
            <br>
            Description:
            ```
            {self.blueprint.description.rstrip()}
            ```
            """)

        created_pr = await rest_api.pull_request.create_pull_request(
            self.org_id,
            self.repo_name,
            pr_title,
            branch_name,
            default_branch,
            pr_body,
        )

        result.remediation_pr = created_pr["number"]

    async def _post_execute(self, result_or_exception: CheckResult | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            await update_or_create_blueprint_status(
                self.org_id,
                self.repo_name,
                self.blueprint.id,
                BlueprintStatus.FAILURE,
            )
        else:
            status = (
                BlueprintStatus.SUCCESS
                if result_or_exception.remediation_needed is False
                else BlueprintStatus.REMEDIATION_PREPARED
            )
            await update_or_create_blueprint_status(
                self.org_id,
                self.repo_name,
                self.blueprint.id,
                status,
                result_or_exception.remediation_pr,
            )

    def __repr__(self) -> str:
        return f"CheckFilesTask(repo='{self.org_id}/{self.repo_name}', blueprint='{self.blueprint.id}')"
