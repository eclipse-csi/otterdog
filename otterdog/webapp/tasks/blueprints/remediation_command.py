#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from quart import render_template

from otterdog.webapp.blueprints import create_blueprint_from_model
from otterdog.webapp.db.models import BlueprintStatus, TaskModel
from otterdog.webapp.db.service import (
    find_blueprint,
    find_blueprint_status,
    get_configuration_by_github_id,
    update_or_create_blueprint_status,
)
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.tasks.blueprints.branches import (
    blueprint_id_from_branch,
    reset_branch_to_default_branch,
    sync_branch_with_default_branch,
)
from otterdog.webapp.utils import get_app_bot_login


class RemediationCommand(StrEnum):
    # bring the branch up to date with the default branch and rewrite the blueprint's files on top
    REBASE = "rebase"
    # discard the branch, recreate it from the default branch and reuse / reopen the pull request
    RECREATE = "recreate"
    # dismiss the blueprint for this repository explicitly
    IGNORE = "ignore"


class CommandOutcome(StrEnum):
    PERMISSION_DENIED = "permission_denied"
    NOT_A_REMEDIATION_PR = "not_a_remediation_pr"
    UNKNOWN_BLUEPRINT = "unknown_blueprint"
    DISMISSED = "dismissed"
    ALREADY_DISMISSED = "already_dismissed"
    REBASED = "rebased"
    RECREATED = "recreated"
    IGNORED = "ignored"


@dataclass
class CommandResult:
    outcome: CommandOutcome
    blueprint_id: str | None = None
    branch_reset: bool = False
    pull_request_reopened: bool = False


@dataclass(repr=False)
class RemediationCommandTask(InstallationBasedTask, Task[CommandResult]):
    """
    Handles `/otterdog rebase`, `/otterdog recreate` and `/otterdog ignore` on a remediation
    pull request of a blueprint (head branch `otterdog/blueprint/<id>`).
    """

    installation_id: int
    org_id: str
    repo_name: str
    pull_request_number: int
    author: str
    command: RemediationCommand

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _execute(self) -> CommandResult:
        self.logger.info(
            "'%s' requested by '%s' on '%s/%s#%d'",
            self.command,
            self.author,
            self.org_id,
            self.repo_name,
            self.pull_request_number,
        )

        rest_api = await self.rest_api

        if not await self.has_write_access(self.org_id, self.repo_name, self.author):
            return await self._finish(CommandResult(CommandOutcome.PERMISSION_DENIED))

        pull_request = await rest_api.pull_request.get_pull_request(
            self.org_id, self.repo_name, str(self.pull_request_number)
        )

        branch_name = pull_request["head"]["ref"]
        blueprint_id = blueprint_id_from_branch(branch_name)
        if blueprint_id is None:
            return await self._finish(CommandResult(CommandOutcome.NOT_A_REMEDIATION_PR))

        blueprint_model = await find_blueprint(self.org_id, blueprint_id)
        if blueprint_model is None:
            return await self._finish(CommandResult(CommandOutcome.UNKNOWN_BLUEPRINT, blueprint_id))

        blueprint = create_blueprint_from_model(blueprint_model)
        config_model = await get_configuration_by_github_id(self.org_id)
        default_branch = pull_request["base"]["ref"]
        is_open = pull_request["state"] == "open"

        match self.command:
            case RemediationCommand.IGNORE:
                return await self._ignore(blueprint_id, is_open)

            case RemediationCommand.REBASE:
                status = await find_blueprint_status(self.org_id, self.repo_name, blueprint_id)
                if not is_open or (status is not None and status.status == BlueprintStatus.DISMISSED):
                    return await self._finish(CommandResult(CommandOutcome.DISMISSED, blueprint_id))

                branch_reset = await sync_branch_with_default_branch(
                    rest_api,
                    self.org_id,
                    self.repo_name,
                    branch_name,
                    default_branch,
                    await get_app_bot_login(),
                    self.logger,
                )
                await blueprint.evaluate_repo(self.installation_id, self.org_id, self.repo_name, config_model)
                return await self._finish(CommandResult(CommandOutcome.REBASED, blueprint_id, branch_reset))

            case RemediationCommand.RECREATE:
                await reset_branch_to_default_branch(rest_api, self.org_id, self.repo_name, branch_name, default_branch)

                reopened = False
                if not is_open:
                    try:
                        await rest_api.pull_request.update_pull_request(
                            self.org_id, self.repo_name, self.pull_request_number, state="open"
                        )
                        reopened = True
                    except RuntimeError as ex:
                        # e.g. the pull request is too old to be reopened, a new one will be created
                        self.logger.warning(
                            f"failed to reopen pull request #{self.pull_request_number} in "
                            f"'{self.org_id}/{self.repo_name}', a new one will be created",
                            exc_info=ex,
                        )

                # clear a dismissal and detach the stored status from the pull request, so that the
                # evaluation is not blocked by the closed pull request on GitHub
                await update_or_create_blueprint_status(
                    self.org_id,
                    self.repo_name,
                    blueprint_id,
                    BlueprintStatus.RECHECK,
                    self.pull_request_number if (is_open or reopened) else None,
                )

                await blueprint.evaluate_repo(self.installation_id, self.org_id, self.repo_name, config_model)
                return await self._finish(CommandResult(CommandOutcome.RECREATED, blueprint_id, True, reopened))

    async def _ignore(self, blueprint_id: str, is_open: bool) -> CommandResult:
        status = await find_blueprint_status(self.org_id, self.repo_name, blueprint_id)
        if status is not None and status.status == BlueprintStatus.DISMISSED:
            return await self._finish(CommandResult(CommandOutcome.ALREADY_DISMISSED, blueprint_id))

        await update_or_create_blueprint_status(
            self.org_id,
            self.repo_name,
            blueprint_id,
            BlueprintStatus.DISMISSED,
            self.pull_request_number,
        )

        if is_open:
            # closing the pull request triggers the regular dismissal comment via the webhook
            rest_api = await self.rest_api
            await rest_api.pull_request.update_pull_request(
                self.org_id, self.repo_name, self.pull_request_number, state="closed"
            )

        return await self._finish(CommandResult(CommandOutcome.IGNORED, blueprint_id))

    async def _post_execute(self, result_or_exception: CommandResult | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            await self.comment_on_failure(
                self.org_id,
                self.repo_name,
                self.pull_request_number,
                self.author,
                str(self.command),
                result_or_exception,
            )

    async def _finish(self, result: CommandResult) -> CommandResult:
        comment = await render_template(
            "comment/remediation_command_comment.txt",
            command=self.command,
            result=result,
            author=self.author,
        )

        rest_api = await self.rest_api
        await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.pull_request_number), comment)
        return result

    def __repr__(self) -> str:
        return (
            f"RemediationCommandTask(repo='{self.org_id}/{self.repo_name}', "
            f"pull_request=#{self.pull_request_number}, command='{self.command}')"
        )
