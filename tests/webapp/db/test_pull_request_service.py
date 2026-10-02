#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
from datetime import UTC, datetime
from unittest import mock

import pytest
from pymongo.errors import DuplicateKeyError

from otterdog.webapp.db import service
from otterdog.webapp.db.models import ApplyStatus, PullRequestModel, PullRequestStatus
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


class _FakeCollection:
    """In-memory collection supporting the queries used for pull requests."""

    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.before_insert = None
        self.before_update = None
        self.duplicate_key_errors = 0

    async def insert_one(self, doc):
        if self.before_insert is not None:
            await self.before_insert()

        key = repr(doc["_id"])
        if key in self.docs:
            self.duplicate_key_errors += 1
            raise DuplicateKeyError("duplicate key")
        self.docs[key] = dict(doc)

    async def update_one(self, update_filter, update):
        if self.before_update is not None:
            await self.before_update(update_filter)

        doc = self.docs.get(repr(update_filter["_id"]))
        if doc is None:
            return
        condition = update_filter.get("updated_at")
        if condition is not None and not doc["updated_at"] <= condition["$lte"]:
            return
        doc.update(update["$set"])


@pytest.fixture
def collection(monkeypatch):
    fake = _FakeCollection()

    async def find_pull_request(owner, repo, number):
        doc = fake.docs.get(repr({"org_id": owner, "repo_name": repo, "pull_request": number}))
        return None if doc is None else PullRequestModel.model_validate_doc(doc)

    engine = mock.Mock()
    engine.get_collection.return_value = fake
    monkeypatch.setattr(type(service.mongo), "odm", mock.PropertyMock(return_value=engine))
    monkeypatch.setattr(service, "find_pull_request", find_pull_request)
    return fake


_OPENED = _pull_request("open", "2026-09-29T22:31:28Z")
_MERGED = _pull_request("closed", "2026-09-29T22:32:10Z", "2026-09-29T22:32:10Z")
_MERGED_AT = datetime(2026, 9, 29, 22, 32, 10, tzinfo=UTC)


async def test_stale_snapshot_does_not_reopen_merged_pull_request(collection):
    await service.update_or_create_pull_request("org", ".eclipsefdn", _MERGED, apply_status=ApplyStatus.COMPLETED)

    # snapshot taken when the PR was opened, saved by a long-running task after the merge
    result = await service.update_or_create_pull_request("org", ".eclipsefdn", _OPENED, in_sync=False)

    assert result.status == PullRequestStatus.MERGED
    assert result.merged_at == _MERGED_AT
    assert result.updated_at == _MERGED_AT
    assert result.apply_status == ApplyStatus.COMPLETED
    # task specific results are still recorded
    assert result.in_sync is False


async def test_stale_snapshot_saved_concurrently_does_not_reopen_merged_pull_request(collection):
    await service.update_or_create_pull_request("org", ".eclipsefdn", _OPENED)

    stale_read_done = asyncio.Event()
    merge_stored = asyncio.Event()

    async def before_update(update_filter):
        # suspend the task holding the outdated snapshot after it read the pull request
        # and until the merge has been stored by another task
        if asyncio.current_task() is stale and not merge_stored.is_set():
            stale_read_done.set()
            await merge_stored.wait()

    collection.before_update = before_update

    stale = asyncio.create_task(service.update_or_create_pull_request("org", ".eclipsefdn", _OPENED, in_sync=False))
    await asyncio.wait_for(stale_read_done.wait(), timeout=5)

    await service.update_or_create_pull_request("org", ".eclipsefdn", _MERGED, apply_status=ApplyStatus.COMPLETED)
    merge_stored.set()

    result = await stale

    assert result.status == PullRequestStatus.MERGED
    assert result.merged_at == _MERGED_AT
    assert result.in_sync is False


async def test_concurrent_creation_of_pull_request(collection):
    # both tasks first observe the pull request as absent, then race to insert it
    barrier = asyncio.Barrier(2)

    async def before_insert():
        await asyncio.wait_for(barrier.wait(), timeout=5)

    collection.before_insert = before_insert

    await asyncio.gather(
        service.update_or_create_pull_request("org", ".eclipsefdn", _OPENED, valid=True),
        service.update_or_create_pull_request("org", ".eclipsefdn", _OPENED, in_sync=True),
    )

    result = await service.find_pull_request("org", ".eclipsefdn", 25)

    assert len(collection.docs) == 1
    # the task losing the race recovered from the duplicate key error
    assert collection.duplicate_key_errors == 1
    assert result is not None
    assert result.status == PullRequestStatus.OPEN
    assert result.valid is True
    assert result.in_sync is True


async def test_newer_snapshot_updates_pull_request(collection):
    closed = _pull_request("closed", "2026-09-29T22:40:00Z")
    reopened = _pull_request("open", "2026-09-29T23:00:00Z")

    await service.update_or_create_pull_request("org", ".eclipsefdn", closed)
    result = await service.update_or_create_pull_request("org", ".eclipsefdn", reopened)

    assert result.status == PullRequestStatus.OPEN
    assert result.closed_at is None
