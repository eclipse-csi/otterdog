#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import filecmp
from dataclasses import dataclass
from io import StringIO

from quart import current_app, render_template

from otterdog.models import LivePatch
from otterdog.operations.diff_operation import DiffStatus
from otterdog.operations.local_plan import LocalPlanOperation
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import update_or_create_pull_request
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import (
    escape_for_github,
    fetch_config_from_github,
    get_admin_team,
    get_otterdog_config,
)
from otterdog.webapp.webhook.github_models import PullRequest


@dataclass
class ValidationResult:
    plan_output: str = ""
    validation_success: bool = True
    requires_secrets: bool = False


@dataclass(repr=False)
class ValidatePullRequestTask(InstallationBasedTask, Task[ValidationResult]):
    """Validates a PR and adds the result as a comment."""

    installation_id: int
    org_id: str
    repo_name: str
    pull_request_or_number: PullRequest | int
    log_level: LogLevel = LogLevel.WARN

    @property
    def pull_request_number(self) -> int:
        return (
            self.pull_request_or_number
            if isinstance(self.pull_request_or_number, int)
            else self.pull_request_or_number.number
        )

    @property
    def check_base_config(self) -> bool:
        return True

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _pre_execute(self) -> None:
        if isinstance(self.pull_request_or_number, int):
            rest_api = await self.rest_api
            response = await rest_api.pull_request.get_pull_request(
                self.org_id, self.repo_name, str(self.pull_request_or_number)
            )
            self._pull_request = PullRequest.model_validate(response)
        else:
            self._pull_request = self.pull_request_or_number

        self.logger.info(
            "validating pull request #%d of repo '%s/%s' with log level '%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
            self.log_level,
        )

        await self._create_pending_status()

    async def _post_execute(self, result_or_exception: ValidationResult | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            await self._create_failure_status()
        else:
            await self._update_final_status(result_or_exception)

    async def _execute(self) -> ValidationResult:
        async with self.get_organization_config() as org_config:
            rest_api = await self.rest_api

            org_config_file = org_config.jsonnet_config.org_config_file

            # get BASE config
            base_file = org_config_file + "-BASE"
            await fetch_config_from_github(
                rest_api,
                self.org_id,
                self.org_id,
                org_config.config_repo,
                base_file,
                # always check against the HEAD of the default branch
                # PRs might not be up-to-date
            )

            assert self._pull_request.head.repo is not None

            # get HEAD config from PR
            head_file = org_config_file
            await fetch_config_from_github(
                rest_api,
                self.org_id,
                self._pull_request.head.repo.owner.login,
                self._pull_request.head.repo.name,
                head_file,
                self._pull_request.head.ref,
            )

            validation_result = ValidationResult()

            if filecmp.cmp(base_file, head_file):
                self.logger.debug("head and base config are identical, no need to validate")
                validation_result.plan_output = "No changes."
                validation_result.validation_success = True
            else:
                output = StringIO()
                printer = IndentingPrinter(output, log_level=self.log_level)
                operation = LocalPlanOperation("-BASE", False, False, "")

                def callback(org_id: str, diff_status: DiffStatus, patches: list[LivePatch]):
                    validation_result.requires_secrets = any(list(map(lambda x: x.requires_secrets(), patches)))

                otterdog_config = await get_otterdog_config()

                operation.set_callback(callback)
                operation.init(otterdog_config, printer)

                try:
                    plan_result = await operation.execute(org_config)
                    validation_result.plan_output = output.getvalue()
                    validation_result.validation_success = plan_result == 0
                except Exception as ex:
                    self.logger.exception("exception during validate", exc_info=ex)

                    validation_result.plan_output = str(ex)
                    validation_result.validation_success = False

                self.logger.info("local plan:" + validation_result.plan_output)

            warnings = []
            if validation_result.requires_secrets:
                warnings.append("some of requested changes require secrets, need to apply these changes manually")

            comment = await render_template(
                "comment/validation_comment.txt",
                sha=self._pull_request.head.sha,
                result=escape_for_github(validation_result.plan_output),
                warnings=warnings,
                admin_team=f"{self.org_id}/{get_admin_team()}",
            )

            await self.minimize_outdated_comments(
                self.org_id,
                self.repo_name,
                self.pull_request_number,
                "<!-- Otterdog Comment: validate -->",
            )

            # add a comment about the validation result to the PR
            await rest_api.issue.create_comment(
                self.org_id, org_config.config_repo, str(self.pull_request_number), comment
            )

            return validation_result

    async def _create_pending_status(self):
        rest_api = await self.rest_api
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repo_name,
            self._pull_request.head.sha,
            "pending",
            _get_webhook_validation_context(),
            "validating configuration change using otterdog",
        )

    async def _create_failure_status(self):
        rest_api = await self.rest_api
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repo_name,
            self._pull_request.head.sha,
            "failure",
            _get_webhook_validation_context(),
            "otterdog validation failed, please contact an admin",
        )

    async def _update_final_status(self, validation_result: ValidationResult) -> None:
        if validation_result.validation_success is True:
            desc = "otterdog validation completed successfully"
            status = "success"
        else:
            desc = "otterdog validation failed, check validation result in comment history"
            status = "error"

        rest_api = await self.rest_api
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repo_name,
            self._pull_request.head.sha,
            status,
            _get_webhook_validation_context(),
            desc,
        )

        await update_or_create_pull_request(
            self.org_id,
            self.repo_name,
            self._pull_request,
            valid=validation_result.validation_success,
            requires_manual_apply=validation_result.requires_secrets,
        )

    def __repr__(self) -> str:
        return (
            f"ValidatePullRequestTask(repo='{self.org_id}/{self.repo_name}', "
            f"pull_request=#{self.pull_request_number})"
        )


def _get_webhook_validation_context() -> str:
    return current_app.config["GITHUB_WEBHOOK_VALIDATION_CONTEXT"]
