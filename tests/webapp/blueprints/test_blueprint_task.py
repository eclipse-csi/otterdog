#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from otterdog.webapp.db.models import BlueprintStatus
from otterdog.webapp.tasks.blueprints import BlueprintTask, CheckResult


@dataclass(repr=False)
class DummyBlueprintTask(BlueprintTask):
    installation_id: int
    org_id: str
    repo_name: str
    blueprint: SimpleNamespace

    async def _execute(self) -> CheckResult:
        return CheckResult(remediation_needed=False)

    def __repr__(self) -> str:
        return "DummyBlueprintTask"


def _pr(number: int, state: str, merged: bool, created_at: str) -> dict:
    return {
        "number": number,
        "state": state,
        "merged_at": "2026-09-23T13:00:00Z" if merged else None,
        "created_at": created_at,
    }


@pytest.fixture
def task():
    return DummyBlueprintTask(1, "my-org", ".otterdog", SimpleNamespace(id="add-dot-github-repo"))


async def _pre_execute(task, stored_status, pull_requests):
    rest_api = MagicMock()
    rest_api.pull_request.get_pull_requests = AsyncMock(return_value=pull_requests)

    with (
        patch("otterdog.webapp.tasks.blueprints.find_blueprint_status", AsyncMock(return_value=stored_status)),
        patch("otterdog.webapp.tasks.blueprints.update_or_create_blueprint_status", AsyncMock()) as update_status,
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
    ):
        result = await task._pre_execute()

    return result, update_status, rest_api


async def test_skips_when_stored_status_is_dismissed(task):
    stored = SimpleNamespace(status=BlueprintStatus.DISMISSED)
    result, update_status, rest_api = await _pre_execute(task, stored, [])

    assert result is False
    update_status.assert_not_awaited()
    rest_api.pull_request.get_pull_requests.assert_not_awaited()


async def test_skips_and_restores_dismissed_status_when_pr_was_closed_without_merge(task):
    # the stored status got lost, but the remediation PR has been closed manually on GitHub
    result, update_status, rest_api = await _pre_execute(
        task, None, [_pr(12, "closed", merged=False, created_at="2026-09-23T12:50:06Z")]
    )

    assert result is False
    rest_api.pull_request.get_pull_requests.assert_awaited_once_with(
        "my-org", ".otterdog", "all", head_ref="otterdog/blueprint/add-dot-github-repo"
    )
    update_status.assert_awaited_once_with("my-org", ".otterdog", "add-dot-github-repo", BlueprintStatus.DISMISSED, 12)


@pytest.mark.parametrize(
    "pull_requests",
    [
        [],
        [_pr(12, "closed", merged=True, created_at="2026-09-23T12:50:06Z")],
        [_pr(13, "open", merged=False, created_at="2026-09-23T13:45:06Z")],
        # only the latest PR counts: a dismissed PR that got superseded by a merged one
        [
            _pr(12, "closed", merged=False, created_at="2026-09-23T12:50:06Z"),
            _pr(13, "closed", merged=True, created_at="2026-09-23T13:45:06Z"),
        ],
    ],
)
async def test_proceeds_when_no_pr_was_dismissed(task, pull_requests):
    stored = SimpleNamespace(status=BlueprintStatus.NOT_CHECKED)
    result, update_status, _ = await _pre_execute(task, stored, pull_requests)

    assert result is True
    update_status.assert_not_awaited()


async def test_skips_when_pull_requests_cannot_be_retrieved(task):
    rest_api = MagicMock()
    rest_api.pull_request.get_pull_requests = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch("otterdog.webapp.tasks.blueprints.find_blueprint_status", AsyncMock(return_value=None)),
        patch("otterdog.webapp.tasks.blueprints.update_or_create_blueprint_status", AsyncMock()) as update_status,
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
    ):
        assert await task._pre_execute() is False

    update_status.assert_not_awaited()
