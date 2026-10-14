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


def _rest_api(parents: dict[str, list[str]], associated_pull_requests: dict[str, list[int]]):
    async def get_commit(_org_id, _repo_name, sha):
        return {"sha": sha, "parents": [{"sha": parent} for parent in parents[sha]]}

    async def get_associated_pull_requests(_org_id, _repo_name, sha):
        return [{"number": number} for number in associated_pull_requests.get(sha, [])]

    return stub(commit=stub(get_commit=get_commit, get_associated_pull_requests=get_associated_pull_requests))


async def _find_base_commit_sha(rest_api, merge_commit_sha):
    return await find_base_commit_sha(rest_api, "org", "repo", PULL_REQUEST_NUMBER, merge_commit_sha)


async def test_find_base_commit_sha_for_merge_commit():
    rest_api = _rest_api({"merge": ["base", "pr-head"]}, {})

    assert await _find_base_commit_sha(rest_api, "merge") == "base"


async def test_find_base_commit_sha_for_squash_merge():
    rest_api = _rest_api({"squashed": ["base"]}, {"squashed": [PULL_REQUEST_NUMBER], "base": [1]})

    assert await _find_base_commit_sha(rest_api, "squashed") == "base"


async def test_find_base_commit_sha_for_rebase_merge():
    rest_api = _rest_api(
        {"commit-3": ["commit-2"], "commit-2": ["commit-1"], "commit-1": ["base"]},
        {
            "commit-1": [PULL_REQUEST_NUMBER],
            "commit-2": [PULL_REQUEST_NUMBER],
            "commit-3": [PULL_REQUEST_NUMBER],
        },
    )

    assert await _find_base_commit_sha(rest_api, "commit-3") == "base"


async def test_find_base_commit_sha_for_base_commit_without_pull_request():
    rest_api = _rest_api({"commit-2": ["commit-1"], "commit-1": ["base"]}, {"commit-1": [PULL_REQUEST_NUMBER]})

    assert await _find_base_commit_sha(rest_api, "commit-2") == "base"


async def test_find_base_commit_sha_fails_for_root_commit():
    rest_api = _rest_api({"root": []}, {})

    with pytest.raises(RuntimeError, match="has no parent"):
        await _find_base_commit_sha(rest_api, "root")
