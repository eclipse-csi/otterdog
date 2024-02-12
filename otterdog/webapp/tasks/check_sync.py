#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from io import StringIO
from typing import Union

from quart import current_app, render_template

from otterdog.models import LivePatch
from otterdog.operations.diff_operation import DiffStatus
from otterdog.operations.plan import PlanOperation
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.tasks import Task
from otterdog.webapp.tasks.validate_pull_request import get_admin_team
from otterdog.webapp.utils import (
    escape_for_github,
    fetch_config_from_github,
    get_otterdog_config,
)
from otterdog.webapp.webhook.github_models import PullRequest


@dataclasses.dataclass(repr=False)
class CheckConfigurationInSyncTask(Task[bool]):
    """Checks whether the base ref is in sync with live settings."""

    installation_id: int
    org_id: str
    repo_name: str
    pull_request_or_number: PullRequest | int

    @property
    def pull_request_number(self) -> int:
        return (
            self.pull_request_or_number
            if isinstance(self.pull_request_or_number, int)
            else self.pull_request_or_number.number
        )

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _pre_execute(self) -> None:
        self.logger.info(
            "checking if base ref is in sync for pull request #%d of repo '%s/%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )

        self._rest_api = await self.get_rest_api(self.installation_id)
        if isinstance(self.pull_request_or_number, int):
            response = await self._rest_api.pull_request.get_pull_request(
                self.org_id, self.repo_name, str(self.pull_request_number)
            )
            self._pull_request = PullRequest.model_validate(response)
        else:
            self._pull_request = self.pull_request_or_number

        await self._create_pending_status()

    async def _post_execute(self, result_or_exception: Union[bool, Exception]) -> None:
        if isinstance(result_or_exception, Exception):
            await self._create_failure_status()
        else:
            await self._update_final_status(result_or_exception)

    async def _execute(self) -> bool:
        rest_api = self._rest_api
        otterdog_config = await get_otterdog_config()

        async with self.get_organization_config(otterdog_config, rest_api, self.installation_id) as org_config:
            # get BASE config
            base_file = org_config.jsonnet_config.org_config_file
            await fetch_config_from_github(
                rest_api,
                self.org_id,
                self.org_id,
                org_config.config_repo,
                base_file,
                self._pull_request.base.ref,
            )

            output = StringIO()
            printer = IndentingPrinter(output, log_level=LogLevel.ERROR)
            operation = PlanOperation(True, False, False, "")

            config_in_sync = True

            def sync_callback(org_id: str, diff_status: DiffStatus, patches: list[LivePatch]):
                nonlocal config_in_sync
                config_in_sync = diff_status.total_changes(True) == 0

            operation.set_callback(sync_callback)
            operation.init(otterdog_config, printer)

            await operation.execute(org_config)

            sync_output = output.getvalue()
            self.logger.info("sync plan:\n" + sync_output)

            if config_in_sync is False:
                comment = await render_template(
                    "comment/out_of_sync_comment.txt",
                    result=escape_for_github(sync_output),
                    admin_team=f"{self.org_id}/{get_admin_team()}",
                )
            else:
                comment = await render_template("comment/in_sync_comment.txt")

            await rest_api.issue.create_comment(
                self.org_id,
                org_config.config_repo,
                self.pull_request_number,
                comment,
            )

            return config_in_sync

    async def _create_pending_status(self):
        await self._rest_api.commit.create_commit_status(
            self.org_id,
            self.repo_name,
            self._pull_request.head.sha,
            "pending",
            _get_webhook_sync_context(),
            "checking if configuration is in-sync using otterdog",
        )

    async def _create_failure_status(self):
        await self._rest_api.commit.create_commit_status(
            self.org_id,
            self.repo_name,
            self._pull_request.head.sha,
            "failure",
            _get_webhook_sync_context(),
            "otterdog sync check failed, please contact an admin",
        )

    async def _update_final_status(self, config_in_sync: bool) -> None:
        if config_in_sync is True:
            desc = "otterdog sync check completed successfully"
            status = "success"
        else:
            desc = "otterdog sync check failed, check comment history"
            status = "error"

        await self._rest_api.commit.create_commit_status(
            self.org_id,
            self.repo_name,
            self._pull_request.head.sha,
            status,
            _get_webhook_sync_context(),
            desc,
        )

    def __repr__(self) -> str:
        return (
            f"CheckConfigurationInSyncTask(repo='{self.org_id}/{self.repo_name}', "
            f"pull_request=#{self.pull_request_number})"
        )


def _get_webhook_sync_context() -> str:
    return current_app.config["GITHUB_WEBHOOK_SYNC_CONTEXT"]
