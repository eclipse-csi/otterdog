#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

# imported through the webhook package, as importing the tasks first runs into an import cycle
from otterdog.webapp.webhook import (  # isort: skip
    CheckConfigurationInSyncTask,
    RetrieveTeamMembershipTask,
    UpdatePullRequestTask,
    ValidatePullRequestTask,
)
from otterdog.providers.github.exception import GitHubException
from otterdog.webapp.db.models import PullRequestId, PullRequestModel, PullRequestStatus
from otterdog.webapp.tasks.auto_merge_comment import AutoMergeCommentTask
from otterdog.webapp.tasks.validate_pull_request import ValidationResult

_ORG = "org"
_REPO = ".otterdog"
_NUMBER = 10
_HEAD = "a" * 40
_PREVIOUS_HEAD = "b" * 40

_VALIDATION_COMMENT = (
    "<!-- Otterdog Comment: validate -->\n"
    "<!-- otterdog:auto-merge-status --><!-- /otterdog:auto-merge-status -->\n"
    "Please find below the validation of the requested configuration changes:\n"
)
_READY_TO_MERGE = "### :rocket: Ready to merge"


class _PullRequestStore:
    """The pull request stored by the webapp, eligible for the auto-merge once its head is validated."""

    def __init__(self) -> None:
        self.draft = False
        self.status = PullRequestStatus.OPEN
        self.fields: dict = {
            "valid": True,
            "supports_auto_merge": True,
            "author_can_auto_merge": True,
            "validated_sha": _HEAD,
        }

    def model(self) -> PullRequestModel:
        return PullRequestModel(
            id=PullRequestId(org_id=_ORG, repo_name=_REPO, pull_request=_NUMBER),
            draft=self.draft,
            status=self.status,
            created_at=datetime(2026, 9, 2, tzinfo=UTC),
            updated_at=datetime(2026, 11, 19, tzinfo=UTC),
            **self.fields,
        )

    async def update_or_create(self, owner, repo, pull_request, **fields) -> PullRequestModel:
        self.draft = pull_request.draft
        self.fields.update({k: v for k, v in fields.items() if v is not None})
        return self.model()

    async def find(self, owner, repo, number) -> PullRequestModel:
        return self.model()


class _Comments:
    """The comments of the pull request on GitHub."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def add(self, body: str, minimized: bool = False) -> str:
        comment_id = f"IC_{len(self.items)}"
        self.items[comment_id] = {"id": comment_id, "body": body, "isMinimized": minimized}
        return comment_id

    async def create(self, org_id, repo_name, number, body) -> dict:
        return {"node_id": self.add(body)}

    async def get(self, comment_id) -> dict | None:
        # lets the tasks running concurrently interleave, as the request to GitHub would
        await asyncio.sleep(0)
        comment = self.items.get(comment_id)
        return dict(comment) if comment is not None else None

    async def update(self, comment_id, body) -> None:
        self.items[comment_id]["body"] = body

    async def list(self, org_id, repo_name, number) -> list[dict]:
        return [dict(comment) for comment in self.items.values()]

    async def minimize(self, comment_id, classifier) -> None:
        self.items[comment_id]["isMinimized"] = True


@pytest.fixture
async def github(app, monkeypatch, fake_redis):
    store = _PullRequestStore()
    comments = _Comments()

    rest_api = SimpleNamespace(
        pull_request=SimpleNamespace(get_pull_request=AsyncMock(return_value={"head": {"sha": _HEAD}})),
        commit=SimpleNamespace(create_commit_status=AsyncMock()),
        issue=SimpleNamespace(create_comment=AsyncMock(side_effect=comments.create)),
        # the author is a member of an approval team
        team=SimpleNamespace(get_membership=AsyncMock(return_value={"state": "active", "role": "member"})),
        close=AsyncMock(),
    )
    graphql_api = SimpleNamespace(
        get_issue_comment=AsyncMock(side_effect=comments.get),
        update_issue_comment=AsyncMock(side_effect=comments.update),
        get_issue_comments=AsyncMock(side_effect=comments.list),
        minimize_comment=AsyncMock(side_effect=comments.minimize),
        get_team_membership=AsyncMock(return_value=[{"name": "project-leads"}]),
        close=AsyncMock(),
    )

    monkeypatch.setattr("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api))
    monkeypatch.setattr("otterdog.webapp.tasks.get_graphql_api_for_installation", AsyncMock(return_value=graphql_api))
    for module in ("validate_pull_request", "check_sync", "update_pull_request", "retrieve_team_membership"):
        monkeypatch.setattr(f"otterdog.webapp.tasks.{module}.update_or_create_pull_request", store.update_or_create)
    monkeypatch.setattr("otterdog.webapp.tasks.auto_merge_comment.find_pull_request", store.find)
    monkeypatch.setattr(
        "otterdog.webapp.tasks.auto_merge_comment.get_teams_matching_approval_pattern",
        AsyncMock(return_value=["project-leads"]),
    )
    monkeypatch.setattr("otterdog.webapp.tasks.auto_merge_comment._LEASE_RETRY_DELAY_IN_SECONDS", 0.01)
    # no per-organization teams, the ones of the configuration apply
    monkeypatch.setattr("otterdog.webapp.db.service.get_installation_by_github_id", AsyncMock(return_value=None))

    async with app.app_context():
        app.config["GITHUB_APPROVAL_TEAMS"] = "project-leads$"
        app.config["GITHUB_ADMIN_TEAMS"] = "otterdog-admins"
        yield SimpleNamespace(store=store, comments=comments, rest_api=rest_api, graphql_api=graphql_api)


def _validated(github, ready_to_merge: bool = False, minimized: bool = False) -> str:
    """Adds the comment of the last validation, as recorded by it."""
    body = _VALIDATION_COMMENT
    if ready_to_merge:
        body = body.replace(
            "<!-- otterdog:auto-merge-status -->", f"<!-- otterdog:auto-merge-status -->\n{_READY_TO_MERGE}\n"
        )
    comment_id = github.comments.add(body, minimized)
    github.store.fields["validation_comment_id"] = comment_id
    return comment_id


def _shows_ready_to_merge(github, comment_id: str | None = None) -> bool:
    comment_id = comment_id or github.store.fields["validation_comment_id"]
    return _READY_TO_MERGE in github.comments.items[comment_id]["body"]


def _pull_request(head_sha: str = _HEAD, draft: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        number=_NUMBER,
        draft=draft,
        head=SimpleNamespace(sha=head_sha),
        user=SimpleNamespace(login="author", type="User"),
        author_association="MEMBER",
    )


def _validation(head_sha: str = _HEAD) -> ValidatePullRequestTask:
    task = ValidatePullRequestTask(1, _ORG, _REPO, _NUMBER)
    task._pull_request = _pull_request(head_sha)
    return task


def _record_scheduled_updates(task) -> list:
    scheduled: list = []
    task.schedule_automerge_task = Mock(side_effect=lambda *args: scheduled.append(args))
    return scheduled


async def _run_scheduled_updates(scheduled: list) -> None:
    for args in scheduled:
        await AutoMergeCommentTask(1, *args)._execute()


async def _update_status() -> None:
    await AutoMergeCommentTask(1, _ORG, _REPO, _NUMBER)._execute()


async def _complete_validation(github, result: ValidationResult, head_sha: str = _HEAD) -> str:
    """Completes a validation that added its comment, returns the id of the comment."""
    task = _validation(head_sha)
    created = await github.rest_api.issue.create_comment(_ORG, _REPO, str(_NUMBER), _VALIDATION_COMMENT)
    task._comment_id = created["node_id"]
    scheduled = _record_scheduled_updates(task)

    await task._update_final_status(result)
    await _run_scheduled_updates(scheduled)
    return task._comment_id


async def _update_pull_request(pull_request: SimpleNamespace, review: SimpleNamespace | None = None) -> None:
    task = UpdatePullRequestTask(1, _ORG, _REPO, pull_request, review=review)
    task.has_required_approvals = AsyncMock(return_value=review is not None and review.state == "approved")
    scheduled = _record_scheduled_updates(task)

    await task._execute()
    await _run_scheduled_updates(scheduled)


def _membership_error(status: int) -> RuntimeError:
    """The error of the REST client when GitHub answers the given status."""
    try:
        raise RuntimeError("failed retrieving membership") from GitHubException("url", status, "body")
    except RuntimeError as ex:
        return ex


# the status in the comment of the last validation


async def test_status_shows_ready_to_merge_when_the_head_is_eligible(github):
    comment_id = _validated(github)

    await _update_status()

    body = github.comments.items[comment_id]["body"]
    assert body.index(_READY_TO_MERGE) < body.index("Please find below the validation")
    assert "/otterdog merge" in body


async def test_status_is_removed_once_a_newer_commit_has_been_pushed(github):
    comment_id = _validated(github, ready_to_merge=True)
    # the validated commit is not the head anymore
    github.rest_api.pull_request.get_pull_request.return_value = {"head": {"sha": _PREVIOUS_HEAD}}

    await _update_status()

    assert github.comments.items[comment_id]["body"] == _VALIDATION_COMMENT


async def test_status_is_not_rewritten_when_unchanged(github):
    _validated(github)
    await _update_status()

    await _update_status()

    github.graphql_api.update_issue_comment.assert_awaited_once()


async def test_status_reflects_the_latest_state_when_updated_concurrently(github):
    _validated(github)
    first_update_started = asyncio.Event()
    get_comment = github.comments.get

    async def get_comment_while_the_approval_is_dismissed(comment_id):
        comment = await get_comment(comment_id)
        if not first_update_started.is_set():
            first_update_started.set()
            # the state changes while the first update is running, e.g. the author leaves the approval team
            github.store.fields["author_can_auto_merge"] = False
            await asyncio.sleep(0.05)
        return comment

    github.graphql_api.get_issue_comment.side_effect = get_comment_while_the_approval_is_dismissed

    async def update_once_the_state_changed():
        # fails rather than hangs if the first update never reads the comment
        await asyncio.wait_for(first_update_started.wait(), timeout=5)
        await _update_status()

    await asyncio.gather(_update_status(), update_once_the_state_changed())

    assert not _shows_ready_to_merge(github)


async def test_status_is_updated_without_redis(github, monkeypatch):
    _validated(github)
    monkeypatch.setattr("otterdog.webapp.lease.get_redis", Mock(side_effect=RuntimeError("redis not available")))

    await _update_status()

    assert _shows_ready_to_merge(github)


async def test_status_is_not_updated_before_the_first_validation(github):
    await _update_status()

    github.rest_api.pull_request.get_pull_request.assert_not_awaited()
    github.graphql_api.update_issue_comment.assert_not_awaited()


async def test_status_of_a_replaced_validation_comment_is_not_updated(github):
    # the comment of a newer validation has been added, its own status is shown once it is recorded
    _validated(github, minimized=True)

    await _update_status()

    github.graphql_api.update_issue_comment.assert_not_awaited()


async def test_comment_of_a_previous_version_without_status_is_not_updated(github):
    comment_id = github.comments.add("<!-- Otterdog Comment: validate -->\nPlease find below the validation")
    github.store.fields["validation_comment_id"] = comment_id

    await _update_status()

    github.graphql_api.update_issue_comment.assert_not_awaited()


# the validation


async def test_validation_shows_the_status_in_its_comment(github):
    comment_id = await _complete_validation(github, ValidationResult(validation_success=True))

    assert github.store.fields["validation_comment_id"] == comment_id
    assert _shows_ready_to_merge(github, comment_id)


async def test_validation_of_a_head_that_is_not_eligible_shows_no_status(github):
    comment_id = await _complete_validation(github, ValidationResult(validation_success=True, includes_deletions=True))

    assert github.comments.items[comment_id]["body"] == _VALIDATION_COMMENT


async def test_failed_validation_keeps_the_status_of_the_previous_one(github):
    # validated before, the validation of the same commit is requested again and fails before replacing the comment
    _validated(github)
    task = _validation()
    scheduled = _record_scheduled_updates(task)

    await task._post_execute(RuntimeError("failed fetching the configuration"))
    await _run_scheduled_updates(scheduled)

    # the stored result still allows /otterdog merge
    assert _shows_ready_to_merge(github)


async def test_validation_hides_the_comments_it_replaces(github):
    previous_validation = _validated(github, ready_to_merge=True)
    legacy_comment = github.comments.add("<!-- Otterdog Comment: automerge -->\n### :rocket: Ready to merge")
    help_comment = github.comments.add("<!-- Otterdog Comment: help -->\nThank you")
    task = _validation()

    await task.minimize_outdated_comments(
        _ORG, _REPO, _NUMBER, "<!-- Otterdog Comment: validate -->", "<!-- Otterdog Comment: automerge -->"
    )

    assert github.comments.items[previous_validation]["isMinimized"] is True
    assert github.comments.items[legacy_comment]["isMinimized"] is True
    assert github.comments.items[help_comment]["isMinimized"] is False


@pytest.mark.parametrize("late_task", ["validation", "sync_check"])
async def test_no_status_is_left_for_a_head_that_is_not_eligible(github, late_task):
    # the previous head was eligible, a commit removing a resource is pushed and its validation is running
    github.store.fields["validated_sha"] = _PREVIOUS_HEAD
    previous_comment = _validated(github, ready_to_merge=True)
    await _update_pull_request(_pull_request(_HEAD))
    assert not _shows_ready_to_merge(github, previous_comment)

    # a task started for the previous head completes in the meantime, e.g. a slow sync check
    if late_task == "validation":
        task = _validation(_PREVIOUS_HEAD)
        scheduled = _record_scheduled_updates(task)
        await task._update_final_status(ValidationResult(validation_success=True))
    else:
        task = CheckConfigurationInSyncTask(1, _ORG, _REPO, _NUMBER)
        task._pull_request = _pull_request(_PREVIOUS_HEAD)
        scheduled = _record_scheduled_updates(task)
        await task._update_final_status(True)
    await _run_scheduled_updates(scheduled)

    comment_id = await _complete_validation(github, ValidationResult(validation_success=True, includes_deletions=True))

    assert not _shows_ready_to_merge(github, previous_comment)
    assert not _shows_ready_to_merge(github, comment_id)


# the sync check, which changes no condition of the auto-merge

# the stored validation is the one of the head, or of a previous one while the head is still being validated
_VALIDATED_SHAS = pytest.mark.parametrize(
    ("validated_sha", "update_scheduled"),
    [(_HEAD, True), (_PREVIOUS_HEAD, False)],
    ids=["head_validated", "head_not_validated_yet"],
)


@_VALIDATED_SHAS
async def test_sync_check_updates_the_status_only_once_the_head_is_validated(github, validated_sha, update_scheduled):
    github.store.fields["validated_sha"] = validated_sha
    task = CheckConfigurationInSyncTask(1, _ORG, _REPO, _NUMBER)
    task._pull_request = _pull_request()
    scheduled = _record_scheduled_updates(task)

    await task._update_final_status(True)

    assert bool(scheduled) is update_scheduled


# the events changing the conditions of the auto-merge


@pytest.mark.parametrize(("review_state", "ready_to_merge"), [("approved", True), ("dismissed", False)])
async def test_review_shows_or_removes_the_status(github, review_state, ready_to_merge):
    # the author needs an approval, the pull request was approved before
    github.store.fields["author_can_auto_merge"] = False
    github.store.fields["has_required_approvals"] = True
    _validated(github, ready_to_merge=review_state == "dismissed")

    await _update_pull_request(_pull_request(), SimpleNamespace(state=review_state))

    assert _shows_ready_to_merge(github) is ready_to_merge


async def test_conversion_to_draft_removes_the_status(github):
    _validated(github, ready_to_merge=True)

    await _update_pull_request(_pull_request(draft=True))

    assert not _shows_ready_to_merge(github)


@pytest.mark.parametrize("status", [PullRequestStatus.CLOSED, PullRequestStatus.MERGED])
async def test_closed_or_merged_pull_request_removes_the_status(github, status):
    _validated(github, ready_to_merge=True)
    github.store.status = status

    await _update_pull_request(_pull_request())

    assert not _shows_ready_to_merge(github)


async def test_draft_validated_on_request_shows_no_status(github):
    github.store.draft = True
    task = _validation()
    task._pull_request.draft = True
    created = await github.rest_api.issue.create_comment(_ORG, _REPO, str(_NUMBER), _VALIDATION_COMMENT)
    task._comment_id = created["node_id"]
    scheduled = _record_scheduled_updates(task)

    await task._update_final_status(ValidationResult(validation_success=True))
    await _run_scheduled_updates(scheduled)

    assert not _shows_ready_to_merge(github)


@pytest.mark.parametrize("author_can_auto_merge", [True, False])
async def test_team_info_updates_the_status_once_the_author_is_known(github, monkeypatch, author_can_auto_merge):
    # the validation completed before the membership of the author was known
    del github.store.fields["author_can_auto_merge"]
    # e.g. shown while the author was still a member
    _validated(github, ready_to_merge=not author_can_auto_merge)
    monkeypatch.setattr(
        "otterdog.webapp.tasks.retrieve_team_membership.contains_eligible_team_for_auto_merge",
        AsyncMock(return_value=author_can_auto_merge),
    )
    task = RetrieveTeamMembershipTask(1, _ORG, _REPO, _NUMBER)
    task._pull_request = _pull_request()
    scheduled = _record_scheduled_updates(task)

    await task._execute()
    await _run_scheduled_updates(scheduled)

    assert _shows_ready_to_merge(github) is author_can_auto_merge


async def test_team_info_fails_when_the_membership_cannot_be_retrieved(github):
    del github.store.fields["author_can_auto_merge"]
    github.rest_api.team.get_membership.side_effect = _membership_error(502)
    task = RetrieveTeamMembershipTask(1, _ORG, _REPO, _NUMBER)
    task._pull_request = _pull_request()
    _record_scheduled_updates(task)

    with pytest.raises(RuntimeError, match="failed retrieving membership"):
        await task._execute()

    # not taken for a user who is not a member
    assert "author_can_auto_merge" not in github.store.fields


# the membership of the author, unknown e.g. if the pull request was opened before the webapp was installed


@pytest.mark.parametrize("member", [True, False])
async def test_validation_retrieves_the_unknown_membership_of_the_author(github, member):
    del github.store.fields["author_can_auto_merge"]
    if not member:
        github.rest_api.team.get_membership.side_effect = _membership_error(404)

    comment_id = await _complete_validation(github, ValidationResult(validation_success=True))

    assert github.store.fields.get("author_can_auto_merge") is member
    assert _shows_ready_to_merge(github, comment_id) is member
    # retrieved without adding the team-info comment
    github.rest_api.issue.create_comment.assert_awaited_once()


async def test_validation_does_not_retrieve_a_known_membership(github):
    github.store.fields["author_can_auto_merge"] = False

    await _complete_validation(github, ValidationResult(validation_success=True))

    github.rest_api.team.get_membership.assert_not_awaited()


async def test_validation_does_not_retrieve_the_membership_of_a_bot(github):
    del github.store.fields["author_can_auto_merge"]
    task = _validation()
    task._pull_request.user.type = "Bot"
    _record_scheduled_updates(task)

    await task._update_final_status(ValidationResult(validation_success=True))

    github.rest_api.team.get_membership.assert_not_awaited()
    assert "author_can_auto_merge" not in github.store.fields


@pytest.mark.parametrize("failing_call", ["membership", "teams"])
async def test_validation_result_is_kept_when_the_membership_cannot_be_retrieved(github, failing_call):
    del github.store.fields["author_can_auto_merge"]
    if failing_call == "membership":
        github.rest_api.team.get_membership.side_effect = _membership_error(502)
    else:
        github.graphql_api.get_team_membership.side_effect = RuntimeError("failed running graphql query")
    task = _validation()
    scheduled = _record_scheduled_updates(task)

    await task._update_final_status(ValidationResult(validation_success=True))

    assert github.rest_api.commit.create_commit_status.await_args.args[3] == "success"
    assert github.store.fields["valid"] is True
    # unknown, retrieved again by the next validation
    assert "author_can_auto_merge" not in github.store.fields
    assert scheduled == [(_ORG, _REPO, _NUMBER)]
