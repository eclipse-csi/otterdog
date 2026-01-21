import json

import pretend
import pytest

from otterdog.providers.github.rest.repo_client import GitHubException, RepoClient


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
    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
    @pytest.mark.asyncio
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
    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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


class TestRepoClientForkPrApprovalPolicy:
    async def test_get_fork_pr_approval_policy_success(self):
        expected_policy = {"approval_policy": "first_time_contributors"}
        expected_method = "GET"
        expected_url = "/repos/org/repo/actions/permissions/fork-pr-contributor-approval"

        async def mock_request(method, url):
            assert method == expected_method
            assert url == expected_url
            return expected_policy

        mock_requester = pretend.stub(request_json=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        repo_client = RepoClient(mock_restapi)

        result = await repo_client._get_fork_pr_approval_policy("org", "repo")

        assert result == expected_policy

    async def test_get_fork_pr_approval_policy_raises_on_error(self):
        async def mock_request(method, url):
            raise GitHubException(None, 500, "")

        mock_requester = pretend.stub(request_json=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        repo_client = RepoClient(mock_restapi)

        with pytest.raises(RuntimeError) as e:
            await repo_client._get_fork_pr_approval_policy("org", "repo")

        assert "fork PR approval policy" in str(e.value)

    async def test_update_fork_pr_approval_policy_success(self):
        expected_policy = {"approval_policy": "first_time_contributors"}
        expected_method = "PUT"
        expected_url = "/repos/org/repo/actions/permissions/fork-pr-contributor-approval"

        async def mock_request(method, url, data):
            assert method == expected_method
            assert url == expected_url
            assert json.loads(data) == expected_policy
            return (204, "")

        mock_requester = pretend.stub(request_raw=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        repo_client = RepoClient(mock_restapi)

        await repo_client._update_fork_pr_approval_policy("org", "repo", expected_policy)

    async def test_update_fork_pr_approval_policy_raises_on_non_204(self):
        async def mock_request(method, url, data):
            return (500, "")

        mock_requester = pretend.stub(request_raw=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        repo_client = RepoClient(mock_restapi)

        with pytest.raises(RuntimeError) as e:
            await repo_client._update_fork_pr_approval_policy(
                "org", "repo", {"approval_policy": "first_time_contributors"}
            )
        assert "fork PR approval policy" in str(e)

    async def test_update_workflow_settings_with_approval_policy(self):
        policy = {"approval_policy": "all_external_contributors"}

        async def mock_update(org, repo, data):
            assert org == "org"
            assert repo == "repo"
            assert data == policy

        repo_client = RepoClient(None)
        repo_client._update_fork_pr_approval_policy = mock_update

        await repo_client.update_workflow_settings("org", "repo", policy)

    async def test_update_workflow_settings_without_approval_policy(self):
        policy = {}

        async def mock_update(org, repo, data): ...

        repo_client = RepoClient(None)
        repo_client._update_fork_pr_approval_policy = pretend.call_recorder(mock_update)

        await repo_client.update_workflow_settings("org", "repo", policy)

        assert not repo_client._update_fork_pr_approval_policy.calls

    async def test_get_workflow_settings_includes_fork_pr_approval_policy(self):
        policy = {"approval_policy": "all_external_contributors"}

        async def mock_request(method, url):
            return {}

        async def mock_get(org, repo):
            assert org == "org"
            assert repo == "repo"
            return policy

        mock_requester = pretend.stub(request_json=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        repo_client = RepoClient(mock_restapi)
        repo_client._get_fork_pr_approval_policy = mock_get

        result = await repo_client.get_workflow_settings("org", "repo")

        # Assert result includes the approval policy
        assert set(policy.items()).issubset(result.items())
