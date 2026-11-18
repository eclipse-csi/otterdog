#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import re

import pretend
import pytest

from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.content_client import ContentClient

_CONTENT_PATH = "/repos/test-org/test-repo/contents/path/to/file.txt"


def _content_client(get_result, delete_result=None) -> ContentClient:
    """A content client whose requests return the given results, or raise them when they are exceptions."""

    async def request_json(method, url_path, data=None, params=None):
        result = get_result if method == "GET" else delete_result
        if isinstance(result, Exception):
            raise result
        return result

    requester = pretend.stub(request_json=pretend.call_recorder(request_json))
    return ContentClient(pretend.stub(requester=requester))


def _sent_methods(client: ContentClient) -> list[str]:
    return [call.args[0] for call in client.requester.request_json.calls]


class TestContentClientDeleteContent:
    @pytest.mark.parametrize(
        "message,expected_message",
        [
            (None, "Deleting file 'path/to/file.txt' with otterdog."),
            ("chore: remove file", "chore: remove file"),
        ],
    )
    async def test_deletes_the_file_with_its_sha(self, message, expected_message):
        client = _content_client({"type": "file", "sha": "abc123"}, {"commit": {"sha": "def456"}})

        deleted = await client.delete_content("test-org", "test-repo", "path/to/file.txt", message)

        assert deleted is True
        get_call, delete_call = client.requester.request_json.calls
        assert get_call.args == ("GET", _CONTENT_PATH)
        assert delete_call.args == ("DELETE", _CONTENT_PATH, {"message": expected_message, "sha": "abc123"})

    async def test_absent_file_is_not_deleted(self):
        client = _content_client(GitHubException(_CONTENT_PATH, 404, '{"message": "Not Found"}'))

        deleted = await client.delete_content("test-org", "test-repo", "path/to/file.txt")

        assert deleted is False
        assert _sent_methods(client) == ["GET"]

    @pytest.mark.parametrize("status", [403, 500, 502])
    async def test_failed_read_is_not_taken_as_an_absent_file(self, status):
        client = _content_client(GitHubException(_CONTENT_PATH, status, '{"message": "Server Error"}'))

        with pytest.raises(RuntimeError, match=re.escape("failed retrieving content 'path/to/file.txt'")) as exc_info:
            await client.delete_content("test-org", "test-repo", "path/to/file.txt")

        assert f"status={status}" in str(exc_info.value)
        assert _sent_methods(client) == ["GET"]

    async def test_directory_is_not_deleted(self):
        client = _content_client([{"type": "file", "name": "file.txt", "sha": "abc123"}])

        with pytest.raises(RuntimeError, match="is not a file"):
            await client.delete_content("test-org", "test-repo", "path/to/file.txt")

        assert _sent_methods(client) == ["GET"]

    async def test_failed_deletion_raises(self):
        client = _content_client(
            {"type": "file", "sha": "abc123"},
            GitHubException(_CONTENT_PATH, 409, '{"message": "path/to/file.txt does not match abc123"}'),
        )

        with pytest.raises(
            RuntimeError, match=re.escape("failed deleting content 'path/to/file.txt' in repo 'test-org/test-repo'")
        ):
            await client.delete_content("test-org", "test-repo", "path/to/file.txt")
