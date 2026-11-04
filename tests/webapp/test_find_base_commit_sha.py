#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest
from pretend import stub

from otterdog.webapp.utils import find_base_commit_sha

PULL_REQUEST_NUMBER = 2


def _commit(sha: str, parents: list[str], message: str | None = None, date: str = "2026-11-04T10:00:00Z") -> dict:
    return {
        "sha": sha,
        "parents": [{"sha": parent} for parent in parents],
        "commit": {
            "author": {"name": "author", "email": "author@example.org", "date": date},
            "message": message if message is not None else f"message of {sha}",
        },
    }


def _rebased(commit: dict, sha: str, parent: str) -> dict:
    """Returns the copy of a commit of the pull request that a rebase merge adds to the base branch."""
    return {**commit, "sha": sha, "parents": [{"sha": parent}]}


def _rest_api(commits: list[dict], pull_request_commits: list[dict]):
    commits_by_sha = {commit["sha"]: commit for commit in commits}

    async def get_commit(_org_id, _repo_name, sha):
        return commits_by_sha[sha]

    async def get_commits(_org_id, _repo_name, pull_request_number):
        assert pull_request_number == str(PULL_REQUEST_NUMBER)
        return pull_request_commits

    return stub(commit=stub(get_commit=get_commit), pull_request=stub(get_commits=get_commits))


async def _find_base_commit_sha(rest_api, merge_commit_sha):
    return await find_base_commit_sha(rest_api, "org", "repo", PULL_REQUEST_NUMBER, merge_commit_sha)


PULL_REQUEST_COMMITS = [
    _commit("pr-1", ["base"], date="2026-11-04T10:01:00Z"),
    _commit("pr-2", ["pr-1"], date="2026-11-04T10:02:00Z"),
    _commit("pr-3", ["pr-2"], date="2026-11-04T10:03:00Z"),
]


async def test_find_base_commit_sha_for_merge_commit():
    rest_api = _rest_api([_commit("merge", ["base", "pr-3"])], PULL_REQUEST_COMMITS)

    assert await _find_base_commit_sha(rest_api, "merge") == "base"


async def test_find_base_commit_sha_for_squash_merge():
    rest_api = _rest_api(
        [_commit("squashed", ["base"], message="squashed (#2)"), _commit("base", ["previous"])],
        PULL_REQUEST_COMMITS,
    )

    assert await _find_base_commit_sha(rest_api, "squashed") == "base"


async def test_find_base_commit_sha_for_squash_merge_of_single_commit():
    rest_api = _rest_api([_commit("squashed", ["base"]), _commit("base", ["previous"])], PULL_REQUEST_COMMITS[:1])

    assert await _find_base_commit_sha(rest_api, "squashed") == "base"


async def test_find_base_commit_sha_for_rebase_merge():
    rest_api = _rest_api(
        [
            _rebased(PULL_REQUEST_COMMITS[2], "commit-3", "commit-2"),
            _rebased(PULL_REQUEST_COMMITS[1], "commit-2", "commit-1"),
            _rebased(PULL_REQUEST_COMMITS[0], "commit-1", "base"),
            _commit("base", ["previous"]),
        ],
        PULL_REQUEST_COMMITS,
    )

    assert await _find_base_commit_sha(rest_api, "commit-3") == "base"


async def test_find_base_commit_sha_for_rebase_merge_without_a_commit_of_the_pull_request():
    # e.g. a commit of the pull request that is empty once rebased
    rest_api = _rest_api(
        [
            _rebased(PULL_REQUEST_COMMITS[2], "commit-3", "commit-1"),
            _rebased(PULL_REQUEST_COMMITS[0], "commit-1", "base"),
            _commit("base", ["previous"]),
        ],
        PULL_REQUEST_COMMITS,
    )

    assert await _find_base_commit_sha(rest_api, "commit-3") == "base"


async def test_find_base_commit_sha_fails_for_root_commit():
    rest_api = _rest_api([_commit("root", [])], PULL_REQUEST_COMMITS)

    with pytest.raises(RuntimeError, match="'root' has no parent"):
        await _find_base_commit_sha(rest_api, "root")


async def test_find_base_commit_sha_fails_for_too_many_commits():
    pull_request_commits = [_commit(f"pr-{index}", ["base"], date=str(index)) for index in range(250)]
    rest_api = _rest_api([_commit("commit", ["parent"])], pull_request_commits)

    with pytest.raises(RuntimeError, match="at least 250 commits"):
        await _find_base_commit_sha(rest_api, "commit")
