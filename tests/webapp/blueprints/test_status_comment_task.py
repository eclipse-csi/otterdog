#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from otterdog.webapp.blueprints import read_blueprint
from otterdog.webapp.db.models import BlueprintId, BlueprintModel, BlueprintStatus
from otterdog.webapp.tasks.blueprints.status_comment import (
    BlueprintStatusCommentTask,
    job_status,
    resolve_workflow_selectors,
    select_workflows,
)

CONFIG_REPO = ".eclipsefdn"
MODULE = "otterdog.webapp.tasks.blueprints.status_comment"

WORKFLOWS = [
    {"id": 1, "name": "Build", "path": ".github/workflows/build.yml", "html_url": "https://wf/build"},
    {"id": 2, "name": "CodeQL", "path": ".github/workflows/codeql.yml", "html_url": "https://wf/codeql"},
    {"id": 3, "name": "pages build and deployment", "path": "dynamic/pages/pages-build-deployment"},
]


@pytest.mark.parametrize(
    "job, expected",
    [
        ({"status": "completed", "conclusion": "success"}, "success"),
        ({"status": "completed", "conclusion": "timed_out"}, "timed_out"),
        ({"status": "in_progress", "conclusion": None}, "in_progress"),
        ({"status": "queued"}, "queued"),
    ],
)
def test_job_status_is_githubs_own_value(job, expected):
    assert job_status(job) == expected


@pytest.mark.parametrize(
    "selectors, expected_ids",
    [
        ([], [1, 2, 3]),
        (["build.yml"], [1]),
        (["build"], [1]),
        (["CodeQL"], [2]),
        (["build", "codeql.yml"], [1, 2]),
        (["missing"], []),
    ],
)
def test_select_workflows(selectors, expected_ids):
    assert [w["id"] for w in select_workflows(WORKFLOWS, selectors)] == expected_ids


def _blueprint(blueprint_type: str = "required_file", **config):
    data = {"id": "codeql", "type": blueprint_type, "config": config}
    return read_blueprint("https://example.org/codeql.yml", data)


def test_workflow_selection_order():
    managed = _blueprint(files=[{"path": ".github/workflows/codeql.yml", "content": "x"}])
    assert resolve_workflow_selectors(managed, "build") == ["build"]
    assert resolve_workflow_selectors(managed, None) == ["codeql.yml"]

    configured = _blueprint(status_workflow=["build", "test"], files=[{"path": "README.md", "content": "x"}])
    assert resolve_workflow_selectors(configured, None) == ["build", "test"]

    nothing = _blueprint(files=[{"path": "README.md", "content": "x"}])
    assert resolve_workflow_selectors(nothing, None) == []

    scorecard = _blueprint("scorecard_integration", workflow_content="x")
    assert resolve_workflow_selectors(scorecard, None) == ["scorecard-analysis.yml"]


def _model(blueprint) -> BlueprintModel:
    return BlueprintModel(
        id=BlueprintId(org_id="osgi", blueprint_type=blueprint.type.value, blueprint_id=blueprint.id),
        path=blueprint.path,
        name="CodeQL",
        config=blueprint.config,
    )


def _organization(*repo_names: str) -> SimpleNamespace:
    repos = [SimpleNamespace(name=name, archived=False) for name in repo_names]
    return SimpleNamespace(
        repositories=repos,
        get_repository=lambda name: next((repo for repo in repos if repo.name == name), None),
    )


def _status(repo_name: str, status: BlueprintStatus, pr: int | None, revision: str | None):
    return SimpleNamespace(
        id=SimpleNamespace(repo_name=repo_name),
        status=status,
        remediation_pr=pr,
        remediation_revision=revision,
        updated_at=datetime(2026, 10, 1, 10, 0, tzinfo=UTC),
    )


async def _run(repo_name: str, blueprint_id: str | None = None, workflow=None, label=None, status=None):
    blueprint = _blueprint(
        repo_selector={"name_pattern": r"org\.osgi\..*"}, files=[{"path": "SECURITY.md", "content": "x"}]
    )
    task = BlueprintStatusCommentTask(1, "osgi", repo_name, 7, "alice", blueprint_id, workflow, label, status)

    statuses = {
        "org.osgi.annotation": _status("org.osgi.annotation", BlueprintStatus.REMEDIATION_PREPARED, 5, "old"),
        "org.osgi.framework": _status("org.osgi.framework", BlueprintStatus.SUCCESS, None, None),
    }

    rest_api = MagicMock()
    rest_api.repo.get_collaborator_permission = AsyncMock(return_value="write")
    rest_api.repo.get_default_branch = AsyncMock(return_value="main")
    rest_api.issue.get_comments = AsyncMock(return_value=[])
    rest_api.issue.create_comment = AsyncMock()
    rest_api.issue.update_comment = AsyncMock()
    rest_api.pull_request.get_pull_request = AsyncMock(
        return_value={
            "html_url": "https://github.com/osgi/org.osgi.annotation/pull/5",
            "state": "open",
            "merged_at": None,
            "mergeable_state": "dirty",
            "labels": [{"name": "otterdog"}, {"name": "blueprint:codeql"}],
        }
    )
    rest_api.action.get_workflows = AsyncMock(return_value=WORKFLOWS)

    async def get_workflow_runs(org, repo, branch=None, per_page=100, workflow_id=None):
        if workflow_id is None:
            return [
                {"id": 100, "workflow_id": 1, "html_url": "https://run/100"},
                {"id": 99, "workflow_id": 1, "html_url": "https://run/99"},  # older run of the same workflow
            ]
        # the explicit lookup for a workflow missing on the first page
        if workflow_id == 2:
            return [{"id": 50, "workflow_id": 2, "html_url": "https://run/50", "status": "queued"}]
        return []

    rest_api.action.get_workflow_runs = AsyncMock(side_effect=get_workflow_runs)
    rest_api.action.get_workflow_run_jobs = AsyncMock(
        return_value=[
            {"name": "linux", "status": "completed", "conclusion": "success", "html_url": "https://job/1"},
            {"name": "windows", "status": "completed", "conclusion": "failure", "html_url": "https://job/2"},
        ]
    )

    async def find_status(org, repo, bp_id):
        return statuses.get(repo)

    with (
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
        patch("otterdog.webapp.db.service.get_blueprints", AsyncMock(return_value=[_model(blueprint)])),
        patch(f"{MODULE}.get_installation", AsyncMock(return_value=SimpleNamespace(config_repo=CONFIG_REPO))),
        patch(f"{MODULE}.get_configuration_by_github_id", AsyncMock(return_value=SimpleNamespace(config={}))),
        patch(f"{MODULE}.find_blueprint_status", AsyncMock(side_effect=find_status)),
        patch(
            "otterdog.webapp.blueprints.GitHubOrganization.from_model_data",
            return_value=_organization("org.osgi.annotation", "org.osgi.framework", ".github"),
        ),
        patch(f"{MODULE}.render_template", AsyncMock(return_value="reply")),
        patch(f"{MODULE}.get_base_url", return_value="https://otterdog"),
    ):
        result = await task._execute()

    return result, rest_api


async def test_config_repo_reports_every_matching_repository():
    result, rest_api = await _run(CONFIG_REPO)

    assert len(result.reports) == 1
    rows = {row.repo_name: row for row in result.reports[0].rows}
    assert list(rows) == ["org.osgi.annotation", "org.osgi.framework"]

    annotation = rows["org.osgi.annotation"]
    assert annotation.status == "remediation_prepared"
    assert annotation.pull_request == 5
    assert annotation.mergeable_state == "dirty"
    assert annotation.labels == ["blueprint:codeql", "otterdog"]
    assert annotation.outdated is True  # stored revision "old" differs from the current one

    framework = rows["org.osgi.framework"]
    assert framework.pull_request is None
    assert framework.outdated is False

    # no workflow configured or managed: every workflow with a file, every job; the pages workflow is dropped
    assert [job.text for job in annotation.jobs] == [
        "Build / linux: success",
        "Build / windows: failure",
        "CodeQL / linux: success",
        "CodeQL / windows: failure",
    ]
    # the CodeQL run was not on the first page and was looked up explicitly, once per repository
    assert [c.kwargs.get("workflow_id") for c in rest_api.action.get_workflow_runs.await_args_list].count(2) == 2
    assert annotation.jobs[0].url == "https://job/1"

    # the first ("collecting") comment is created, the final one updates it in place
    assert rest_api.issue.create_comment.await_count + rest_api.issue.update_comment.await_count == 2


async def test_target_repo_reports_only_itself():
    result, _ = await _run("org.osgi.framework")

    assert [row.repo_name for row in result.reports[0].rows] == ["org.osgi.framework"]


async def test_workflow_option_narrows_jobs():
    result, rest_api = await _run(CONFIG_REPO, "codeql", workflow="build.yml")

    for row in result.reports[0].rows:
        assert {job.workflow for job in row.jobs} == {"Build"}
    # jobs of the latest Build run are fetched once per repository, CodeQL is not looked up at all
    assert rest_api.action.get_workflow_run_jobs.await_count == 2
    assert all(c.kwargs.get("workflow_id") is None for c in rest_api.action.get_workflow_runs.await_args_list)


async def test_label_and_status_filters():
    result, _ = await _run(CONFIG_REPO, label="blueprint:codeql")
    assert [row.repo_name for row in result.reports[0].rows] == ["org.osgi.annotation"]

    result, _ = await _run(CONFIG_REPO, status="failure")
    assert [row.repo_name for row in result.reports[0].rows] == ["org.osgi.annotation", "org.osgi.framework"]

    result, _ = await _run(CONFIG_REPO, status="cancelled")
    assert result.reports[0].rows == []


async def test_unknown_blueprint_id_is_reported():
    result, _ = await _run(CONFIG_REPO, "nope")

    assert result.unknown_blueprint_id == "nope"
    assert result.known_blueprint_ids == ["codeql"]


async def test_unexpected_error_replaces_the_placeholder_comment():
    task = BlueprintStatusCommentTask(1, "osgi", "org.osgi.annotation", 7, "alice")

    rest_api = MagicMock()
    rest_api.repo.get_collaborator_permission = AsyncMock(side_effect=RuntimeError("boom"))
    rest_api.issue.get_comments = AsyncMock(
        return_value=[{"id": 11, "body": f"{task.comment_header}\nCollecting the blueprint status"}]
    )
    rest_api.issue.create_comment = AsyncMock()
    rest_api.issue.update_comment = AsyncMock()
    rest_api.close = AsyncMock()

    with (
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
        patch("otterdog.webapp.tasks.create_task", AsyncMock()),
        patch("otterdog.webapp.tasks.schedule_task", AsyncMock()),
        patch("otterdog.webapp.tasks.fail_task", AsyncMock()),
        patch("otterdog.webapp.tasks.finish_task", AsyncMock()),
    ):
        outcome = await task.execute()

    assert isinstance(outcome, RuntimeError)
    rest_api.issue.update_comment.assert_awaited_once()
    assert "failed with an unexpected error: `boom`" in rest_api.issue.update_comment.await_args.args[3]
    rest_api.issue.create_comment.assert_not_awaited()
