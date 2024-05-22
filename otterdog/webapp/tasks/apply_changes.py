#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass
from datetime import timedelta
from io import StringIO

from quart import render_template

from otterdog.operations.apply import ApplyOperation
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.db.models import ApplyStatus, TaskModel
from otterdog.webapp.db.service import (
    find_pull_request,
    get_latest_sync_or_apply_task_for_organization,
    update_pull_request,
)
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import (
    backoff_if_needed,
    escape_for_github,
    fetch_config_from_github,
    get_admin_teams,
    get_full_admin_team_slugs,
    get_otterdog_config,
)
from otterdog.webapp.webhook.github_models import PullRequest


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
    repo_name: str
    pull_request_or_number: PullRequest | int
    author: str | None = None

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

    async def _pre_execute(self) -> bool:
        self.logger.info(
            "applying merged pull request #%d of repo '%s/%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )

        if isinstance(self.pull_request_or_number, int):
            rest_api = await self.rest_api
            response = await rest_api.pull_request.get_pull_request(
                self.org_id, self.repo_name, str(self.pull_request_or_number)
            )
            self._pull_request = PullRequest.model_validate(response)
        else:
            self._pull_request = self.pull_request_or_number

        pr_model = await find_pull_request(self.org_id, self.repo_name, self.pull_request_number)
        if pr_model is None:
            raise RuntimeError(
                f"failed to fetch pull request #{self.pull_request_number} in repo '{self.org_id}/{self.repo_name}'"
            )
        else:
            self._pr_model = pr_model

        if self._pull_request.merged is not True or self._pull_request.merge_commit_sha is None:
            self.logger.error(
                f"trying to apply changes for unmerged pull request #{self.pull_request_number} "
                f"of org '{self.org_id}', skipping"
            )
            return False

        if self._pr_model.apply_status == ApplyStatus.COMPLETED:
            self.logger.error(
                f"trying to apply changes for already applied pull request #{self.pull_request_number} "
                f"of org '{self.org_id}', skipping"
            )
            return False

        if self._pr_model.valid is not True:
            self.logger.error(
                f"trying to apply changes for invalid pull request #{self.pull_request_number} "
                f"of org '{self.org_id}', skipping"
            )
            return False

        if self.author is not None:
            rest_api = await self.rest_api
            admin_teams = get_admin_teams()
            is_admin = False
            for admin_team in admin_teams:
                if await rest_api.team.is_user_member_of_team(self.org_id, admin_team, self.author):
                    is_admin = True
                    break

            if not is_admin:
                comment = await render_template(
                    "comment/wrong_team_apply_comment.txt", admin_teams=get_full_admin_team_slugs(self.org_id)
                )
                await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.pull_request_number), comment)

                self.logger.error(
                    f"apply for pull request #{self.pull_request_number} triggered by user '{self.author}' "
                    f"who is not a member of the admin team, skipping"
                )

                return False

        latest_sync_or_apply_task = await get_latest_sync_or_apply_task_for_organization(self.org_id, self.repo_name)
        # to avoid secondary rate limit failures, backoff at least 1 min before running another sync task
        if latest_sync_or_apply_task is not None:
            await backoff_if_needed(latest_sync_or_apply_task.created_at, timedelta(minutes=1))

        return True

    async def _post_execute(self, result_or_exception: ApplyResult | None | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            self._pr_model.apply_status = ApplyStatus.FAILED
        elif result_or_exception is None:
            pass
        else:
            if result_or_exception.apply_success is False or result_or_exception.partial:
                self._pr_model.apply_status = ApplyStatus.PARTIALLY_APPLIED
            else:
                self._pr_model.apply_status = ApplyStatus.COMPLETED

            await update_pull_request(self._pr_model)

    async def _execute(self) -> ApplyResult:
        apply_result = ApplyResult()
        pull_request_number = str(self.pull_request_number)

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
                self._pull_request.merge_commit_sha,
            )

            output = StringIO()
            printer = IndentingPrinter(output, log_level=LogLevel.WARN)

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

            # set concurrency to 20 to avoid hitting secondary rate limits with installation tokens
            operation.concurrency = 20

            otterdog_config = await get_otterdog_config()
            operation.init(otterdog_config, printer)

            try:
                operation_result = await operation.execute(org_config)
                apply_result.apply_output = output.getvalue()
                apply_result.apply_success = operation_result == 0
                apply_result.partial = self._pr_model.requires_manual_apply is True
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
                admin_teams=get_full_admin_team_slugs(self.org_id),
            )

            await rest_api.issue.create_comment(self.org_id, org_config.config_repo, pull_request_number, result)

            return apply_result

    def __repr__(self) -> str:
        return f"ApplyChangesTask(repo='{self.org_id}/{self.repo_name}', pull_request=#{self.pull_request_number})"
