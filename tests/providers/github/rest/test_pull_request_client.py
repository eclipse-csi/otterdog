#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from pretend import stub

from otterdog.providers.github.rest.pull_request_client import PullRequestClient


def _client(calls):
    async def request_json(method, url, data=None):
        calls.append((method, url, data))
        return {"merged": True}

    return PullRequestClient(stub(requester=stub(request_json=request_json)))


async def test_merging_a_pull_request():
    calls = []

    assert await _client(calls).merge("org", ".eclipsefdn", "25") is True
    assert calls == [("PUT", "/repos/org/.eclipsefdn/pulls/25/merge", {"merge_method": "squash"})]


async def test_merging_a_pull_request_only_if_its_head_is_still_the_given_commit():
    calls = []

    assert await _client(calls).merge("org", ".eclipsefdn", "25", sha="abc") is True
    assert calls == [("PUT", "/repos/org/.eclipsefdn/pulls/25/merge", {"merge_method": "squash", "sha": "abc"})]
