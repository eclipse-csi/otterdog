#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pretend
import pytest

# imported through the webhook package, as importing the task first runs into an import cycle
from otterdog.webapp.webhook import ValidatePullRequestTask  # isort: skip
from otterdog.webapp.tasks import validate_pull_request
from otterdog.webapp.tasks.validate_pull_request import _MergeCommit


@pytest.fixture(autouse=True)
def no_retry_delays(monkeypatch):
    monkeypatch.setattr(validate_pull_request, "_MERGE_COMMIT_RETRY_DELAYS", (0, 0))


def _task(base_ref="main"):
    task = ValidatePullRequestTask(1, "test-org", "repo", 42)
    task._pull_request = SimpleNamespace(
        head=SimpleNamespace(sha="head-sha"),
        base=SimpleNamespace(ref=base_ref, repo=SimpleNamespace(default_branch="main")),
    )
    return task


def _pull_request(mergeable, merge_commit_sha="merge-sha", head_sha="head-sha"):
    return {"head": {"sha": head_sha}, "mergeable": mergeable, "merge_commit_sha": merge_commit_sha}


def _rest_api(pull_requests, commits=None, default_branch_sha="base-sha"):
    """GitHub returning the given states of the pull request, one per request, the last one repeated."""
    pull_requests = list(pull_requests)

    async def get_pull_request(org_id, repo_name, number):
        assert (org_id, repo_name, number) == ("test-org", "repo", "42")
        return pull_requests.pop(0) if len(pull_requests) > 1 else pull_requests[0]

    async def get_commit(org_id, repo_name, sha):
        return {"parents": [{"sha": parent} for parent in (commits or {})[sha]]}

    async def get_branch(org_id, repo_name, branch_name):
        assert (org_id, repo_name, branch_name) == ("test-org", "repo", "main")
        return {"commit": {"sha": default_branch_sha}}

    return pretend.stub(
        pull_request=pretend.stub(get_pull_request=AsyncMock(side_effect=get_pull_request)),
        commit=pretend.stub(get_commit=AsyncMock(side_effect=get_commit)),
        repo=pretend.stub(get_branch=AsyncMock(side_effect=get_branch)),
    )


async def test_merge_commit_of_a_mergeable_pull_request():
    rest_api = _rest_api([_pull_request(True)], {"merge-sha": ["base-sha", "head-sha"]})

    assert await _task()._find_merge_commit(rest_api) == _MergeCommit("merge-sha", "base-sha")


async def test_merge_commit_is_waited_for_while_github_creates_it():
    rest_api = _rest_api(
        [
            # mergeability not computed yet
            _pull_request(None, None),
            # still the merge commit of the previous head
            _pull_request(True, "old-merge-sha"),
            _pull_request(True, "merge-sha"),
        ],
        {"old-merge-sha": ["old-base-sha", "old-head-sha"], "merge-sha": ["base-sha", "head-sha"]},
    )

    assert await _task()._find_merge_commit(rest_api) == _MergeCommit("merge-sha", "base-sha")
    assert rest_api.pull_request.get_pull_request.await_count == 3


async def test_merge_commit_is_waited_for_once_the_default_branch_moved():
    rest_api = _rest_api(
        [
            # same head, still the merge commit into the previous head of the default branch, which
            # the base sha of the pull request still refers to as well
            _pull_request(True, "old-merge-sha"),
            _pull_request(True, "merge-sha"),
        ],
        {"old-merge-sha": ["old-base-sha", "head-sha"], "merge-sha": ["base-sha", "head-sha"]},
    )

    assert await _task()._find_merge_commit(rest_api) == _MergeCommit("merge-sha", "base-sha")
    assert rest_api.pull_request.get_pull_request.await_count == 2


async def test_no_merge_commit_while_the_default_branch_keeps_moving():
    rest_api = _rest_api(
        [_pull_request(True)], {"merge-sha": ["old-base-sha", "head-sha"]}, default_branch_sha="base-sha"
    )

    assert await _task()._find_merge_commit(rest_api) is None
    # one request, then one per retry delay
    assert rest_api.pull_request.get_pull_request.await_count == 3


async def test_no_merge_commit_once_github_gave_up_waiting():
    rest_api = _rest_api([_pull_request(None, None)])

    assert await _task()._find_merge_commit(rest_api) is None
    # one request, then one per retry delay
    assert rest_api.pull_request.get_pull_request.await_count == 3


async def test_no_merge_commit_for_conflicting_pull_request():
    rest_api = _rest_api([_pull_request(False)])

    assert await _task()._find_merge_commit(rest_api) is None
    assert rest_api.pull_request.get_pull_request.await_count == 1


async def test_no_merge_commit_once_a_newer_commit_has_been_pushed():
    rest_api = _rest_api(
        [_pull_request(True, head_sha="newer-head-sha")], {"merge-sha": ["base-sha", "newer-head-sha"]}
    )

    assert await _task()._find_merge_commit(rest_api) is None
    assert rest_api.pull_request.get_pull_request.await_count == 1


async def test_no_merge_commit_for_pull_request_not_targeting_the_default_branch():
    rest_api = _rest_api([_pull_request(True)], {"merge-sha": ["base-sha", "head-sha"]})

    assert await _task(base_ref="release")._find_merge_commit(rest_api) is None
    rest_api.pull_request.get_pull_request.assert_not_awaited()


async def test_no_merge_commit_when_github_fails():
    rest_api = pretend.stub(
        pull_request=pretend.stub(get_pull_request=AsyncMock(side_effect=RuntimeError("failed retrieving"))),
    )

    assert await _task()._find_merge_commit(rest_api) is None
