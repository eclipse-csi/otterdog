import json

import pretend
import pytest

from otterdog.providers.github.rest.repo_client import RepoClient


class TestRepoClientCodeScanningConfig:
    @pytest.mark.parametrize(
        "input_languages,expected_languages,description",
        [
            (
                ["javascript", "javascript-typescript", "typescript"],
                ["javascript", "typescript"],
                "filters out invalid javascript-typescript",
            ),
            (
                ["javascript", "typescript", "python"],
                ["javascript", "typescript", "python"],
                "keeps all valid languages",
            ),
            ([], [], "handles empty languages list"),
            (["javascript-typescript"], [], "filters out only invalid language"),
            (["javascript", "typescript"], ["javascript", "typescript"], "keeps valid languages unchanged"),
        ],
    )
    async def test_fill_code_scanning_config_language_filtering(self, input_languages, expected_languages, description):
        async def mock_request_raw(method, url):
            return (200, json.dumps({"languages": input_languages, "state": "configured"}))

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=pretend.call_recorder(mock_request_raw)))

        repo_client = RepoClient(mocked_restapi)

        repo_data = {}

        await repo_client._fill_code_scanning_config("test-org", "test-repo", repo_data)

        assert len(repo_client.requester.request_raw.calls) == 1
        call = repo_client.requester.request_raw.calls[0]
        assert call.args == ("GET", "/repos/test-org/test-repo/code-scanning/default-setup")

        expected_config = {"languages": expected_languages, "state": "configured"}
        assert repo_data["code_scanning_default_config"] == expected_config

    async def test_fill_code_scanning_config_no_languages_key(self):
        async def mock_request_raw(method, url):
            return (200, json.dumps({"state": "configured"}))

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=pretend.call_recorder(mock_request_raw)))
        repo_client = RepoClient(mocked_restapi)
        repo_data = {}

        await repo_client._fill_code_scanning_config("test-org", "test-repo", repo_data)

        expected_config = {"state": "configured"}
        assert repo_data["code_scanning_default_config"] == expected_config

    @pytest.mark.parametrize(
        "status_code,response_body",
        [
            (404, "Not Found"),
            (403, "Forbidden"),
            (500, "Internal Server Error"),
        ],
    )
    async def test_fill_code_scanning_config_non_200_status(self, status_code, response_body):
        async def mock_request_raw(method, url):
            return (status_code, response_body)

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=pretend.call_recorder(mock_request_raw)))
        repo_client = RepoClient(mocked_restapi)

        repo_data = {}

        await repo_client._fill_code_scanning_config("test-org", "test-repo", repo_data)

        assert len(repo_client.requester.request_raw.calls) == 1
        assert "code_scanning_default_config" not in repo_data


class TestRepoClientUpdateRepo:
    async def test_update_repo_with_rename_and_topics_correct_order(self):
        request_calls = []

        async def mock_request_json(method, url, data=None):
            request_calls.append((method, url, data))
            return data or {}

        mocked_restapi = pretend.stub(requester=pretend.stub(request_json=pretend.call_recorder(mock_request_json)))
        repo_client = RepoClient(mocked_restapi)

        update_data = {"name": "new-repo-name", "topics": ["python", "cli"], "description": "A test repository"}

        await repo_client.update_repo("test-org", "old-repo-name", update_data)

        assert repo_client.requester.request_json.calls == [
            pretend.call(
                "PATCH", "/repos/test-org/old-repo-name", {"name": "new-repo-name", "description": "A test repository"}
            ),
            pretend.call("PUT", "/repos/test-org/new-repo-name/topics", data={"names": ["python", "cli"]}),
        ]

    async def test_update_repo_topics_only_no_rename(self):
        request_calls = []

        async def mock_request_json(method, url, data=None):
            request_calls.append((method, url, data))
            return {}

        mocked_restapi = pretend.stub(requester=pretend.stub(request_json=pretend.call_recorder(mock_request_json)))
        repo_client = RepoClient(mocked_restapi)

        update_data = {"topics": ["python", "cli"], "description": "A test repository"}

        await repo_client.update_repo("test-org", "repo-name", update_data)

        assert repo_client.requester.request_json.calls == [
            pretend.call("PATCH", "/repos/test-org/repo-name", {"description": "A test repository"}),
            pretend.call("PUT", "/repos/test-org/repo-name/topics", data={"names": ["python", "cli"]}),
        ]

    async def test_update_repo_rename_only(self):
        request_calls = []

        async def mock_request_json(method, url, data=None):
            request_calls.append((method, url, data))
            return data or {}

        mocked_restapi = pretend.stub(requester=pretend.stub(request_json=pretend.call_recorder(mock_request_json)))
        repo_client = RepoClient(mocked_restapi)

        update_data = {"name": "new-repo-name"}

        await repo_client.update_repo("test-org", "old-repo-name", update_data)

        assert repo_client.requester.request_json.calls == [
            pretend.call("PATCH", "/repos/test-org/old-repo-name", {"name": "new-repo-name"}),
        ]
