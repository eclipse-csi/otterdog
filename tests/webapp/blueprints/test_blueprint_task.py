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


def _commit(author_type: str | None) -> dict:
    return {"sha": "abc", "author": {"type": author_type} if author_type else None, "committer": None}


async def _sync(task, comparison: dict, merged: bool = True):
    rest_api = MagicMock()
    rest_api.commit.compare = AsyncMock(return_value=comparison)
    rest_api.repo.merge_branch = AsyncMock(return_value=merged)
    rest_api.reference.get_branch_reference = AsyncMock(return_value={"object": {"sha": "default-sha"}})
    rest_api.reference.update_reference = AsyncMock()

    with patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)):
        reset = await task._sync_branch_with_default_branch("main")

    return reset, rest_api


async def test_identical_branch_is_treated_as_fresh(task):
    reset, rest_api = await _sync(task, {"status": "identical", "behind_by": 0, "commits": []})

    assert reset is True
    rest_api.reference.update_reference.assert_not_awaited()
    rest_api.repo.merge_branch.assert_not_awaited()


async def test_branch_without_own_commits_behind_default_is_reset(task):
    reset, rest_api = await _sync(task, {"status": "behind", "behind_by": 3, "commits": []})

    assert reset is True
    rest_api.reference.update_reference.assert_awaited_once_with(
        "my-org", ".otterdog", "otterdog/blueprint/add-dot-github-repo", "default-sha", force=True
    )


async def test_up_to_date_branch_with_own_commits_is_left_alone(task):
    reset, rest_api = await _sync(task, {"status": "ahead", "behind_by": 0, "commits": [_commit("Bot")]})

    assert reset is False
    rest_api.reference.update_reference.assert_not_awaited()
    rest_api.repo.merge_branch.assert_not_awaited()


async def test_stale_branch_with_only_otterdog_commits_is_reset(task):
    # regression: remediation branches were never brought up to date and their PRs conflicted forever
    comparison = {"status": "diverged", "behind_by": 5, "commits": [_commit("Bot"), _commit("Bot")]}
    reset, rest_api = await _sync(task, comparison)

    assert reset is True
    rest_api.reference.update_reference.assert_awaited_once()
    rest_api.repo.merge_branch.assert_not_awaited()


async def test_stale_branch_with_maintainer_commits_gets_default_branch_merged(task):
    comparison = {"status": "diverged", "behind_by": 5, "commits": [_commit("Bot"), _commit("User")]}
    reset, rest_api = await _sync(task, comparison, merged=True)

    assert reset is False
    rest_api.reference.update_reference.assert_not_awaited()
    rest_api.repo.merge_branch.assert_awaited_once()
    assert rest_api.repo.merge_branch.await_args.args[2:4] == ("otterdog/blueprint/add-dot-github-repo", "main")


async def test_conflicting_branch_with_maintainer_commits_is_not_reset(task):
    comparison = {"status": "diverged", "behind_by": 5, "commits": [_commit(None)]}
    reset, rest_api = await _sync(task, comparison, merged=False)

    assert reset is False
    rest_api.reference.update_reference.assert_not_awaited()
