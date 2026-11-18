#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json

import pytest
from pretend import stub

from otterdog.providers.github.rest.reference_client import ReferenceClient


def _client(status: int, body: str):
    calls = []

    async def request_raw(method, url):
        calls.append((method, url))
        return status, body

    return ReferenceClient(stub(requester=stub(request_raw=request_raw))), calls


def _error(message: str) -> str:
    return json.dumps(
        {"message": message, "documentation_url": "https://docs.github.com/rest/git/refs#delete-a-reference"}
    )


async def test_deleting_a_reference():
    client, calls = _client(204, "")

    assert await client.delete_reference("org", "repo", "otterdog/update") is True
    assert calls == [("DELETE", "/repos/org/repo/git/refs/heads/otterdog/update")]


@pytest.mark.parametrize("message", ["Reference does not exist", "reference does not exist"])
async def test_a_reference_already_deleted_is_not_a_failure(message):
    # GitHub answers with 422 when the branch has already been deleted, e.g. on merge of the pull request
    client, _ = _client(422, _error(message))

    assert await client.delete_reference("org", "repo", "otterdog/update") is False


@pytest.mark.parametrize(
    "body",
    [
        _error("Validation Failed"),
        _error("Cannot delete the default branch"),
        _error("Reference does not exist in the cache"),
        "Reference does not exist",
        "[]",
    ],
)
async def test_any_other_unprocessable_deletion_fails(body):
    client, _ = _client(422, body)

    with pytest.raises(RuntimeError, match="failed deleting reference 'otterdog/update' in repo 'org/repo'\n422: "):
        await client.delete_reference("org", "repo", "otterdog/update")


async def test_a_missing_reference_is_not_a_failure():
    client, _ = _client(404, _error("Not Found"))

    assert await client.delete_reference("org", "repo", "otterdog/update") is False


async def test_a_conflicting_deletion_is_not_a_failure():
    client, _ = _client(409, _error("Conflict"))

    assert await client.delete_reference("org", "repo", "otterdog/update") is False


async def test_an_unexpected_status_fails():
    client, _ = _client(500, "")

    with pytest.raises(RuntimeError, match="failed deleting reference"):
        await client.delete_reference("org", "repo", "otterdog/update")
