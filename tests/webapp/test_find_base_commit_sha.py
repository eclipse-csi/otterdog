#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest
from pretend import stub

from otterdog.webapp import utils
from otterdog.webapp.utils import find_base_commit_sha


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(utils, "_BASE_BRANCH_ACTIVITY_RETRY_DELAYS", (0, 0))


def _commit(sha: str, parents: list[str]) -> dict:
    return {"sha": sha, "parents": [{"sha": parent} for parent in parents]}


def _activity(before: str, after: str, activity_type: str = "pr_merge") -> dict:
    return {"before": before, "after": after, "ref": "refs/heads/main", "activity_type": activity_type}


def _rest_api(commits: list[dict], *recorded_activities: list[dict]):
    """Returns a rest api whose activities of the base branch are the given ones at each successive lookup."""
    commits_by_sha = {commit["sha"]: commit for commit in commits}
    lookups = []
    consumed = []

    async def get_commit(_org_id, _repo_name, sha):
        return commits_by_sha[sha]

    async def get_activities(_org_id, _repo_name, ref, activity_type):
        assert ref == "refs/heads/main"
        lookups.append(ref)
        activities = recorded_activities[min(len(lookups), len(recorded_activities)) - 1]
        for activity in activities:
            if activity["activity_type"] == activity_type:
                consumed.append(activity)
                yield activity

    return stub(
        commit=stub(get_commit=get_commit),
        repo=stub(get_activities=get_activities),
        lookups=lookups,
        consumed=consumed,
    )


async def _find_base_commit_sha(rest_api, merge_commit_sha):
    return await find_base_commit_sha(rest_api, "org", "repo", "main", merge_commit_sha)


async def test_find_base_commit_sha_for_merge_commit():
    rest_api = _rest_api([_commit("merge", ["base", "pr-3"])], [])

    assert await _find_base_commit_sha(rest_api, "merge") == "base"
    assert rest_api.lookups == []


async def test_find_base_commit_sha_for_squash_merge():
    rest_api = _rest_api(
        [_commit("squashed", ["base"])],
        [_activity("squashed", "later"), _activity("base", "squashed"), _activity("previous", "base")],
    )

    assert await _find_base_commit_sha(rest_api, "squashed") == "base"


async def test_find_base_commit_sha_stops_at_the_merge_of_the_pull_request():
    # the activities are retrieved page by page, older ones are not retrieved once the merge has been found
    rest_api = _rest_api(
        [_commit("squashed", ["base"])],
        [_activity("squashed", "later"), _activity("base", "squashed"), _activity("previous", "base")],
    )

    assert await _find_base_commit_sha(rest_api, "squashed") == "base"
    assert rest_api.consumed == [_activity("squashed", "later"), _activity("base", "squashed")]


async def test_find_base_commit_sha_for_rebase_merge():
    # the parent of the last copied commit, and possibly further ones, can not be told apart from the base branch,
    # e.g. if a commit of the pull request has been cherry-picked onto it in the same second
    rest_api = _rest_api([_commit("commit-3", ["commit-2"])], [_activity("base", "commit-3")])

    assert await _find_base_commit_sha(rest_api, "commit-3") == "base"


async def test_find_base_commit_sha_once_github_records_the_merge():
    rest_api = _rest_api(
        [_commit("commit-3", ["commit-2"])],
        [_activity("previous", "base")],
        [_activity("base", "commit-3"), _activity("previous", "base")],
    )

    assert await _find_base_commit_sha(rest_api, "commit-3") == "base"
    assert len(rest_api.lookups) == 2


async def test_find_base_commit_sha_ignores_other_changes_of_the_branch_to_the_merge_commit():
    # e.g. the branch force-pushed back to the merge commit later on
    rest_api = _rest_api(
        [_commit("squashed", ["base"])],
        [
            _activity("later", "squashed", activity_type="force_push"),
            _activity("squashed", "later"),
            _activity("base", "squashed"),
        ],
    )

    assert await _find_base_commit_sha(rest_api, "squashed") == "base"


async def test_find_base_commit_sha_fails_if_github_does_not_record_the_merge_of_the_pull_request():
    rest_api = _rest_api(
        [_commit("commit-3", ["commit-2"])],
        [_activity("base", "commit-3", activity_type="merge_queue_merge"), _activity("previous", "base")],
    )

    with pytest.raises(RuntimeError, match="no merge of a pull request into branch 'main' up to commit 'commit-3'"):
        await _find_base_commit_sha(rest_api, "commit-3")

    assert len(rest_api.lookups) == 3
