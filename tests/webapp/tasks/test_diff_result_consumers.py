#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pretend

from otterdog.models import CostPolicy, LivePatchType
from otterdog.models.repository import Repository
from otterdog.operations.diff_operation import DiffResult, DiffStatus
from otterdog.operations.validate import ValidationStatus

# imported through the webhook package, as importing the task first runs into an import cycle
from otterdog.webapp.webhook import CheckConfigurationInSyncTask, ValidatePullRequestTask  # isort: skip
from otterdog.webapp.tasks.auto_merge_comment import LEGACY_AUTO_MERGE_COMMENT_HEADER
from otterdog.webapp.tasks.validate_pull_request import ValidationResult


def _operation_factory(result: DiffResult, operation_name: str):
    """
    Create an operation double that reports one predetermined public result.
    """

    def create_operation(*args, **kwargs):
        operation = SimpleNamespace(gh_client=pretend.stub())
        create_operation.operations.append(operation)

        def set_callback(callback):
            operation.callback = callback

        def init(*args, **kwargs):
            return None

        async def execute(org_config):
            operation.callback(result)
            return 0

        operation.set_callback = set_callback
        operation.init = init
        operation.execute = execute
        return operation

    create_operation.__name__ = operation_name
    create_operation.operations = []
    return create_operation


def _organization_config(tmp_path: Path):
    return pretend.stub(
        config_repo=".config",
        jsonnet_config=pretend.stub(
            org_config_file=str(tmp_path / "test-org.jsonnet"),
            org_dir=str(tmp_path),
        ),
    )


def _prepare_task(task, monkeypatch, org_config, rest_api):
    """
    Run the task through its public lifecycle without database or network side effects.
    """

    @asynccontextmanager
    async def get_organization_config():
        yield org_config

    monkeypatch.setattr(task, "get_organization_config", get_organization_config)
    monkeypatch.setattr(task, "create_task_model", lambda: None)
    monkeypatch.setattr(task, "_pre_execute", AsyncMock(return_value=True))
    monkeypatch.setattr(task, "_post_execute", AsyncMock())
    monkeypatch.setattr(task, "_cleanup", AsyncMock())
    monkeypatch.setattr(task, "minimize_outdated_comments", AsyncMock())
    monkeypatch.setattr(task, "merge_statistics_from_provider", lambda provider: None)
    monkeypatch.setattr(
        "otterdog.webapp.tasks.get_rest_api_for_installation",
        AsyncMock(return_value=rest_api),
    )


async def _execute_check_sync_task(monkeypatch, tmp_path, result, app):
    rest_api = pretend.stub(issue=pretend.stub(create_comment=AsyncMock()))
    org_config = _organization_config(tmp_path)
    task = CheckConfigurationInSyncTask(1, "test-org", "repo", 42)
    _prepare_task(task, monkeypatch, org_config, rest_api)

    plan_operation = _operation_factory(result, "PlanOperation")
    monkeypatch.setattr("otterdog.webapp.tasks.check_sync.PlanOperation", plan_operation)
    monkeypatch.setattr(
        "otterdog.webapp.tasks.check_sync.fetch_config_from_github",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "otterdog.webapp.tasks.check_sync.get_otterdog_config",
        AsyncMock(return_value=pretend.stub()),
    )
    monkeypatch.setattr(
        "otterdog.webapp.tasks.check_sync.render_template",
        AsyncMock(return_value="out-of-sync comment"),
    )
    monkeypatch.setattr(
        "otterdog.webapp.tasks.check_sync.get_full_admin_team_slugs",
        AsyncMock(return_value=[]),
    )

    async with app.app_context():
        task_result = await task.execute()

    return task_result, rest_api, plan_operation.operations


async def test_check_sync_task_reports_out_of_sync_result_from_plan(monkeypatch, tmp_path, app):
    """
    The sync-check task turns a plan with changes into an out-of-sync result and a comment.
    """
    diff_status = DiffStatus()
    diff_status.additions = 1
    result = DiffResult("test-org", diff_status, ValidationStatus(), [object()])
    task_result, rest_api, _ = await _execute_check_sync_task(monkeypatch, tmp_path, result, app)

    assert task_result is False
    rest_api.issue.create_comment.assert_awaited_once()


async def test_check_sync_reports_managed_team_permission_removal_as_drift(monkeypatch, tmp_path, repository_test, app):
    """
    A still-present GitHub permission makes the sync check report drift when configuration removes its team.
    """
    expected = Repository.from_model_data(repository_test.model_data)
    current = Repository.from_model_data(repository_test.model_data)
    expected.set_team_permissions({"committers": "push"})
    current.set_team_permissions({"committers": "push", "contributors": "push"})
    changes = expected.get_difference_from(current)
    assert "team_permissions" in changes

    diff_status = DiffStatus()
    diff_status.differences = len(changes)
    result = DiffResult("test-org", diff_status, ValidationStatus(), [object()])
    task_result, rest_api, _ = await _execute_check_sync_task(monkeypatch, tmp_path, result, app)

    assert task_result is False
    rest_api.issue.create_comment.assert_awaited_once()


async def test_check_sync_limits_the_concurrent_requests_by_its_setting(monkeypatch, tmp_path, app):
    app.config["CHECK_SYNC_MAX_CONCURRENT_REQUESTS"] = 7
    result = DiffResult("test-org", DiffStatus(), ValidationStatus(), [])

    _, _, operations = await _execute_check_sync_task(monkeypatch, tmp_path, result, app)

    assert [operation.concurrency for operation in operations] == [7]


_NO_MISSING_CHANGES = {"behind_by": 0, "files": [], "html_url": "https://github.com/test-org/repo/compare/x...main"}


# GitHub found conflicts, the pull request has no merge commit
_CONFLICTING_PULL_REQUEST = {"head": {"sha": "head-sha"}, "mergeable": False, "merge_commit_sha": None}


async def _execute_validate_task(
    monkeypatch,
    tmp_path,
    result,
    compare_commits,
    pull_request=_CONFLICTING_PULL_REQUEST,
    merge_commit_parents=None,
):
    rest_api = pretend.stub(
        issue=pretend.stub(create_comment=AsyncMock(return_value={"node_id": "IC_validation"})),
        pull_request=pretend.stub(get_pull_request=AsyncMock(return_value=pull_request)),
        commit=pretend.stub(
            compare_commits=compare_commits,
            get_commit=AsyncMock(return_value={"parents": [{"sha": sha} for sha in merge_commit_parents or []]}),
        ),
    )
    org_config = _organization_config(tmp_path)
    task = ValidatePullRequestTask(1, "test-org", "repo", 42)
    task._pull_request = SimpleNamespace(
        head=SimpleNamespace(
            repo=SimpleNamespace(owner=SimpleNamespace(login="contributor"), name="repo"),
            ref="feature",
            sha="head-sha",
        ),
        base=SimpleNamespace(ref="main", repo=SimpleNamespace(default_branch="main")),
    )
    _prepare_task(task, monkeypatch, org_config, rest_api)
    monkeypatch.setattr("otterdog.webapp.tasks.validate_pull_request._MERGE_COMMIT_RETRY_DELAYS", ())

    fetched_configs = []

    async def fetch_config(_rest_api, _org_id, owner, repo, filename, ref=None):
        is_base = filename.endswith("-BASE")
        fetched_configs.append(("BASE" if is_base else "HEAD", owner, repo, ref))
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        Path(filename).write_text("base" if is_base else "head", encoding="utf-8")

    task._get_pull_request_files = AsyncMock(return_value=["otterdog/test-org.jsonnet"])
    monkeypatch.setattr(
        "otterdog.webapp.tasks.validate_pull_request.LocalPlanOperation",
        _operation_factory(result, "LocalPlanOperation"),
    )
    monkeypatch.setattr("otterdog.webapp.tasks.validate_pull_request.fetch_config_from_github", fetch_config)
    monkeypatch.setattr(
        "otterdog.webapp.tasks.validate_pull_request.get_otterdog_config",
        AsyncMock(return_value=pretend.stub(cost_policy=CostPolicy())),
    )
    render_template = AsyncMock(return_value="validation comment")
    monkeypatch.setattr("otterdog.webapp.tasks.validate_pull_request.render_template", render_template)
    monkeypatch.setattr(
        "otterdog.webapp.tasks.validate_pull_request.get_full_admin_team_slugs",
        AsyncMock(return_value=[]),
    )

    validation_result = await task.execute()
    rest_api.fetched_configs = fetched_configs
    rest_api.task = task

    return validation_result, rest_api, render_template


async def test_validate_pull_request_task_exposes_patch_safety_flags(monkeypatch, tmp_path):
    """
    PR validation exposes safety flags derived from the patches in the plan result.
    """
    patch = pretend.stub(
        requires_secrets=lambda: True,
        requires_web_ui=lambda: False,
        is_cost_related=lambda cost_policy: True,
        patch_type=LivePatchType.REMOVE,
    )
    result = DiffResult("test-org", DiffStatus(), ValidationStatus(), [patch])

    validation_result, rest_api, render_template = await _execute_validate_task(
        monkeypatch, tmp_path, result, AsyncMock(return_value=_NO_MISSING_CHANGES)
    )

    assert validation_result.validation_success is True
    assert validation_result.requires_secrets is True
    assert validation_result.requires_web_ui is False
    assert validation_result.cost_related is True
    assert validation_result.includes_deletions is True
    assert validation_result.supports_auto_merge is False
    assert render_template.await_args.kwargs["auto_merge_blockers"] == [
        "some of the requested changes require secrets",
        "some of the requested changes may incur costs",
        "some of the requested changes remove resources",
    ]
    assert render_template.await_args.kwargs["missing_changes_url"] is None
    rest_api.issue.create_comment.assert_awaited_once()


async def test_validate_pull_request_task_records_its_comment(monkeypatch, tmp_path):
    result = DiffResult("test-org", DiffStatus(), ValidationStatus(), [])

    _, rest_api, _ = await _execute_validate_task(
        monkeypatch, tmp_path, result, AsyncMock(return_value=_NO_MISSING_CHANGES)
    )

    task = rest_api.task
    # the comment shows whether the pull request can be auto-merged, see AutoMergeCommentTask
    assert task._comment_id == "IC_validation"
    # it replaces the comment of the previous validation, and the separate comment of previous versions
    task.minimize_outdated_comments.assert_awaited_once_with(
        "test-org", "repo", 42, "<!-- Otterdog Comment: validate -->", LEGACY_AUTO_MERGE_COMMENT_HEADER
    )


async def test_validate_pull_request_task_detects_configuration_changes_missing_from_the_branch(monkeypatch, tmp_path):
    """
    A branch created before the configuration changed on the default branch shows these changes as reverted.
    """
    result = DiffResult("test-org", DiffStatus(), ValidationStatus(), [])
    compare_commits = AsyncMock(
        return_value={
            "behind_by": 1,
            "files": [{"filename": "README.md"}, {"filename": "otterdog/test-org.jsonnet"}],
            "html_url": "https://github.com/test-org/.config/compare/head-sha...main",
        }
    )

    _, _, render_template = await _execute_validate_task(monkeypatch, tmp_path, result, compare_commits)

    # what the default branch has that the pull request has not
    compare_commits.assert_awaited_once_with("test-org", ".config", "head-sha", "main")
    assert (
        render_template.await_args.kwargs["missing_changes_url"]
        == "https://github.com/test-org/.config/compare/head-sha...main"
    )


async def test_validate_pull_request_task_ignores_missing_changes_to_other_files(monkeypatch, tmp_path):
    result = DiffResult("test-org", DiffStatus(), ValidationStatus(), [])
    compare_commits = AsyncMock(
        return_value={
            "behind_by": 1,
            "files": [{"filename": "README.md"}],
            "html_url": "https://github.com/test-org/.config/compare/head-sha...main",
        }
    )

    _, _, render_template = await _execute_validate_task(monkeypatch, tmp_path, result, compare_commits)

    assert render_template.await_args.kwargs["missing_changes_url"] is None


async def test_validate_pull_request_task_still_validates_when_the_comparison_fails(monkeypatch, tmp_path):
    result = DiffResult("test-org", DiffStatus(), ValidationStatus(), [])
    compare_commits = AsyncMock(side_effect=RuntimeError("failed comparing"))

    validation_result, rest_api, render_template = await _execute_validate_task(
        monkeypatch, tmp_path, result, compare_commits
    )

    assert validation_result.validation_success is True
    assert render_template.await_args.kwargs["missing_changes_url"] is None
    rest_api.issue.create_comment.assert_awaited_once()


async def test_validate_pull_request_task_validates_the_merge_commit(monkeypatch, tmp_path):
    """
    The validated diff is the one applied when merging, whether the branch is up-to-date or not.
    """
    result = DiffResult("test-org", DiffStatus(), ValidationStatus(), [])
    compare_commits = AsyncMock()

    validation_result, rest_api, render_template = await _execute_validate_task(
        monkeypatch,
        tmp_path,
        result,
        compare_commits,
        pull_request={"head": {"sha": "head-sha"}, "mergeable": True, "merge_commit_sha": "merge-sha"},
        merge_commit_parents=["base-sha", "head-sha"],
    )

    assert validation_result.validation_success is True
    assert rest_api.fetched_configs == [
        ("BASE", "test-org", ".config", "base-sha"),
        ("HEAD", "test-org", ".config", "merge-sha"),
    ]
    assert render_template.await_args.kwargs["merged_into"] == "base-sha"
    # the merge keeps the changes of the default branch, the diff does not revert them
    compare_commits.assert_not_awaited()
    assert render_template.await_args.kwargs["missing_changes_url"] is None


async def test_validate_pull_request_task_validates_the_head_without_merge_commit(monkeypatch, tmp_path):
    result = DiffResult("test-org", DiffStatus(), ValidationStatus(), [])

    _, rest_api, render_template = await _execute_validate_task(
        monkeypatch, tmp_path, result, AsyncMock(return_value=_NO_MISSING_CHANGES)
    )

    assert rest_api.fetched_configs == [
        # the head of the default branch
        ("BASE", "test-org", ".config", None),
        # the commit the status is set on, not the branch which may have moved since
        ("HEAD", "contributor", "repo", "head-sha"),
    ]
    assert render_template.await_args.kwargs["merged_into"] is None


async def test_validate_pull_request_task_records_the_validated_commit(monkeypatch):
    rest_api = pretend.stub(commit=pretend.stub(create_commit_status=AsyncMock()))
    task = ValidatePullRequestTask(1, "test-org", "repo", 42)
    task._pull_request = SimpleNamespace(head=SimpleNamespace(sha="head-sha"))
    task._comment_id = "IC_validation"
    task.schedule_automerge_task = Mock()
    update_or_create_pull_request = AsyncMock(
        return_value=pretend.stub(author_can_auto_merge=True, can_be_automerged=AsyncMock(return_value=False))
    )

    monkeypatch.setattr("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api))
    monkeypatch.setattr(
        "otterdog.webapp.tasks.validate_pull_request._get_webhook_validation_context", lambda: "otterdog-validate"
    )
    monkeypatch.setattr(
        "otterdog.webapp.tasks.validate_pull_request.update_or_create_pull_request", update_or_create_pull_request
    )

    await task._update_final_status(ValidationResult(validation_success=True))

    # a later push is validated on its own, the result must not count for it
    assert update_or_create_pull_request.await_args.kwargs.get("validated_sha") == "head-sha"
    assert update_or_create_pull_request.await_args.kwargs.get("validation_comment_id") == "IC_validation"
    # the auto-merge comment is added or hidden depending on the recorded result, here hidden
    task.schedule_automerge_task.assert_called_once_with("test-org", "repo", 42)
