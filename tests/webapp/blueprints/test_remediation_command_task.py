#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from otterdog.webapp.blueprints import read_blueprint
from otterdog.webapp.db.models import BlueprintId, BlueprintModel, BlueprintStatus
from otterdog.webapp.tasks.blueprints.remediation_command import (
    CommandOutcome,
    RemediationCommand,
    RemediationCommandTask,
)

BRANCH = "otterdog/blueprint/codeql"


def _model() -> BlueprintModel:
    blueprint = read_blueprint(
        "https://example.org/codeql.yml",
        {"id": "codeql", "type": "required_file", "config": {"files": [{"path": "x", "content": "y"}]}},
    )
    return BlueprintModel(
        id=BlueprintId(org_id="osgi", blueprint_type="required_file", blueprint_id="codeql"),
        path=blueprint.path,
        config=blueprint.config,
    )


def _pull_request(state: str = "open", head_ref: str = BRANCH) -> dict:
    return {"number": 5, "state": state, "head": {"ref": head_ref}, "base": {"ref": "main"}}


async def _run(
    command: RemediationCommand,
    pull_request: dict,
    stored_status=None,
    permission: str = "write",
    blueprint_model: BlueprintModel | None = "default",  # type: ignore[assignment]
    reopen_fails: bool = False,
):
    if blueprint_model == "default":
        blueprint_model = _model()
    task = RemediationCommandTask(1, "osgi", "org.osgi.annotation", 5, "alice", command)

    rest_api = MagicMock()
    rest_api.repo.get_collaborator_permission = AsyncMock(return_value=permission)
    rest_api.pull_request.get_pull_request = AsyncMock(return_value=pull_request)
    rest_api.pull_request.update_pull_request = AsyncMock(side_effect=RuntimeError("too old") if reopen_fails else None)
    rest_api.issue.create_comment = AsyncMock()

    module = "otterdog.webapp.tasks.blueprints.remediation_command"
    with (
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
        patch(f"{module}.find_blueprint", AsyncMock(return_value=blueprint_model)),
        patch(f"{module}.find_blueprint_status", AsyncMock(return_value=stored_status)),
        patch(f"{module}.get_configuration_by_github_id", AsyncMock(return_value=SimpleNamespace(config={}))),
        patch(f"{module}.update_or_create_blueprint_status", AsyncMock()) as update_status,
        patch(f"{module}.sync_branch_with_default_branch", AsyncMock(return_value=False)) as sync_branch,
        patch(f"{module}.reset_branch_to_default_branch", AsyncMock()) as reset_branch,
        patch(f"{module}.render_template", AsyncMock(return_value="reply")),
        patch(f"{module}.get_app_bot_login", AsyncMock(return_value="otterdog[bot]")),
        patch("otterdog.webapp.blueprints.required_file.RequiredFileBlueprint.evaluate_repo", AsyncMock()) as evaluate,
    ):
        result = await task._execute()

    rest_api.issue.create_comment.assert_awaited_once_with("osgi", "org.osgi.annotation", "5", "reply")
    return result, SimpleNamespace(
        rest_api=rest_api,
        update_status=update_status,
        sync_branch=sync_branch,
        reset_branch=reset_branch,
        evaluate=evaluate,
    )


async def test_read_access_is_rejected():
    result, mocks = await _run(RemediationCommand.REBASE, _pull_request(), permission="read")

    assert result.outcome == CommandOutcome.PERMISSION_DENIED
    mocks.evaluate.assert_not_awaited()


async def test_other_pull_requests_are_rejected():
    result, mocks = await _run(RemediationCommand.REBASE, _pull_request(head_ref="feature/x"))

    assert result.outcome == CommandOutcome.NOT_A_REMEDIATION_PR
    mocks.sync_branch.assert_not_awaited()


async def test_removed_blueprint_is_reported():
    result, _ = await _run(RemediationCommand.REBASE, _pull_request(), blueprint_model=None)

    assert result.outcome == CommandOutcome.UNKNOWN_BLUEPRINT
    assert result.blueprint_id == "codeql"


async def test_rebase_syncs_branch_and_reevaluates():
    result, mocks = await _run(RemediationCommand.REBASE, _pull_request())

    assert result.outcome == CommandOutcome.REBASED
    mocks.sync_branch.assert_awaited_once()
    assert mocks.sync_branch.await_args.args[1:5] == ("osgi", "org.osgi.annotation", BRANCH, "main")
    mocks.evaluate.assert_awaited_once()
    mocks.reset_branch.assert_not_awaited()


async def test_rebase_on_closed_pull_request_points_to_recreate():
    result, mocks = await _run(RemediationCommand.REBASE, _pull_request(state="closed"))

    assert result.outcome == CommandOutcome.DISMISSED
    mocks.sync_branch.assert_not_awaited()
    mocks.evaluate.assert_not_awaited()


async def test_recreate_on_open_pull_request_resets_branch_and_keeps_pr():
    result, mocks = await _run(RemediationCommand.RECREATE, _pull_request())

    assert result.outcome == CommandOutcome.RECREATED
    assert result.pull_request_reopened is False
    mocks.reset_branch.assert_awaited_once()
    mocks.rest_api.pull_request.update_pull_request.assert_not_awaited()
    mocks.update_status.assert_awaited_once_with("osgi", "org.osgi.annotation", "codeql", BlueprintStatus.RECHECK, 5)
    mocks.evaluate.assert_awaited_once()


async def test_recreate_on_dismissed_pull_request_reopens_it_and_clears_dismissal():
    # regression: closing a remediation PR dismissed the blueprint for good
    dismissed = SimpleNamespace(status=BlueprintStatus.DISMISSED, remediation_pr=5)
    result, mocks = await _run(RemediationCommand.RECREATE, _pull_request(state="closed"), stored_status=dismissed)

    assert result.outcome == CommandOutcome.RECREATED
    assert result.pull_request_reopened is True
    mocks.reset_branch.assert_awaited_once()
    mocks.rest_api.pull_request.update_pull_request.assert_awaited_once_with(
        "osgi", "org.osgi.annotation", 5, state="open"
    )
    mocks.update_status.assert_awaited_once_with("osgi", "org.osgi.annotation", "codeql", BlueprintStatus.RECHECK, 5)
    mocks.evaluate.assert_awaited_once()


async def test_recreate_detaches_status_when_reopening_fails():
    result, mocks = await _run(RemediationCommand.RECREATE, _pull_request(state="closed"), reopen_fails=True)

    assert result.outcome == CommandOutcome.RECREATED
    assert result.pull_request_reopened is False
    # the stored status no longer references the closed PR, so the evaluation creates a new one
    mocks.update_status.assert_awaited_once_with("osgi", "org.osgi.annotation", "codeql", BlueprintStatus.RECHECK, None)
    mocks.evaluate.assert_awaited_once()


async def test_ignore_dismisses_and_closes_pull_request():
    result, mocks = await _run(RemediationCommand.IGNORE, _pull_request())

    assert result.outcome == CommandOutcome.IGNORED
    mocks.update_status.assert_awaited_once_with("osgi", "org.osgi.annotation", "codeql", BlueprintStatus.DISMISSED, 5)
    mocks.rest_api.pull_request.update_pull_request.assert_awaited_once_with(
        "osgi", "org.osgi.annotation", 5, state="closed"
    )
    mocks.evaluate.assert_not_awaited()


async def test_ignore_on_dismissed_blueprint_is_a_no_op():
    dismissed = SimpleNamespace(status=BlueprintStatus.DISMISSED, remediation_pr=5)
    result, mocks = await _run(RemediationCommand.IGNORE, _pull_request(state="closed"), stored_status=dismissed)

    assert result.outcome == CommandOutcome.ALREADY_DISMISSED
    mocks.update_status.assert_not_awaited()
    mocks.rest_api.pull_request.update_pull_request.assert_not_awaited()
