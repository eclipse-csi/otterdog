#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from datetime import UTC, datetime

import pytest

from otterdog.webapp.db import service
from otterdog.webapp.db.models import ApplyStatus, PullRequestId, PullRequestModel, PullRequestStatus
from otterdog.webapp.webhook.github_models import PullRequest

_REF = {
    "label": "org:main",
    "ref": "main",
    "sha": "da122b78dcfe316ce78997cef66771a3407ee236",
    "user": {"login": "org", "id": 1, "node_id": "O_1", "type": "Organization"},
    "repo": {
        "id": 1,
        "node_id": "R_1",
        "name": ".eclipsefdn",
        "full_name": "org/.eclipsefdn",
        "private": False,
        "default_branch": "main",
        "owner": {"login": "org", "id": 1, "node_id": "O_1", "type": "Organization"},
    },
}


def _pull_request(state: str, updated_at: str, merged_at: str | None = None) -> PullRequest:
    return PullRequest.model_validate(
        {
            "id": 1,
            "node_id": "PR_1",
            "number": 25,
            "state": state,
            "locked": False,
            "title": "Require one approving review",
            "draft": False,
            "user": {"login": "author", "id": 2, "node_id": "U_2", "type": "User"},
            "author_association": "MEMBER",
            "created_at": "2026-09-29T22:31:28Z",
            "updated_at": updated_at,
            "closed_at": merged_at,
            "merged_at": merged_at,
            "head": _REF,
            "base": _REF,
        }
    )


def _naive_utc(*args: int) -> datetime:
    # mongo returns naive datetimes in UTC
    return datetime(*args, tzinfo=UTC).replace(tzinfo=None)


def _merged_model() -> PullRequestModel:
    return PullRequestModel(
        id=PullRequestId(org_id="org", repo_name=".eclipsefdn", pull_request=25),
        draft=False,
        status=PullRequestStatus.MERGED,
        apply_status=ApplyStatus.COMPLETED,
        created_at=_naive_utc(2026, 9, 29, 22, 31, 28),
        updated_at=_naive_utc(2026, 9, 29, 22, 32, 10),
        closed_at=_naive_utc(2026, 9, 29, 22, 32, 10),
        merged_at=_naive_utc(2026, 9, 29, 22, 32, 10),
    )


@pytest.fixture
def stored(monkeypatch):
    model = _merged_model()

    async def find_pull_request(owner, repo, number):
        return model

    async def update_pull_request(pr_model):
        pass

    monkeypatch.setattr(service, "find_pull_request", find_pull_request)
    monkeypatch.setattr(service, "update_pull_request", update_pull_request)
    return model


async def test_stale_snapshot_does_not_reopen_merged_pull_request(stored):
    # snapshot taken when the PR was opened, saved by a long-running task after the merge
    stale = _pull_request("open", "2026-09-29T22:31:28Z")

    result = await service.update_or_create_pull_request("org", ".eclipsefdn", stale, in_sync=False)

    assert result.status == PullRequestStatus.MERGED
    assert result.merged_at == _naive_utc(2026, 9, 29, 22, 32, 10)
    assert result.updated_at == _naive_utc(2026, 9, 29, 22, 32, 10)
    # task specific results are still recorded
    assert result.in_sync is False


async def test_newer_snapshot_updates_pull_request(stored):
    stored.status = PullRequestStatus.CLOSED
    stored.merged_at = None

    reopened = _pull_request("open", "2026-09-29T23:00:00Z")

    result = await service.update_or_create_pull_request("org", ".eclipsefdn", reopened)

    assert result.status == PullRequestStatus.OPEN
    assert result.closed_at is None
