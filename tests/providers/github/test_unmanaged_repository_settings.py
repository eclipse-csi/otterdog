#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest.mock import AsyncMock, patch

import pretend
import pytest

from otterdog.providers.github import GitHubProvider
from otterdog.providers.github.rest.repo_client import RepoClient


async def test_the_provider_passes_the_unmanaged_settings_when_adding_a_repository():
    add_repo = AsyncMock()
    provider = GitHubProvider(None)
    provider.rest_api = pretend.stub(repo=pretend.stub(add_repo=add_repo))
    provider.unmanaged_repository_settings = frozenset({"topics"})

    await provider.add_repo("org", {"name": "repo"}, None, [], None, False, True)

    assert add_repo.await_args.args[-1] == frozenset({"topics"})


@pytest.mark.parametrize("flow", ["fork", "template"])
async def test_the_data_of_a_created_repository_does_not_include_unmanaged_settings(flow):
    requester = pretend.stub(request_json=AsyncMock(return_value={}))
    repo_client = RepoClient(pretend.stub(requester=requester))
    get_repo_data = AsyncMock(return_value={})

    with (
        patch.object(repo_client, "get_repo_data", get_repo_data),
        patch.object(repo_client, "_attach_code_security_configuration", AsyncMock()),
        patch.object(repo_client, "_remove_already_active_settings"),
        patch.object(repo_client, "_remove_not_configured_code_scanning", AsyncMock()),
        patch.object(repo_client, "update_repo", AsyncMock()),
    ):
        await repo_client.add_repo(
            "org",
            {"name": "repo"},
            "org/template" if flow == "template" else None,
            [],
            "upstream/repo" if flow == "fork" else None,
            False,
            True,
            None,
            frozenset({"topics", "custom_properties"}),
        )

    assert get_repo_data.await_args.args == ("org", "repo", frozenset({"topics", "custom_properties"}))
