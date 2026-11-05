#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The latest change of the configuration of an organization, stored with it when it is fetched."""

import contextlib
from datetime import UTC, datetime
from unittest import mock

import aiofiles
import aiohttp
import pytest
from pretend import stub

from otterdog.webapp.tasks import fetch_config
from otterdog.webapp.tasks.fetch_config import latest_change


def _rest_api(get_latest_commit_for_path):
    return stub(commit=stub(get_latest_commit_for_path=get_latest_commit_for_path))


async def test_the_latest_change_is_the_latest_commit_of_the_configuration():
    async def get_latest_commit_for_path(org_id, repo_name, path):
        assert (org_id, repo_name, path) == ("org", ".eclipsefdn", "otterdog/org.jsonnet")
        return {"sha": "abc123", "commit": {"committer": {"date": "2026-11-04T15:48:04Z"}}}

    change = await latest_change(_rest_api(get_latest_commit_for_path), "org", ".eclipsefdn", "otterdog/org.jsonnet")

    assert change == ("abc123", datetime(2026, 11, 4, 15, 48, 4, tzinfo=UTC))


async def test_the_latest_change_is_unknown_without_commit():
    async def get_latest_commit_for_path(org_id, repo_name, path):
        return None

    assert await latest_change(_rest_api(get_latest_commit_for_path), "org", "repo", "path") == (None, None)


@pytest.mark.parametrize(
    "error",
    [RuntimeError("failed retrieving the latest commit"), TimeoutError(), aiohttp.ClientConnectionError("reset")],
)
async def test_the_latest_change_is_unknown_when_github_fails_without_failing_the_fetch(error):
    async def get_latest_commit_for_path(org_id, repo_name, path):
        raise error

    assert await latest_change(_rest_api(get_latest_commit_for_path), "org", "repo", "path") == (None, None)


async def test_the_latest_change_is_unknown_with_an_unexpected_date():
    async def get_latest_commit_for_path(org_id, repo_name, path):
        return {"sha": "abc123", "commit": {"committer": {"date": "yesterday"}}}

    assert await latest_change(_rest_api(get_latest_commit_for_path), "org", "repo", "path") == (None, None)


@pytest.fixture
def fetch(monkeypatch, tmp_path):
    """A fetch of the configuration of an organization, recording the calls to GitHub in their order."""
    calls = []
    saved = []

    async def get_latest_commit_for_path(org_id, repo_name, path):
        calls.append(("latest commit", path))
        return fetch.commit

    async def fetch_config_from_github(rest_api, org_id, owner, repo, filename, ref=None):
        calls.append(("content", ref))
        async with aiofiles.open(filename, "w") as file:
            await file.write("{}")
        return "blob-sha"

    async def get_default_branch(org_id, repo_name):
        return "main"

    async def save_config(config):
        saved.append(config)

    async def save_statistics(statistics):
        pass

    rest_api = stub(
        commit=stub(get_latest_commit_for_path=get_latest_commit_for_path),
        repo=stub(get_default_branch=get_default_branch),
    )
    org_config = stub(
        name="technology.csi",
        config_repo=".eclipsefdn",
        jsonnet_config=stub(org_config_file=str(tmp_path / "org.jsonnet"), org_dir=str(tmp_path)),
    )

    @contextlib.asynccontextmanager
    async def get_organization_config(self, initialize_template=True):
        yield org_config

    monkeypatch.setattr("otterdog.webapp.tasks.get_rest_api_for_installation", mock.AsyncMock(return_value=rest_api))
    monkeypatch.setattr(fetch_config.FetchConfigTask, "get_organization_config", get_organization_config)
    monkeypatch.setattr(fetch_config, "fetch_config_from_github", fetch_config_from_github)
    monkeypatch.setattr(fetch_config, "jsonnet_evaluate_file", lambda file, import_base_dir: {"settings": {}})
    monkeypatch.setattr(fetch_config.GitHubOrganization, "from_model_data", lambda data: stub())
    monkeypatch.setattr(fetch_config, "get_organization_statistics", lambda *args: stub())
    monkeypatch.setattr(fetch_config, "save_config", save_config)
    monkeypatch.setattr(fetch_config, "save_statistics", save_statistics)

    fetch.commit = None
    fetch.calls = calls
    fetch.saved = saved
    return fetch


def _task():
    return fetch_config.FetchConfigTask(installation_id=1, org_id="eclipse-csi", repo_name=".eclipsefdn")


async def test_the_configuration_is_read_at_the_commit_of_its_latest_change(fetch):
    fetch.commit = {"sha": "abc123", "commit": {"committer": {"date": "2026-11-04T15:48:04Z"}}}

    await _task()._execute()

    # the content of the commit, not of the default branch, which a change pushed in between would have moved
    assert fetch.calls == [("latest commit", "otterdog/eclipse-csi.jsonnet"), ("content", "abc123")]
    [config] = fetch.saved
    assert (config.commit_sha, config.sha) == ("abc123", "blob-sha")


async def test_the_configuration_is_read_from_the_default_branch_when_its_latest_change_is_unknown(fetch):
    await _task()._execute()

    assert fetch.calls == [("latest commit", "otterdog/eclipse-csi.jsonnet"), ("content", None)]
    [config] = fetch.saved
    assert (config.commit_sha, config.committed_at) == (None, None)
