#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from io import StringIO
from unittest.mock import patch

from otterdog.models import LivePatch
from otterdog.models.repository import Repository
from otterdog.operations.apply import ApplyOperation
from otterdog.operations.diff_operation import DiffStatus
from otterdog.operations.validate import ValidationStatus
from otterdog.utils import Change, IndentingPrinter, LogLevel


async def _succeed(_patch, _org_id, _provider):
    pass


async def _fail(_patch, _org_id, _provider):
    raise RuntimeError("name already exists on this account")


def _repo(name: str, description: str = "") -> Repository:
    return Repository.from_model_data({"name": name, "description": description})


async def _apply(patches: list[LivePatch], diff_status: DiffStatus):
    operation = ApplyOperation(
        force_processing=True,
        no_web_ui=True,
        repo_filter="*",
        update_webhooks=False,
        update_secrets=False,
        only_secrets=False,
        update_filter="",
        delete_resources=True,
    )
    output = StringIO()
    operation.init(None, IndentingPrinter(output, log_level=LogLevel.ERROR))  # type: ignore
    operation._gh_client = object()  # type: ignore
    operation._org_config = object()  # type: ignore

    with patch.object(operation, "execute_custom_hook_if_present_with_patches") as hook:
        errors = await operation.handle_finish("org", diff_status, ValidationStatus(), patches)

    return errors, output.getvalue(), hook


def _diff_status(additions: int, differences: int, deletions: int) -> DiffStatus:
    status = DiffStatus()
    status.additions = additions
    status.differences = differences
    status.deletions = deletions
    return status


async def test_apply_reports_only_applied_patches():
    created = LivePatch.of_addition(_repo("created"), None, _succeed)
    existing = LivePatch.of_addition(_repo("existing"), None, _fail)
    changed = LivePatch.of_changes(
        _repo("changed", "new"),
        _repo("changed", "old"),
        {"description": Change("old", "new")},
        None,
        False,
        _fail,
    )

    errors, output, _ = await _apply([created, existing, changed], _diff_status(2, 1, 0))

    assert errors == 2
    assert "Executed plan: 1 added, 0 changed, 0 deleted." in output
    assert "Failed: 1 to add, 1 to change, 0 to delete, see errors above." in output


async def test_apply_hook_only_receives_successful_additions():
    created = LivePatch.of_addition(_repo("created"), None, _succeed)
    existing = LivePatch.of_addition(_repo("existing"), None, _fail)

    _, _, hook = await _apply([created, existing], _diff_status(2, 0, 0))

    hook.assert_called_once()
    assert hook.call_args.args[1] == [created]


async def test_apply_hook_not_called_when_all_additions_fail():
    existing = LivePatch.of_addition(_repo("existing"), None, _fail)

    errors, output, hook = await _apply([existing], _diff_status(1, 0, 0))

    assert errors == 1
    assert "Executed plan: 0 added, 0 changed, 0 deleted." in output
    hook.assert_not_called()


async def test_apply_without_failures_does_not_report_failures():
    created = LivePatch.of_addition(_repo("created"), None, _succeed)

    errors, output, hook = await _apply([created], _diff_status(1, 0, 0))

    assert errors == 0
    assert "Executed plan: 1 added, 0 changed, 0 deleted." in output
    assert "Failed" not in output
    hook.assert_called_once()
