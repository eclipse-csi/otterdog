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
from unittest.mock import AsyncMock

import pretend

from otterdog.models import CostPolicy, LivePatchType
from otterdog.operations.diff_operation import DiffResult, DiffStatus
from otterdog.operations.validate import ValidationStatus
from otterdog.webapp.webhook import CheckConfigurationInSyncTask, ValidatePullRequestTask


def _operation_factory(result: DiffResult, operation_name: str):
    """
    Create an operation double that reports one predetermined public result.
    """

    def create_operation(*args, **kwargs):
        operation = SimpleNamespace(gh_client=pretend.stub())

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


async def test_check_sync_task_reports_out_of_sync_result_from_plan(monkeypatch, tmp_path):
    """
    The sync-check task turns a plan with changes into an out-of-sync result and a comment.
    """
    diff_status = DiffStatus()
    diff_status.additions = 1
    result = DiffResult("test-org", diff_status, ValidationStatus(), [object()])
    rest_api = pretend.stub(issue=pretend.stub(create_comment=AsyncMock()))
    org_config = _organization_config(tmp_path)
    task = CheckConfigurationInSyncTask(1, "test-org", "repo", 42)
    _prepare_task(task, monkeypatch, org_config, rest_api)

    monkeypatch.setattr(
        "otterdog.webapp.tasks.check_sync.PlanOperation",
        _operation_factory(result, "PlanOperation"),
    )
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

    task_result = await task.execute()

    assert task_result is False
    rest_api.issue.create_comment.assert_awaited_once()


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
    rest_api = pretend.stub(issue=pretend.stub(create_comment=AsyncMock()))
    org_config = _organization_config(tmp_path)
    task = ValidatePullRequestTask(1, "test-org", "repo", 42)
    task._pull_request = SimpleNamespace(
        head=SimpleNamespace(
            repo=SimpleNamespace(owner=SimpleNamespace(login="contributor"), name="repo"),
            ref="feature",
            sha="head-sha",
        )
    )
    _prepare_task(task, monkeypatch, org_config, rest_api)

    async def fetch_config(_rest_api, _org_id, _owner, _repo, filename, _ref=None):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        Path(filename).write_text("base" if filename.endswith("-BASE") else "head", encoding="utf-8")

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
    monkeypatch.setattr(
        "otterdog.webapp.tasks.validate_pull_request.render_template",
        AsyncMock(return_value="validation comment"),
    )
    monkeypatch.setattr(
        "otterdog.webapp.tasks.validate_pull_request.get_full_admin_team_slugs",
        AsyncMock(return_value=[]),
    )

    validation_result = await task.execute()

    assert validation_result.validation_success is True
    assert validation_result.requires_secrets is True
    assert validation_result.requires_web_ui is False
    assert validation_result.cost_related is True
    assert validation_result.includes_deletions is True
    rest_api.issue.create_comment.assert_awaited_once()
