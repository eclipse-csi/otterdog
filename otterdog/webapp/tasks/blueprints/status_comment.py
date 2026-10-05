#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quart import render_template

from otterdog.webapp.blueprints import create_blueprint_from_model
from otterdog.webapp.db.models import BlueprintStatus, TaskModel
from otterdog.webapp.db.service import (
    find_blueprint_status,
    get_blueprints_for_command,
    get_configuration_by_github_id,
    get_installation,
)
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import get_base_url

if TYPE_CHECKING:
    from otterdog.providers.github.rest import RestApi
    from otterdog.webapp.blueprints import Blueprint
    from otterdog.webapp.db.models import ConfigurationModel

STATUS_COMMENT_HEADER = "<!-- Otterdog Comment: blueprint-status"


@dataclass
class JobLabel:
    """One label per job: `workflow / job: <status>`, the status being GitHub's own value."""

    workflow: str
    job: str
    status: str
    url: str | None = None

    @property
    def text(self) -> str:
        return f"{self.workflow} / {self.job}: {self.status}"


@dataclass
class RepoStatusRow:
    repo_name: str
    repo_url: str
    status: str
    checked_at: str | None = None
    pull_request: int | None = None
    pull_request_url: str | None = None
    pull_request_state: str | None = None
    mergeable_state: str | None = None
    labels: list[str] = field(default_factory=list)
    outdated: bool = False
    jobs: list[JobLabel] = field(default_factory=list)


@dataclass
class BlueprintStatusReport:
    blueprint_id: str
    blueprint_name: str | None
    blueprint_url: str
    rows: list[RepoStatusRow] = field(default_factory=list)


@dataclass
class StatusResult:
    reports: list[BlueprintStatusReport] = field(default_factory=list)
    unknown_blueprint_id: str | None = None
    known_blueprint_ids: list[str] = field(default_factory=list)
    permission_denied: bool = False
    workflow_filter: str | None = None
    label_filter: str | None = None
    status_filter: str | None = None


def job_status(job: dict[str, Any]) -> str:
    """GitHub's own value: the conclusion of a completed job, otherwise its status."""
    if job.get("status") == "completed" and job.get("conclusion"):
        return job["conclusion"]
    return job.get("status") or "unknown"


def workflow_matches(workflow: dict[str, Any], selector: str) -> bool:
    """A selector matches a workflow by file name (with or without extension) or by its name."""
    path = workflow.get("path") or ""
    file_name = path.rsplit("/", 1)[-1]
    stem = file_name.rsplit(".", 1)[0]
    return selector in (file_name, stem, workflow.get("name"))


def select_workflows(workflows: list[dict[str, Any]], selectors: list[str]) -> list[dict[str, Any]]:
    """Resolves selectors to workflows; an empty selection means every workflow of the repository."""
    if len(selectors) == 0:
        return list(workflows)
    return [w for w in workflows if any(workflow_matches(w, s) for s in selectors)]


def resolve_workflow_selectors(blueprint: Blueprint, workflow_option: str | None) -> list[str]:
    """
    Which workflows `/otterdog status` reports, first match wins:

    1. `--workflow <name>` on the command
    2. `status_workflow` in the blueprint config
    3. the workflows the blueprint itself manages
    4. nothing: every workflow of the repository
    """
    if workflow_option is not None:
        return [workflow_option]
    if len(blueprint.status_workflows) > 0:
        return blueprint.status_workflows
    return blueprint.managed_workflows()


@dataclass(repr=False)
class BlueprintStatusCommentTask(InstallationBasedTask, Task[StatusResult]):
    """
    Answers `/otterdog status [<blueprint-id>] [--workflow <name>] [--label <label>] [--status <status>]`
    with one comment that is updated in place on repeated runs.
    """

    installation_id: int
    org_id: str
    repo_name: str
    issue_number: int
    author: str
    blueprint_id: str | None = None
    workflow: str | None = None
    label: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        self._default_branches: dict[str, str] = {}
        self._workflows: dict[str, list[dict[str, Any]]] = {}
        self._latest_runs: dict[str, dict[int, dict[str, Any] | None]] = {}
        self._jobs_by_run: dict[tuple[str, int], list[dict[str, Any]]] = {}

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.issue_number,
        )

    @property
    def comment_header(self) -> str:
        return f"{STATUS_COMMENT_HEADER}:{self.blueprint_id or 'all'} -->"

    async def _execute(self) -> StatusResult:
        self.logger.info(
            "status of blueprint(s) '%s' requested by '%s' in '%s/%s#%d'",
            self.blueprint_id or "*",
            self.author,
            self.org_id,
            self.repo_name,
            self.issue_number,
        )

        result = StatusResult(workflow_filter=self.workflow, label_filter=self.label, status_filter=self.status)

        if not await self.has_write_access(self.org_id, self.repo_name, self.author):
            result.permission_denied = True
            await self._reply(result)
            return result

        blueprint_models, result.known_blueprint_ids = await get_blueprints_for_command(self.org_id, self.blueprint_id)
        if self.blueprint_id is not None and len(blueprint_models) == 0:
            result.unknown_blueprint_id = self.blueprint_id
            await self._reply(result)
            return result

        installation = await get_installation(self.installation_id)
        config_model = await get_configuration_by_github_id(self.org_id)
        if installation is None or config_model is None:
            raise RuntimeError(f"no installation or configuration found for org '{self.org_id}'")

        is_config_repo = installation.config_repo == self.repo_name

        await self.create_or_update_comment(
            self.org_id,
            self.repo_name,
            self.issue_number,
            self.comment_header,
            f"{self.comment_header}\nCollecting the blueprint status, this comment is updated when done.",
        )

        for model in blueprint_models:
            blueprint = create_blueprint_from_model(model)
            repos = await self._repositories_to_report(blueprint, config_model, is_config_repo)
            result.reports.append(await self._report(blueprint, repos))

        await self._reply(result)
        return result

    async def _repositories_to_report(
        self, blueprint: Blueprint, config_model: ConfigurationModel, is_config_repo: bool
    ) -> list[str]:
        if is_config_repo:
            return await blueprint.matching_repositories(config_model)
        return [self.repo_name] if blueprint.matches_repo_name(config_model, self.repo_name) else []

    async def _report(self, blueprint: Blueprint, repos: list[str]) -> BlueprintStatusReport:
        rest_api = await self.rest_api
        report = BlueprintStatusReport(blueprint.id, blueprint.name, blueprint.path)
        selectors = resolve_workflow_selectors(blueprint, self.workflow)

        for repo_name in repos:
            row = await self._collect_row(rest_api, blueprint, repo_name, selectors)
            if self._passes_filters(row):
                report.rows.append(row)

        return report

    def _passes_filters(self, row: RepoStatusRow) -> bool:
        if self.label is not None and self.label not in row.labels:
            return False
        if self.status is not None and not any(job.status == self.status for job in row.jobs):
            return False
        return True

    async def _collect_row(
        self,
        rest_api: RestApi,
        blueprint: Blueprint,
        repo_name: str,
        selectors: list[str],
    ) -> RepoStatusRow:
        row = RepoStatusRow(
            repo_name=repo_name,
            repo_url=f"https://github.com/{self.org_id}/{repo_name}",
            status=BlueprintStatus.NOT_CHECKED.value,
        )

        status_model = await find_blueprint_status(self.org_id, repo_name, blueprint.id)
        if status_model is not None:
            row.status = status_model.status.value
            row.checked_at = status_model.updated_at.strftime("%Y-%m-%d %H:%M")
            row.pull_request = status_model.remediation_pr
            if status_model.remediation_pr is not None:
                await self._collect_pull_request(rest_api, row, repo_name, status_model.remediation_pr)
                row.outdated = (
                    status_model.remediation_revision is not None
                    and status_model.remediation_revision != blueprint.revision
                )

        try:
            row.jobs = await self._collect_jobs(rest_api, repo_name, selectors)
        except RuntimeError as ex:
            self.logger.warning(f"failed to collect workflow runs of '{self.org_id}/{repo_name}'", exc_info=ex)

        return row

    async def _collect_pull_request(self, rest_api: RestApi, row: RepoStatusRow, repo_name: str, number: int) -> None:
        try:
            pull_request = await rest_api.pull_request.get_pull_request(self.org_id, repo_name, str(number))
        except RuntimeError as ex:
            self.logger.warning(
                f"failed to retrieve pull request #{number} of '{self.org_id}/{repo_name}'", exc_info=ex
            )
            return

        row.pull_request_url = pull_request.get("html_url")
        if pull_request.get("merged_at") is not None:
            row.pull_request_state = "merged"
        else:
            row.pull_request_state = pull_request.get("state")
        row.mergeable_state = pull_request.get("mergeable_state")
        row.labels = sorted(label["name"] for label in pull_request.get("labels", []))

    async def _default_branch(self, rest_api: RestApi, repo_name: str) -> str:
        if repo_name not in self._default_branches:
            self._default_branches[repo_name] = await rest_api.repo.get_default_branch(self.org_id, repo_name)
        return self._default_branches[repo_name]

    async def _repo_workflows(self, rest_api: RestApi, repo_name: str) -> list[dict[str, Any]]:
        if repo_name not in self._workflows:
            workflows = await rest_api.action.get_workflows(self.org_id, repo_name)
            # dynamic workflows like pages-build-deployment have no file in .github/workflows
            self._workflows[repo_name] = [w for w in workflows if (w.get("path") or "").startswith(".github/")]
        return self._workflows[repo_name]

    async def _latest_run_per_workflow(self, rest_api: RestApi, repo_name: str) -> dict[int, dict[str, Any] | None]:
        if repo_name not in self._latest_runs:
            default_branch = await self._default_branch(rest_api, repo_name)
            runs = await rest_api.action.get_workflow_runs(self.org_id, repo_name, branch=default_branch)
            latest: dict[int, dict[str, Any] | None] = {}
            # runs are returned newest first, keep the first one per workflow
            for run in runs:
                latest.setdefault(run["workflow_id"], run)
            self._latest_runs[repo_name] = latest
        return self._latest_runs[repo_name]

    async def _latest_run_of_workflow(
        self, rest_api: RestApi, repo_name: str, workflow_id: int
    ) -> dict[str, Any] | None:
        latest_runs = self._latest_runs.setdefault(repo_name, {})
        if workflow_id not in latest_runs:
            default_branch = await self._default_branch(rest_api, repo_name)
            runs = await rest_api.action.get_workflow_runs(
                self.org_id, repo_name, branch=default_branch, per_page=1, workflow_id=workflow_id
            )
            # cache a miss as well, so the lookup happens once per workflow
            latest_runs[workflow_id] = runs[0] if len(runs) > 0 else None
        return latest_runs.get(workflow_id)

    async def _jobs(self, rest_api: RestApi, repo_name: str, run_id: int) -> list[dict[str, Any]]:
        key = (repo_name, run_id)
        if key not in self._jobs_by_run:
            self._jobs_by_run[key] = await rest_api.action.get_workflow_run_jobs(self.org_id, repo_name, run_id)
        return self._jobs_by_run[key]

    async def _collect_jobs(self, rest_api: RestApi, repo_name: str, selectors: list[str]) -> list[JobLabel]:
        workflows = select_workflows(await self._repo_workflows(rest_api, repo_name), selectors)
        if len(workflows) == 0:
            return []

        latest_runs = await self._latest_run_per_workflow(rest_api, repo_name)

        labels: list[JobLabel] = []
        for workflow in workflows:
            workflow_name = workflow.get("name") or workflow["path"].rsplit("/", 1)[-1]
            run = latest_runs.get(workflow["id"])
            if run is None:
                # a rarely running workflow might not be on the first page of runs, ask for it explicitly
                run = await self._latest_run_of_workflow(rest_api, repo_name, workflow["id"])
            if run is None:
                labels.append(JobLabel(workflow_name, "*", "no_run", workflow.get("html_url")))
                continue

            jobs = await self._jobs(rest_api, repo_name, run["id"])
            if len(jobs) == 0:
                labels.append(JobLabel(workflow_name, "*", job_status(run), run.get("html_url")))
            for job in jobs:
                labels.append(JobLabel(workflow_name, job["name"], job_status(job), job.get("html_url")))

        return labels

    async def _post_execute(self, result_or_exception: StatusResult | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            error = str(result_or_exception).strip().splitlines()[0] if str(result_or_exception).strip() else ""
            try:
                # replace the "collecting" placeholder, if it was posted already
                await self.create_or_update_comment(
                    self.org_id,
                    self.repo_name,
                    self.issue_number,
                    self.comment_header,
                    f"{self.comment_header}\n@{self.author} `/otterdog status` failed with an unexpected error: "
                    f"`{error or type(result_or_exception).__name__}`. "
                    "An administrator can find the details in the otterdog logs.",
                )
            except Exception as ex:
                self.logger.warning(f"failed to report the failure of '{self!r}'", exc_info=ex)

    async def _reply(self, result: StatusResult) -> None:
        comment = await render_template(
            "comment/blueprint_status_comment.txt",
            header=self.comment_header,
            result=result,
            author=self.author,
            org_id=self.org_id,
            repo_name=self.repo_name,
            dashboard_url=f"{get_base_url()}/organizations/{self.org_id}",
        )

        await self.create_or_update_comment(
            self.org_id, self.repo_name, self.issue_number, self.comment_header, comment
        )

    def __repr__(self) -> str:
        return (
            f"BlueprintStatusCommentTask(repo='{self.org_id}/{self.repo_name}', "
            f"issue={self.issue_number}, blueprint='{self.blueprint_id}')"
        )
