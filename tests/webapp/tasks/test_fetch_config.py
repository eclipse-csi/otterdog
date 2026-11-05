#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The latest change of the configuration of an organization, stored with it when it is fetched."""

from datetime import UTC, datetime

from pretend import stub

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


async def test_the_latest_change_is_unknown_when_github_fails_without_failing_the_fetch():
    async def get_latest_commit_for_path(org_id, repo_name, path):
        raise RuntimeError("failed retrieving the latest commit")

    assert await latest_change(_rest_api(get_latest_commit_for_path), "org", "repo", "path") == (None, None)
