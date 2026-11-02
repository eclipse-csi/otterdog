#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from otterdog.webapp.db.models import PullRequestId, PullRequestModel, PullRequestStatus
from otterdog.webapp.tasks.merge_pull_request import MergePullRequestTask

_ORG = "org"
_REPO = ".eclipsefdn"
_NUMBER = 25
_AUTHOR = "author"

_TEAMS = {
    "lead": [{"name": "committers"}, {"name": "project-leads"}],
    "committer": [{"name": "committers"}],
}

_REF = {
    "label": "org:main",
    "ref": "main",
    "sha": "da122b78dcfe316ce78997cef66771a3407ee236",
    "user": {"login": "org", "id": 1, "node_id": "O_1", "type": "Organization"},
    "repo": None,
}

_PULL_REQUEST = {
    "id": 1,
    "node_id": "PR_1",
    "number": _NUMBER,
    "state": "open",
    "locked": False,
    "title": "Update description",
    "draft": False,
    "user": {"login": _AUTHOR, "id": 2, "node_id": "U_2", "type": "User"},
    "author_association": "MEMBER",
    "created_at": "2026-10-30T06:58:57Z",
    "updated_at": "2026-11-02T07:33:19Z",
    "head": _REF,
    "base": _REF,
}


def _review(state: str, login: str | None) -> dict:
    user = None if login is None else {"login": login}
    return {"state": state, "user": user}


def _pr_model(has_required_approvals: bool | None) -> PullRequestModel:
    return PullRequestModel(
        id=PullRequestId(org_id=_ORG, repo_name=_REPO, pull_request=_NUMBER),
        draft=False,
        status=PullRequestStatus.OPEN,
        valid=True,
        supports_auto_merge=True,
        author_can_auto_merge=False,
        has_required_approvals=has_required_approvals,
        created_at=datetime(2026, 10, 30, tzinfo=UTC),
        updated_at=datetime(2026, 11, 2, tzinfo=UTC),
    )


@pytest.fixture
async def github(app, monkeypatch):
    """
    Stubs the GitHub apis used to check approvals, along with the stored pull request.
    """

    rest_api = SimpleNamespace(
        pull_request=SimpleNamespace(
            get_pull_request=AsyncMock(return_value=_PULL_REQUEST),
            get_reviews=AsyncMock(return_value=[]),
        ),
        issue=SimpleNamespace(create_comment=AsyncMock()),
        team=SimpleNamespace(get_team_slugs=AsyncMock(return_value=["committers", "project-leads"])),
        close=AsyncMock(),
    )

    async def get_team_membership(org_id, user_login):
        return _TEAMS[user_login]

    graphql_api = SimpleNamespace(get_team_membership=AsyncMock(side_effect=get_team_membership), close=AsyncMock())

    async def update_or_create_pull_request(owner, repo, pull_request, has_required_approvals=None):
        return _pr_model(has_required_approvals)

    db = SimpleNamespace(
        find_pull_request=AsyncMock(return_value=_pr_model(False)),
        update_or_create_pull_request=AsyncMock(side_effect=update_or_create_pull_request),
    )

    monkeypatch.setattr("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api))
    monkeypatch.setattr("otterdog.webapp.tasks.get_graphql_api_for_installation", AsyncMock(return_value=graphql_api))
    monkeypatch.setattr("otterdog.webapp.tasks.merge_pull_request.find_pull_request", db.find_pull_request)
    monkeypatch.setattr(
        "otterdog.webapp.tasks.merge_pull_request.update_or_create_pull_request", db.update_or_create_pull_request
    )
    monkeypatch.setattr("otterdog.webapp.db.service.get_installation_by_github_id", AsyncMock(return_value=None))

    async with app.app_context():
        app.config["GITHUB_APPROVAL_TEAMS"] = "project-leads$"
        app.config["GITHUB_ADMIN_TEAMS"] = "otterdog-admins"
        yield SimpleNamespace(rest_api=rest_api, graphql_api=graphql_api, db=db)


def _merge_task(requested_by: str = _AUTHOR) -> MergePullRequestTask:
    return MergePullRequestTask(1, _ORG, _REPO, _NUMBER, requested_by)


async def test_merge_rechecks_approval_not_recorded_by_review_event(github):
    # the update triggered by the approval of the lead failed, the stored state is outdated
    github.rest_api.pull_request.get_reviews.return_value = [
        _review("APPROVED", "committer"),
        _review("APPROVED", "lead"),
    ]

    assert await _merge_task()._pre_execute() is True

    github.db.update_or_create_pull_request.assert_awaited_once()
    assert github.db.update_or_create_pull_request.await_args.kwargs["has_required_approvals"] is True
    github.rest_api.issue.create_comment.assert_not_awaited()


async def test_merge_requested_by_lead_rechecks_approval_not_recorded_by_review_event(github):
    github.rest_api.pull_request.get_reviews.return_value = [_review("APPROVED", "lead")]

    assert await _merge_task(requested_by="lead")._pre_execute() is True

    assert github.db.update_or_create_pull_request.await_args.kwargs["has_required_approvals"] is True
    github.rest_api.issue.create_comment.assert_not_awaited()


async def test_merge_refused_without_approval_of_eligible_team(github):
    github.rest_api.pull_request.get_reviews.return_value = [
        _review("APPROVED", "committer"),
        _review("COMMENTED", "lead"),
    ]

    assert await _merge_task()._pre_execute() is False

    assert github.db.update_or_create_pull_request.await_args.kwargs["has_required_approvals"] is False
    comment = github.rest_api.issue.create_comment.await_args.kwargs["body"]
    assert "No approval from a member of `team 'project-leads'`" in comment


async def test_merge_does_not_recheck_recorded_approval(github):
    github.db.find_pull_request.return_value = _pr_model(True)

    assert await _merge_task()._pre_execute() is True

    github.rest_api.pull_request.get_reviews.assert_not_awaited()
    github.db.update_or_create_pull_request.assert_not_awaited()


async def test_approval_check_ignores_reviews_of_deleted_accounts(github):
    github.rest_api.pull_request.get_reviews.return_value = [
        _review("APPROVED", None),
        _review("APPROVED", "lead"),
    ]

    assert await _merge_task().has_required_approvals(_ORG, _REPO, _NUMBER) is True
    github.graphql_api.get_team_membership.assert_awaited_once_with(_ORG, "lead")
