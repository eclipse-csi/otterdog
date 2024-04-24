#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from io import StringIO

from quart import current_app, render_template

from otterdog.models import LivePatch
from otterdog.operations.diff_operation import DiffStatus
from otterdog.operations.plan import PlanOperation
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import (
    get_latest_sync_or_apply_task_for_organization,
    update_or_create_pull_request,
)
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import (
    backoff_if_needed,
    current_utc_time,
    escape_for_github,
    fetch_config_from_github,
    get_full_admin_team_slugs,
    get_otterdog_config,
    make_aware_utc,
)
from otterdog.webapp.webhook.github_models import PullRequest


@dataclass(repr=False)
class CheckConfigurationInSyncTask(InstallationBasedTask, Task[bool]):
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

    @property
    def is_triggered_from_comment(self) -> bool:
        # right now if the pull request is a number, the task has been
        # created from a PR comment, this should be made cleaner
        return isinstance(self.pull_request_or_number, int)

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _pre_execute(self) -> bool:
        self.logger.info(
            "checking if base ref is in sync for pull request #%d of repo '%s/%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )

        rest_api = await self.rest_api

        if isinstance(self.pull_request_or_number, int):
            response = await rest_api.pull_request.get_pull_request(
                self.org_id, self.repo_name, str(self.pull_request_number)
            )
            self._pull_request = PullRequest.model_validate(response)
        else:
            self._pull_request = self.pull_request_or_number

        # do not perform checks every time a pull request is synchronized
        # if the last check was done within an hour
        if self.is_triggered_from_comment is False:
            commits = await rest_api.pull_request.get_commits(
                self.org_id,
                self.repo_name,
                str(self.pull_request_number),
            )

            if len(commits) > 1:
                previous_commit = commits[-2]
                commit_time = make_aware_utc(
                    datetime.strptime(previous_commit["commit"]["committer"]["date"], "%Y-%m-%dT%H:%M:%SZ")
                )
                current_time = current_utc_time()
                timedelta_since_last_commit = current_time - commit_time
                if timedelta_since_last_commit < timedelta(hours=1):
                    commit_statuses = await rest_api.commit.get_commit_statuses(
                        self.org_id,
                        self.repo_name,
                        previous_commit["sha"],
                    )

                    commit_status = list(
                        filter(
                            lambda x: x["context"] == _get_webhook_sync_context() and x["state"] != "pending",
                            commit_statuses,
                        )
                    )

                    # if a previous commit status was found, propagate it directly
                    if len(commit_status) > 1:
                        await self._update_final_status(commit_status[0]["state"] == "success")
                        return False

        latest_sync_or_apply_task = await get_latest_sync_or_apply_task_for_organization(self.org_id, self.repo_name)
        # to avoid secondary rate limit failures, backoff at least 1 min before running another sync task
        if latest_sync_or_apply_task is not None:
            await backoff_if_needed(latest_sync_or_apply_task.created_at, timedelta(minutes=1))

        await self._create_pending_status()

        return True

    async def _post_execute(self, result_or_exception: bool | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            await self._create_failure_status()
        else:
            await self._update_final_status(result_or_exception)

    async def _execute(self) -> bool:
        async with self.get_organization_config() as org_config:
            rest_api = await self.rest_api

            # get BASE config
            base_file = org_config.jsonnet_config.org_config_file
            await fetch_config_from_github(
                rest_api,
                self.org_id,
                self.org_id,
                org_config.config_repo,
                base_file,
                # always check the HEAD of the default branch
                # PRs might not be up-to-date
            )

            output = StringIO()
            printer = IndentingPrinter(output, log_level=LogLevel.ERROR)
            operation = PlanOperation(True, False, False, "")

            config_in_sync = True

            def sync_callback(org_id: str, diff_status: DiffStatus, patches: list[LivePatch]):
                nonlocal config_in_sync
                config_in_sync = diff_status.total_changes(True) == 0

            otterdog_config = await get_otterdog_config()
            operation.set_callback(sync_callback)
            operation.init(otterdog_config, printer)

            await operation.execute(org_config)

            self.merge_statistics_from_provider(operation.gh_client)

            sync_output = output.getvalue()
            self.logger.info("sync plan:\n" + sync_output)

            if config_in_sync is False:
                comment = await render_template(
                    "comment/out_of_sync_comment.txt",
                    result=escape_for_github(sync_output),
                    admin_teams=get_full_admin_team_slugs(self.org_id),
                )
            else:
                comment = await render_template("comment/in_sync_comment.txt")

            await self.minimize_outdated_comments(
                self.org_id,
                self.repo_name,
                self.pull_request_number,
                "<!-- Otterdog Comment: check-sync -->",
            )

            rest_api = await self.rest_api
            await rest_api.issue.create_comment(
                self.org_id,
                org_config.config_repo,
                self.pull_request_number,
                comment,
            )

            return config_in_sync

    async def _create_pending_status(self):
        rest_api = await self.rest_api
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repo_name,
            self._pull_request.head.sha,
            "pending",
            _get_webhook_sync_context(),
            "checking if configuration is in-sync using otterdog",
        )

    async def _create_failure_status(self):
        rest_api = await self.rest_api
        await rest_api.commit.create_commit_status(
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

        rest_api = await self.rest_api
        await rest_api.commit.create_commit_status(
            self.org_id,
            self.repo_name,
            self._pull_request.head.sha,
            status,
            _get_webhook_sync_context(),
            desc,
        )

        pull_request_model = await update_or_create_pull_request(
            self.org_id,
            self.repo_name,
            self._pull_request,
            in_sync=config_in_sync,
        )

        if pull_request_model.can_be_automerged():
            self.schedule_automerge_task(self.org_id, self.repo_name, self.pull_request_number)

    def __repr__(self) -> str:
        return (
            f"CheckConfigurationInSyncTask(repo='{self.org_id}/{self.repo_name}', "
            f"pull_request=#{self.pull_request_number})"
        )


def _get_webhook_sync_context() -> str:
    return current_app.config["GITHUB_WEBHOOK_SYNC_CONTEXT"]
