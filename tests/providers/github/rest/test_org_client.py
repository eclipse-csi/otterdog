#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json

import pretend
import pytest

from otterdog.providers.github.rest.org_client import GitHubException, OrgClient


class TestOrgClientForkPrApprovalPolicy:
    async def test_get_fork_pr_approval_policy_success(self):
        expected_policy = {"approval_policy": "first_time_contributors"}
        expected_method = "GET"
        expected_url = "/orgs/org/actions/permissions/fork-pr-contributor-approval"

        async def mock_request(method, url):
            assert method == expected_method
            assert url == expected_url
            return expected_policy

        mock_requester = pretend.stub(request_json=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        org_client = OrgClient(mock_restapi)

        result = await org_client._get_fork_pr_approval_policy("org")

        assert result == expected_policy

    async def test_get_fork_pr_approval_policy_raises_on_error(self):
        async def mock_request(method, url):
            raise GitHubException(None, 500, "")

        mock_requester = pretend.stub(request_json=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        org_client = OrgClient(mock_restapi)

        with pytest.raises(RuntimeError) as e:
            await org_client._get_fork_pr_approval_policy("org")

        assert "fork PR approval policy" in str(e.value)

    async def test_update_fork_pr_approval_policy_success(self):
        expected_policy = {"approval_policy": "first_time_contributors"}
        expected_method = "PUT"
        expected_url = "/orgs/org/actions/permissions/fork-pr-contributor-approval"

        async def mock_request(method, url, data):
            assert method == expected_method
            assert url == expected_url
            assert json.loads(data) == expected_policy
            return (204, "")

        mock_requester = pretend.stub(request_raw=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        org_client = OrgClient(mock_restapi)

        await org_client._update_fork_pr_approval_policy("org", expected_policy)

    async def test_update_fork_pr_approval_policy_raises_on_non_204(self):
        async def mock_request(method, url, data):
            return (500, "")

        mock_requester = pretend.stub(request_raw=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        org_client = OrgClient(mock_restapi)

        with pytest.raises(RuntimeError) as e:
            await org_client._update_fork_pr_approval_policy("org", {"approval_policy": "first_time_contributors"})
        assert "fork PR approval policy" in str(e)

    async def test_update_workflow_settings_with_approval_policy(self):
        policy = {"approval_policy": "all_external_contributors"}

        async def mock_update(org, data):
            assert org == "org"
            assert data == policy

        org_client = OrgClient(None)
        org_client._update_fork_pr_approval_policy = mock_update

        await org_client.update_workflow_settings("org", policy)

    async def test_update_workflow_settings_without_approval_policy(self):
        policy = {}

        async def mock_update(org, data): ...

        org_client = OrgClient(None)
        org_client._update_fork_pr_approval_policy = pretend.call_recorder(mock_update)

        await org_client.update_workflow_settings("org", policy)

        assert not org_client._update_fork_pr_approval_policy.calls

    async def test_get_workflow_settings_includes_fork_pr_approval_policy(self):
        policy = {"approval_policy": "all_external_contributors"}

        async def mock_request(method, url):
            return {"enabled_repositories": "none"}

        async def mock_get(org):
            assert org == "org"
            return policy

        mock_requester = pretend.stub(request_json=mock_request)
        mock_restapi = pretend.stub(requester=mock_requester)
        org_client = OrgClient(mock_restapi)
        org_client._get_fork_pr_approval_policy = mock_get

        result = await org_client.get_workflow_settings("org")

        # Assert result includes the approval policy
        assert set(policy.items()).issubset(result.items())
