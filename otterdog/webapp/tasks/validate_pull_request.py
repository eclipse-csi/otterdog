#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import asyncio
import filecmp
from dataclasses import dataclass
from io import StringIO
from typing import TYPE_CHECKING

from quart import current_app, render_template

from otterdog.models import LivePatchType
from otterdog.operations.local_plan import LocalPlanOperation
from otterdog.utils import IndentingPrinter, LogLevel, restrict_jsonnet_imports, unwrap
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import update_or_create_pull_request
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import (
    escape_for_github,
    fetch_config_from_github,
    get_full_admin_team_slugs,
    get_otterdog_config,
)
from otterdog.webapp.webhook.github_models import PullRequest, Repository

if TYPE_CHECKING:
    from otterdog.operations.diff_operation import DiffResult
    from otterdog.providers.github.rest import RestApi


# delays in seconds before looking again for the merge commit of a pull request, as GitHub creates it
# in the background once the pull request changed
_MERGE_COMMIT_RETRY_DELAYS = (1, 2, 4, 8)


@dataclass(frozen=True)
class _MergeCommit:
    """A commit merging the head of a pull request into the commit `base_sha` of its base branch."""

    sha: str
    base_sha: str


@dataclass
class ValidationResult:
    """Validation output and safety gates for applying a pull request.

    Cost-related changes are tracked separately because they require designated
    review and must not be auto-merged, even when they need no manual UI work.
    """

    plan_output: str = ""
    validation_success: bool = False
    touches_non_configuration: bool = False
    requires_secrets: bool | None = None
    requires_web_ui: bool | None = None
    cost_related: bool | None = None
    includes_deletions: bool | None = None

    def auto_merge_blockers(self) -> list[str]:
        """Reasons why the pull request cannot be merged via `/otterdog merge`."""
        blockers = []
        if self.requires_secrets:
            blockers.append("some of the requested changes require secrets")
        if self.requires_web_ui:
            blockers.append("some of the requested changes require accessing the Web UI")
        if self.cost_related:
            blockers.append("some of the requested changes may incur costs")
        if self.includes_deletions:
            blockers.append("some of the requested changes remove resources")
        if self.touches_non_configuration:
            blockers.append("the pull request modifies files other than the organization configuration")
        return blockers

    @property
    def supports_auto_merge(self) -> bool:
        return not self.auto_merge_blockers()


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

    async def _pre_execute(self) -> bool:
        if isinstance(self.pull_request_or_number, int):
            rest_api = await self.rest_api
            response = await rest_api.pull_request.get_pull_request(
                self.org_id, self.repo_name, str(self.pull_request_or_number)
            )
            self._pull_request = PullRequest.model_validate(response)
        else:
            self._pull_request = self.pull_request_or_number

        await self._create_pending_status()

        return True

    async def _post_execute(self, result_or_exception: ValidationResult | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            await self._create_failure_status()
        else:
            await self._update_final_status(result_or_exception)

    async def _execute(self) -> ValidationResult:
        self.logger.info(
            "validating pull request #%d of repo '%s/%s' with log level '%s'",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
            self.log_level,
        )

        async with self.get_organization_config() as org_config:
            rest_api = await self.rest_api

            base_file = org_config.jsonnet_config.org_config_file + "-BASE"
            head_file = org_config.jsonnet_config.org_config_file

            merge_commit = await self._find_merge_commit(rest_api)
            if merge_commit is not None:
                # validate what merging the pull request applies, see ApplyChangesTask: the merge keeps the
                # changes made on the default branch since the branch of the pull request has been created
                await fetch_config_from_github(
                    rest_api,
                    self.org_id,
                    self.org_id,
                    org_config.config_repo,
                    base_file,
                    merge_commit.base_sha,
                )
                await fetch_config_from_github(
                    rest_api,
                    self.org_id,
                    self.org_id,
                    org_config.config_repo,
                    head_file,
                    merge_commit.sha,
                )
            else:
                # without merge commit, e.g. in case of conflicts, validate the head of the pull request
                # against the head of the default branch
                await fetch_config_from_github(
                    rest_api,
                    self.org_id,
                    self.org_id,
                    org_config.config_repo,
                    base_file,
                )

                head_repo: Repository = unwrap(self._pull_request.head.repo)
                await fetch_config_from_github(
                    rest_api,
                    self.org_id,
                    head_repo.owner.login,
                    head_repo.name,
                    head_file,
                    # the commit status is set on this commit, a later push to the branch is validated on its own
                    self._pull_request.head.sha,
                )

            validation_result = ValidationResult()
            missing_changes_url = None

            for file in await self._get_pull_request_files(rest_api):
                self.logger.debug(f"touched file: {file}")
                if file != f"otterdog/{self.org_id}.jsonnet":
                    validation_result.touches_non_configuration = True
                    break

            if filecmp.cmp(base_file, head_file):
                self.logger.debug("head and base config are identical, no need to validate")
                validation_result.plan_output = "No changes."
                validation_result.validation_success = True
            else:
                if merge_commit is None:
                    missing_changes_url = await self._find_missing_configuration_changes(
                        rest_api, org_config.config_repo
                    )

                output = StringIO()
                printer = IndentingPrinter(output, log_level=self.log_level, output_for_github=True)
                # plan with the deletion policy of the apply of the dashboard, see ApplyChangesTask
                operation = LocalPlanOperation("-BASE", "*", False, False, False, "", delete_resources=True)

                otterdog_config = await get_otterdog_config()
                cost_policy = otterdog_config.cost_policy

                def callback(result: DiffResult):
                    patches = result.patches
                    validation_result.requires_secrets = any(x.requires_secrets() for x in patches)
                    validation_result.requires_web_ui = any(x.requires_web_ui() for x in patches)
                    validation_result.cost_related = any(x.is_cost_related(cost_policy) for x in patches)

                    validation_result.includes_deletions = any(x.patch_type == LivePatchType.REMOVE for x in patches)

                operation.set_callback(callback)
                operation.init(otterdog_config, printer)

                try:
                    # confine jsonnet imports to the org config directory so that
                    # configurations cannot reach files outside the expected vendor layout.
                    with restrict_jsonnet_imports(org_config.jsonnet_config.org_dir):
                        plan_result = await operation.execute(org_config)
                    validation_result.plan_output = output.getvalue()
                    validation_result.validation_success = plan_result == 0
                except Exception as ex:
                    self.logger.exception("exception during validate", exc_info=ex)

                    # use a friendly user-facing message rather than the raw evaluator
                    # output; full diagnostics stay in the server log.
                    validation_result.plan_output = (
                        "Validation failed while evaluating the configuration. "
                        "Please contact an admin if you believe this is incorrect."
                    )
                    validation_result.validation_success = False

                self.logger.info("local plan:" + validation_result.plan_output)

            warnings = []
            if validation_result.requires_secrets:
                warnings.append("some of the requested changes require secrets, need to apply these changes manually")
            if validation_result.requires_web_ui:
                warnings.append(
                    "some of the requested changes require accessing the Web UI, need to apply these changes manually"
                )
            if validation_result.cost_related:
                # Cost changes need review even when the change itself is API-applicable.
                warnings.append("some of the requested changes may incur costs, need review by the designated team")

            comment = await render_template(
                "comment/validation_comment.txt",
                sha=self._pull_request.head.sha,
                merged_into=merge_commit.base_sha if merge_commit is not None else None,
                result=escape_for_github(validation_result.plan_output),
                missing_changes_url=missing_changes_url,
                warnings=warnings,
                auto_merge_blockers=validation_result.auto_merge_blockers(),
                admin_teams=await get_full_admin_team_slugs(self.org_id),
            )

            await self.minimize_outdated_comments(
                self.org_id,
                self.repo_name,
                self.pull_request_number,
                "<!-- Otterdog Comment: validate -->",
            )

            # add a comment about the validation result to the PR
            rest_api = await self.rest_api
            await rest_api.issue.create_comment(
                self.org_id,
                self.repo_name,
                str(self.pull_request_number),
                comment,
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

        pull_request_model = await update_or_create_pull_request(
            self.org_id,
            self.repo_name,
            self._pull_request,
            valid=validation_result.validation_success,
            requires_manual_apply=(validation_result.requires_secrets or validation_result.requires_web_ui),
            supports_auto_merge=validation_result.supports_auto_merge,
        )

        if await pull_request_model.can_be_automerged():
            self.logger.info(
                "pull request #%d of repo '%s/%s' can be automerged, scheduling automerge task",
                self.pull_request_number,
                self.org_id,
                self.repo_name,
            )
            self.schedule_automerge_task(self.org_id, self.repo_name, self.pull_request_number)

    async def _find_merge_commit(self, rest_api: RestApi) -> _MergeCommit | None:
        """
        Returns the commit merging the head of the pull request into the default branch, as created by GitHub
        to test the mergeability of the pull request, None if there is none, e.g. in case of conflicts.

        GitHub creates it in the background once the pull request or its base branch changed: until then,
        the pull request is not known to be mergeable or still refers to the previous merge commit.
        """
        if self._pull_request.base.ref != unwrap(self._pull_request.base.repo).default_branch:
            # only the merges into the default branch are applied
            return None

        head_sha = self._pull_request.head.sha

        try:
            for delay in (*_MERGE_COMMIT_RETRY_DELAYS, None):
                pull_request = await rest_api.pull_request.get_pull_request(
                    self.org_id,
                    self.repo_name,
                    str(self.pull_request_number),
                )

                if pull_request["head"]["sha"] != head_sha:
                    # GitHub only tests the merge of the latest commit, which is validated on its own
                    break

                mergeable = pull_request.get("mergeable")
                if mergeable is False:
                    break

                merge_commit_sha = pull_request.get("merge_commit_sha")
                if mergeable is True and merge_commit_sha is not None:
                    commit = await rest_api.commit.get_commit(self.org_id, self.repo_name, merge_commit_sha)
                    parents = [parent["sha"] for parent in commit["parents"]]
                    if len(parents) == 2 and parents[1] == head_sha:
                        self.logger.info(
                            "validating merge commit '%s' of pull request #%d of repo '%s/%s'",
                            merge_commit_sha,
                            self.pull_request_number,
                            self.org_id,
                            self.repo_name,
                        )
                        return _MergeCommit(merge_commit_sha, parents[0])

                if delay is not None:
                    await asyncio.sleep(delay)
        except RuntimeError as ex:
            self.logger.warning(
                "failed retrieving the merge commit of pull request #%d of repo '%s/%s': %s",
                self.pull_request_number,
                self.org_id,
                self.repo_name,
                ex,
            )

        self.logger.info(
            "no merge commit available for pull request #%d of repo '%s/%s', validating its head",
            self.pull_request_number,
            self.org_id,
            self.repo_name,
        )
        return None

    async def _find_missing_configuration_changes(self, rest_api: RestApi, config_repo: str) -> str | None:
        """
        Returns the url of the changes made to the configuration on the default branch since the branch
        of the pull request has been created, None if the branch already contains all of them.

        Without merge commit, the head of the pull request is validated against the head of the default
        branch, so such changes show up in the diff as being reverted by the pull request, although merging
        it keeps them. They can even prevent auto-merging, e.g. when they changed a secret.
        """
        default_branch = unwrap(self._pull_request.base.repo).default_branch

        try:
            comparison = await rest_api.commit.compare_commits(
                self.org_id,
                config_repo,
                self._pull_request.head.sha,
                default_branch,
            )
        except RuntimeError as ex:
            # this only explains the diff, do not fail the validation because of it
            self.logger.warning(
                "failed checking whether pull request #%d of repo '%s/%s' is up-to-date: %s",
                self.pull_request_number,
                self.org_id,
                self.repo_name,
                ex,
            )
            return None

        config_path = f"otterdog/{self.org_id}.jsonnet"
        if any(file["filename"] == config_path for file in comparison.get("files", [])):
            return comparison["html_url"]

        return None

    async def _get_pull_request_files(self, rest_api: RestApi) -> list[str]:
        pull_request_data = await rest_api.pull_request.get_files(
            self.org_id,
            self.repo_name,
            str(self.pull_request_number),
        )
        return [x["filename"] for x in pull_request_data]

    def __repr__(self) -> str:
        return (
            f"ValidatePullRequestTask(repo='{self.org_id}/{self.repo_name}', pull_request=#{self.pull_request_number})"
        )


def _get_webhook_validation_context() -> str:
    return current_app.config["GITHUB_WEBHOOK_VALIDATION_CONTEXT"]
