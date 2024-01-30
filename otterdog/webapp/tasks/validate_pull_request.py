#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
import filecmp
import os
import re
from io import StringIO
from tempfile import TemporaryDirectory
from typing import Union, cast

from pydantic import ValidationError
from quart import current_app, render_template

from otterdog.config import OrganizationConfig
from otterdog.models import LivePatch
from otterdog.operations.diff_operation import DiffStatus
from otterdog.operations.local_plan import LocalPlanOperation
from otterdog.providers.github import RestApi
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.tasks import Task, get_otterdog_config
from otterdog.webapp.webhook.github_models import PullRequest, Repository


@dataclasses.dataclass
class ValidationResult:
    plan_output: str = ""
    validation_success: bool = True
    requires_secrets: bool = False


@dataclasses.dataclass(repr=False)
class ValidatePullRequestTask(Task[ValidationResult]):
    """Validates a PR and adds the result as a comment."""

    installation_id: int
    org_id: str
    repository: Repository
    pull_request_or_number: PullRequest | int
    log_level: LogLevel = LogLevel.WARN

    @property
    def check_base_config(self) -> bool:
        return True

    async def _pre_execute(self) -> None:
        rest_api = await self.get_rest_api(self.installation_id)

        if isinstance(self.pull_request_or_number, int):
            response = await rest_api.pull_request.get_pull_request(
                self.org_id, self.repository.name, str(self.pull_request_or_number)
            )
            try:
                self.pull_request = PullRequest.model_validate(response)
            except ValidationError as ex:
                self.logger.exception("failed to load pull request event data", exc_info=ex)
                return
        else:
            self.pull_request = cast(PullRequest, self.pull_request_or_number)

        self.logger.info(
            "validating pull request #%d of repo '%s' with log level '%s'",
            self.pull_request.number,
            self.repository.full_name,
            self.log_level,
        )

        await self._create_pending_status(rest_api)

        from .check_sync import CheckConfigurationInSyncTask

        check_task = CheckConfigurationInSyncTask(
            self.installation_id,
            self.org_id,
            self.repository,
            self.pull_request_or_number,
        )

        current_app.add_background_task(check_task.execute)

    async def _post_execute(self, result_or_exception: Union[ValidationResult, Exception]) -> None:
        rest_api = await self.get_rest_api(self.installation_id)

        if isinstance(result_or_exception, Exception):
            await self._create_failure_status(rest_api)
        else:
            await self._update_final_status(rest_api, result_or_exception)

    async def _execute(self) -> ValidationResult:
        otterdog_config = get_otterdog_config()
        pull_request_number = str(self.pull_request.number)
        project_name = otterdog_config.get_project_name(self.org_id) or self.org_id

        rest_api = await self.get_rest_api(self.installation_id)

        with TemporaryDirectory(dir=otterdog_config.jsonnet_base_dir) as work_dir:
            org_config = OrganizationConfig.of(
                project_name,
                self.org_id,
                {"provider": "inmemory", "api_token": rest_api.token},
                work_dir,
                otterdog_config,
            )

            jsonnet_config = org_config.jsonnet_config
            if not os.path.exists(jsonnet_config.org_dir):
                os.makedirs(jsonnet_config.org_dir)

            jsonnet_config.init_template()

            # get BASE config
            base_file = jsonnet_config.org_config_file + "-BASE"
            await get_config(
                rest_api,
                self.org_id,
                self.org_id,
                otterdog_config.default_config_repo,
                base_file,
                self.pull_request.base.ref,
            )

            # get HEAD config from PR
            head_file = jsonnet_config.org_config_file
            await get_config(
                rest_api,
                self.org_id,
                self.pull_request.head.repo.owner.login,
                self.pull_request.head.repo.name,
                head_file,
                self.pull_request.head.ref,
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

                operation.set_callback(callback)
                operation.init(otterdog_config, printer)

                plan_result = await operation.execute(org_config)

                validation_result.plan_output = output.getvalue()
                validation_result.validation_success = plan_result == 0
                self.logger.info("local plan:" + validation_result.plan_output)

            warnings = []
            if validation_result.requires_secrets:
                warnings.append("some of requested changes require secrets, need to apply these changes manually")

            comment = await render_template(
                "validation_comment.txt",
                sha=self.pull_request.head.sha,
                result=escape_for_github(validation_result.plan_output),
                warnings=warnings,
                admin_team=f"{self.org_id}/{get_admin_team()}",
            )

            # add a comment about the validation result to the PR
            await rest_api.issue.create_comment(
                self.org_id, otterdog_config.default_config_repo, pull_request_number, comment
            )

            return validation_result

    async def _create_pending_status(self, rest_api: RestApi):
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repository.name,
            self.pull_request.head.sha,
            "pending",
            _get_webhook_validation_context(),
            "validating configuration change using otterdog",
        )

    async def _create_failure_status(self, rest_api: RestApi):
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repository.name,
            self.pull_request.head.sha,
            "failure",
            _get_webhook_validation_context(),
            "otterdog validation failed, please contact an admin",
        )

    async def _update_final_status(self, rest_api: RestApi, validation_result: ValidationResult) -> None:
        if validation_result.validation_success is True:
            desc = "otterdog validation completed successfully"
            status = "success"
        else:
            desc = "otterdog validation failed, check validation result in comment history"
            status = "error"

        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repository.name,
            self.pull_request.head.sha,
            status,
            _get_webhook_validation_context(),
            desc,
        )

    def __repr__(self) -> str:
        pull_request_number = (
            self.pull_request_or_number
            if isinstance(self.pull_request_or_number, int)
            else self.pull_request_or_number.number
        )
        return f"ValidatePullRequestTask(repo={self.repository.full_name}, pull_request={pull_request_number})"


def _get_webhook_validation_context() -> str:
    return current_app.config["GITHUB_WEBHOOK_VALIDATION_CONTEXT"]


def get_admin_team() -> str:
    return current_app.config["GITHUB_ADMIN_TEAM"]


async def get_config(rest_api: RestApi, org_id: str, owner: str, repo: str, filename: str, ref: str):
    path = f"otterdog/{org_id}.jsonnet"
    content = await rest_api.content.get_content(
        owner,
        repo,
        path,
        ref,
    )
    with open(filename, "w") as file:
        file.write(content)


def escape_for_github(text: str) -> str:
    lines = text.splitlines()

    output = []
    for line in lines:
        ansi_escape = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]")
        line = ansi_escape.sub("", line)

        diff_escape = re.compile(r"(\s+)([-+!])(\s+)")
        line = diff_escape.sub(r"\g<2>\g<1>", line)

        diff_escape2 = re.compile(r"(\s+)(~)")
        line = diff_escape2.sub(r"!\g<1>", line)

        output.append(line)

    return "\n".join(output)
