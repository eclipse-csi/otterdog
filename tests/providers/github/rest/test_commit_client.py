#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest
from pretend import stub

from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.commit_client import CommitClient


def _client(request_json):
    return CommitClient(stub(requester=stub(request_json=request_json)))


async def test_the_latest_commit_changing_a_file_of_the_default_branch():
    calls = []

    async def request_json(method, url, params=None):
        calls.append((method, url, params))
        return [{"sha": "abc"}]

    commit = await _client(request_json).get_latest_commit_for_path("org", ".eclipsefdn", "otterdog/org.jsonnet")

    assert commit == {"sha": "abc"}
    assert calls == [("GET", "/repos/org/.eclipsefdn/commits", {"path": "otterdog/org.jsonnet", "per_page": "1"})]


async def test_the_latest_commit_changing_a_file_of_a_ref():
    async def request_json(method, url, params=None):
        assert params == {"path": "otterdog/org.jsonnet", "per_page": "1", "sha": "main"}
        return []

    # no commit changed the file on that ref
    assert await _client(request_json).get_latest_commit_for_path("org", "repo", "otterdog/org.jsonnet", "main") is None


async def test_the_latest_commit_translates_github_errors():
    async def request_json(method, url, params=None):
        raise GitHubException(url, 404, "not found")

    client = _client(request_json)

    with pytest.raises(RuntimeError, match="failed retrieving the latest commit"):
        await client.get_latest_commit_for_path("org", "repo", "otterdog/org.jsonnet")
