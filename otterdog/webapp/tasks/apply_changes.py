#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass
from io import StringIO

from quart import render_template

from otterdog.operations.apply import ApplyOperation
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.db.models import ApplyStatus, TaskModel
from otterdog.webapp.db.service import find_pull_request, update_pull_request
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import (
    escape_for_github,
    fetch_config_from_github,
    get_admin_team,
    get_otterdog_config,
)
from otterdog.webapp.webhook.github_models import PullRequest, Repository


@dataclass
class ApplyResult:
    apply_output: str = ""
    apply_success: bool = True
    partial: bool = False


@dataclass(repr=False)
class ApplyChangesTask(InstallationBasedTask, Task[ApplyResult]):
    """Applies changes from a merged PR and adds the result as a comment."""

    installation_id: int
    org_id: str
    repository: Repository
    pull_request: PullRequest

    @property
    def pull_request_number(self) -> int:
        return self.pull_request.number

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repository.name,
            pull_request=self.pull_request.number,
        )

    async def _pre_execute(self) -> None:
        self._pr_model = await find_pull_request(self.org_id, self.repository.name, self.pull_request.number)
        if self._pr_model is None:
            self.logger.error(
                f"failed to find pull request #{self.pull_request_number} in repo '{self.repository.full_name}'"
            )

    async def _post_execute(self, result_or_exception: ApplyResult | Exception) -> None:
        if self._pr_model is None:
            return

        if isinstance(result_or_exception, Exception):
            self._pr_model.apply_status = ApplyStatus.FAILED
        else:
            if result_or_exception.apply_success is False or result_or_exception.partial:
                self._pr_model.apply_status = ApplyStatus.PARTIALLY_APPLIED
            else:
                self._pr_model.apply_status = ApplyStatus.COMPLETED

        await update_pull_request(self._pr_model)

    async def _execute(self) -> ApplyResult:
        assert self.pull_request.merged is True
        assert self.pull_request.merge_commit_sha is not None

        self.logger.info(
            "applying merged pull request #%d of repo '%s'", self.pull_request.number, self.repository.full_name
        )

        apply_result = ApplyResult()

        pull_request_number = str(self.pull_request.number)

        async with self.get_organization_config() as org_config:
            rest_api = await self.rest_api

            # get config from merge commit sha
            head_file = org_config.jsonnet_config.org_config_file
            await fetch_config_from_github(
                rest_api,
                self.org_id,
                self.org_id,
                org_config.config_repo,
                head_file,
                self.pull_request.merge_commit_sha,
            )

            output = StringIO()
            printer = IndentingPrinter(output, log_level=LogLevel.ERROR)

            # let's create an apply operation that forces processing but does not update
            # any web UI settings and resources using credentials
            operation = ApplyOperation(
                force_processing=True,
                no_web_ui=True,
                update_webhooks=False,
                update_secrets=False,
                update_filter="",
                delete_resources=True,
                resolve_secrets=False,
                include_resources_with_secrets=False,
            )

            otterdog_config = await get_otterdog_config()
            operation.init(otterdog_config, printer)

            try:
                operation_result = await operation.execute(org_config)
                apply_result.apply_output = output.getvalue()
                apply_result.apply_success = operation_result == 0
                if self._pr_model is not None:
                    apply_result.partial = self._pr_model.requires_manual_apply
                else:
                    apply_result.partial = False
            except Exception as ex:
                self.logger.exception("exception during apply", exc_info=ex)

                apply_result.apply_output = str(ex)
                apply_result.apply_success = False

            self.merge_statistics_from_provider(operation.gh_client)

            self.logger.info("apply:" + apply_result.apply_output)

            result = await render_template(
                "comment/applied_changes_comment.txt",
                output=escape_for_github(apply_result.apply_output),
                success=apply_result.apply_success,
                partial=apply_result.partial,
                admin_team=f"{self.org_id}/{get_admin_team()}",
            )

            await rest_api.issue.create_comment(self.org_id, org_config.config_repo, pull_request_number, result)

            return apply_result

    def __repr__(self) -> str:
        return f"ApplyChangesTask(repo={self.repository.full_name}, pull_request={self.pull_request.number})"
