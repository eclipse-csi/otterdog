#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from .conftest import GitHubProviderTestKit

ORG_ID = "test-org"
REPO_NAME = "test-repo"
PR_NUMBER = 123


def pull_request(github: GitHubProviderTestKit):
    return github.provider.pull_request(ORG_ID, REPO_NAME, PR_NUMBER)


async def test_get_data_returns_pull_request_payload(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/pulls/{PR_NUMBER}",
        response_json={"number": PR_NUMBER, "state": "open"},
    )

    data = await pull_request(github).get_data()

    assert data == {"number": PR_NUMBER, "state": "open"}


async def test_request_reviews(github: GitHubProviderTestKit):
    github.http.expect(
        "POST",
        f"/repos/{ORG_ID}/{REPO_NAME}/pulls/{PR_NUMBER}/requested_reviewers",
        request_json={"reviewers": ["alice"], "team_reviewers": ["core"]},
        response_status=201,
        response_text="created",
    )

    result = await pull_request(github).request_reviews(reviewers=["alice"], team_reviewers=["core"])

    assert result is True


async def test_merge_pull_request_returns_api_response(github: GitHubProviderTestKit):
    github.http.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/pulls/{PR_NUMBER}/merge",
        request_json={"merge_method": "squash"},
        response_json={"merged": True, "sha": "1234"},
    )

    response = await pull_request(github).merge_pull_request("squash")

    assert response == {"merged": True, "sha": "1234"}


async def test_merge_rebase(github: GitHubProviderTestKit):
    github.http.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/pulls/{PR_NUMBER}/merge",
        request_json={"merge_method": "rebase"},
        response_json={"merged": True},
    )

    merged = await pull_request(github).merge(merge_method="rebase")

    assert merged is True


async def test_merge_squash(github: GitHubProviderTestKit):
    github.http.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/pulls/{PR_NUMBER}/merge",
        request_json={"merge_method": "squash", "commit_message": "chore: merge"},
        response_json={"merged": True},
    )

    merged = await pull_request(github).merge(commit_message="chore: merge", merge_method="squash")

    assert merged is True
