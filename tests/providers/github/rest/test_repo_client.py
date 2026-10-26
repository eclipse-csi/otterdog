import json

import pretend
import pytest

from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.repo_client import RepoClient
from otterdog.providers.github.rest.requester import Requester


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

    async def test_update_repo_with_immutable_releases_after_rename(self):
        async def mock_request_json(method, url, data=None):
            return data or {}

        async def mock_request_raw(method, url):
            return (204, "")

        mocked_restapi = pretend.stub(
            requester=pretend.stub(
                request_json=pretend.call_recorder(mock_request_json),
                request_raw=pretend.call_recorder(mock_request_raw),
            )
        )
        repo_client = RepoClient(mocked_restapi)

        update_data = {"name": "new-repo-name", "immutable_releases_enabled": True}

        await repo_client.update_repo("test-org", "old-repo-name", update_data)

        assert repo_client.requester.request_json.calls == [
            pretend.call("PATCH", "/repos/test-org/old-repo-name", {"name": "new-repo-name"}),
        ]
        assert repo_client.requester.request_raw.calls == [
            pretend.call("PUT", "/repos/test-org/new-repo-name/immutable-releases"),
        ]


class TestRepoClientImmutableReleases:
    async def test_fill_immutable_releases_enabled(self):
        async def mock_request_raw(method, url):
            return (200, json.dumps({"enabled": True, "enforced_by_owner": False}))

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=pretend.call_recorder(mock_request_raw)))
        repo_client = RepoClient(mocked_restapi)

        repo_data = {}

        await repo_client._fill_immutable_releases("test-org", "test-repo", repo_data)

        assert repo_client.requester.request_raw.calls == [
            pretend.call("GET", "/repos/test-org/test-repo/immutable-releases")
        ]
        assert repo_data["immutable_releases_enabled"] is True

    async def test_fill_immutable_releases_disabled(self):
        async def mock_request_raw(method, url):
            return (404, "Not Found")

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=pretend.call_recorder(mock_request_raw)))
        repo_client = RepoClient(mocked_restapi)

        repo_data = {}

        await repo_client._fill_immutable_releases("test-org", "test-repo", repo_data)

        assert repo_client.requester.request_raw.calls == [
            pretend.call("GET", "/repos/test-org/test-repo/immutable-releases")
        ]
        assert repo_data["immutable_releases_enabled"] is False

    async def test_fill_immutable_releases_reads_enabled_flag(self):
        async def mock_request_raw(method, url):
            return (200, json.dumps({"enabled": False, "enforced_by_owner": False}))

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=mock_request_raw))
        repo_client = RepoClient(mocked_restapi)

        repo_data = {}

        await repo_client._fill_immutable_releases("test-org", "test-repo", repo_data)

        assert repo_data["immutable_releases_enabled"] is False

    @pytest.mark.parametrize("status", [402, 403])
    async def test_fill_immutable_releases_leaves_setting_unset_when_unavailable(self, status):
        async def mock_request_raw(method, url):
            return (status, "feature unavailable")

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=mock_request_raw))
        repo_client = RepoClient(mocked_restapi)

        repo_data = {}

        await repo_client._fill_immutable_releases("test-org", "test-repo", repo_data)

        assert "immutable_releases_enabled" not in repo_data

    async def test_fill_immutable_releases_leaves_setting_unset_on_missing_scopes(self):
        async def mock_request_raw(method, url):
            # the requester raises an exception for a 403 caused by missing OAuth scopes
            Requester._check_permissions(
                url, 403, "Forbidden", {"X-OAuth-Scopes": "repo", "X-Accepted-OAuth-Scopes": "admin:org"}
            )
            raise AssertionError("expected InsufficientPermissionsException")

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=mock_request_raw))
        repo_client = RepoClient(mocked_restapi)

        repo_data = {}

        await repo_client._fill_immutable_releases("test-org", "test-repo", repo_data)

        assert "immutable_releases_enabled" not in repo_data

    async def test_fill_immutable_releases_raises_on_unexpected_status(self):
        async def mock_request_raw(method, url):
            return (500, "Internal Server Error")

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=pretend.call_recorder(mock_request_raw)))
        repo_client = RepoClient(mocked_restapi)

        repo_data = {}

        with pytest.raises(RuntimeError, match="failed retrieving immutable release settings"):
            await repo_client._fill_immutable_releases("test-org", "test-repo", repo_data)


class TestRepoClientGetRepoIds:
    async def test_get_repo_ids(self):
        async def mock_request_json(method, url):
            return {"id": {"/repos/test-org/repo1": 1, "/repos/test-org/repo2": 2}[url]}

        mocked_restapi = pretend.stub(requester=pretend.stub(request_json=pretend.call_recorder(mock_request_json)))
        repo_client = RepoClient(mocked_restapi)

        assert await repo_client.get_repo_ids("test-org", ["repo1", "repo2"]) == [1, 2]
        assert repo_client.requester.request_json.calls == [
            pretend.call("GET", "/repos/test-org/repo1"),
            pretend.call("GET", "/repos/test-org/repo2"),
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

        async def mock_cache_size(org, repo):
            return {"max_cache_size_gb": 10}

        repo_client._get_max_cache_size_gb = mock_cache_size

        result = await repo_client.get_workflow_settings("org", "repo")

        # Assert result includes the approval policy
        assert set(policy.items()).issubset(result.items())

    async def test_get_workflow_settings_skips_fork_pr_approval_policy_for_private_repo(self):
        called = []

        async def mock_request(method, url):
            return {}

        async def mock_get(org, repo):
            called.append(True)
            return {"approval_policy": "all_external_contributors"}

        mock_requester = pretend.stub(request_json=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        repo_client = RepoClient(mock_restapi)
        repo_client._get_fork_pr_approval_policy = mock_get

        async def mock_cache_size(org, repo):
            return {"max_cache_size_gb": 10}

        repo_client._get_max_cache_size_gb = mock_cache_size

        result = await repo_client.get_workflow_settings("org", "repo", is_private=True)

        # Assert the fork PR approval policy was NOT fetched
        assert not called
        assert "approval_policy" not in result


class TestRepoClientGitHubPagesCustomDomain:
    @staticmethod
    def _create_client(responses):
        async def mock_request_raw(method, url, data=None):
            return responses[method]

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=pretend.call_recorder(mock_request_raw)))
        return RepoClient(mocked_restapi)

    async def test_update_custom_domain_of_existing_site(self):
        repo_client = self._create_client({"GET": (200, "{}"), "PUT": (204, "")})

        await repo_client._update_github_pages_config(
            "test-org", "test-repo", {"cname": "docs.example.org", "https_enforced": True}
        )

        assert repo_client.requester.request_raw.calls == [
            pretend.call("GET", "/repos/test-org/test-repo/pages"),
            pretend.call("PUT", "/repos/test-org/test-repo/pages", data=json.dumps({"cname": "docs.example.org"})),
            pretend.call("PUT", "/repos/test-org/test-repo/pages", data=json.dumps({"https_enforced": True})),
        ]

    async def test_remove_custom_domain(self):
        repo_client = self._create_client({"GET": (200, "{}"), "PUT": (204, "")})

        await repo_client._update_github_pages_config("test-org", "test-repo", {"cname": None})

        assert repo_client.requester.request_raw.calls == [
            pretend.call("GET", "/repos/test-org/test-repo/pages"),
            pretend.call("PUT", "/repos/test-org/test-repo/pages", data=json.dumps({"cname": None})),
        ]

    async def test_create_site_with_custom_domain(self):
        repo_client = self._create_client({"GET": (404, "Not Found"), "POST": (201, "{}"), "PUT": (204, "")})

        await repo_client._update_github_pages_config(
            "test-org",
            "test-repo",
            {"build_type": "workflow", "cname": "docs.example.org", "https_enforced": True},
        )

        assert repo_client.requester.request_raw.calls == [
            pretend.call("GET", "/repos/test-org/test-repo/pages"),
            pretend.call("POST", "/repos/test-org/test-repo/pages", data=json.dumps({"build_type": "workflow"})),
            pretend.call("PUT", "/repos/test-org/test-repo/pages", data=json.dumps({"cname": "docs.example.org"})),
            pretend.call("PUT", "/repos/test-org/test-repo/pages", data=json.dumps({"https_enforced": True})),
        ]

    @staticmethod
    def _create_https_client(https_response):
        async def mock_request_raw(method, url, data=None):
            if method == "GET":
                return 200, "{}"
            if data is not None and "https_enforced" in json.loads(data):
                return https_response
            return 204, ""

        mocked_restapi = pretend.stub(requester=pretend.stub(request_raw=mock_request_raw))
        return RepoClient(mocked_restapi)

    @pytest.mark.parametrize("https_enforced", [True, False])
    async def test_https_enforced_with_pending_certificate_only_warns(self, https_enforced, caplog):
        body = json.dumps(
            {
                "message": "The certificate does not exist yet",
                "documentation_url": "https://docs.github.com/rest/pages/pages#update-information-about-a-apiname-pages-site",
                "status": "404",
            }
        )
        repo_client = self._create_https_client((404, body))

        await repo_client._update_github_pages_config(
            "test-org", "test-repo", {"cname": "docs.example.org", "https_enforced": https_enforced}
        )

        assert "the certificate for the custom domain has not been issued yet" in caplog.text

    @pytest.mark.parametrize("https_enforced", [True, False])
    @pytest.mark.parametrize(
        "status,body",
        [
            (404, '{"message": "Not Found"}'),
            (422, '{"message": "Validation Failed"}'),
            (500, "Internal Server Error"),
            (503, "Service Unavailable"),
        ],
    )
    async def test_https_enforced_failure_raises(self, https_enforced, status, body):
        repo_client = self._create_https_client((status, body))

        with pytest.raises(RuntimeError, match="failed to update github pages https enforcement"):
            await repo_client._update_github_pages_config(
                "test-org", "test-repo", {"cname": "docs.example.org", "https_enforced": https_enforced}
            )

    async def test_custom_domain_failure_raises(self):
        repo_client = self._create_client({"GET": (200, "{}"), "PUT": (422, "invalid domain")})

        with pytest.raises(RuntimeError, match="failed to update github pages custom domain"):
            await repo_client._update_github_pages_config("test-org", "test-repo", {"cname": "docs.example.org"})

    async def test_update_custom_domain_of_organization_site(self):
        current_config = {"build_type": "legacy", "cname": None, "https_enforced": True}
        repo_client = self._create_client({"GET": (200, json.dumps(current_config)), "PUT": (204, "")})

        await repo_client._update_github_pages_config(
            "test-org", "test-org.github.io", {"cname": "docs.example.org", "https_enforced": True}
        )

        assert repo_client.requester.request_raw.calls == [
            pretend.call("GET", "/repos/test-org/test-org.github.io/pages"),
            pretend.call("GET", "/repos/test-org/test-org.github.io/pages"),
            pretend.call(
                "PUT", "/repos/test-org/test-org.github.io/pages", data=json.dumps({"cname": "docs.example.org"})
            ),
            pretend.call("PUT", "/repos/test-org/test-org.github.io/pages", data=json.dumps({"https_enforced": True})),
        ]

    async def test_custom_domain_of_organization_site_already_up_to_date(self):
        current_config = {"build_type": "legacy", "cname": "docs.example.org", "https_enforced": True}
        repo_client = self._create_client({"GET": (200, json.dumps(current_config))})

        await repo_client._update_github_pages_config(
            "test-org", "test-org.github.io", {"cname": "docs.example.org", "https_enforced": True}
        )

        assert repo_client.requester.request_raw.calls == [
            pretend.call("GET", "/repos/test-org/test-org.github.io/pages"),
        ]
