#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import re
from unittest.mock import AsyncMock, patch

import pytest

from otterdog.webapp.webhook import on_issue_comment_received
from otterdog.webapp.webhook.comment_handlers import CommentHandler, CommentScope


class RecordingHandler(CommentHandler):
    def __init__(self, scope: CommentScope, command: str):
        self._scope = scope
        self._command = command
        self.processed: list[str] = []

    @property
    def scope(self) -> CommentScope:
        return self._scope

    def _create_pattern(self):
        return re.compile(rf"/otterdog\s+{self._command}")

    def process(self, match, event) -> None:
        self.processed.append(f"{event.repository.name}#{event.issue.number}")


def _actor(login: str = "alice", actor_type: str = "User") -> dict:
    return {"login": login, "id": 1, "node_id": "U_1", "type": actor_type}


def _payload(body: str, repo_name: str, is_pull_request: bool, sender_type: str = "User") -> dict:
    issue = {
        "number": 7,
        "node_id": "I_7",
        "title": "some issue",
        "state": "open",
        "author_association": "MEMBER",
        "html_url": f"https://github.com/osgi/{repo_name}/issues/7",
    }
    if is_pull_request:
        issue["pull_request"] = {
            "url": f"https://api.github.com/repos/osgi/{repo_name}/pulls/7",
            "html_url": f"https://github.com/osgi/{repo_name}/pull/7",
        }

    return {
        "action": "created",
        "installation": {"id": 42, "node_id": "I_42"},
        "organization": {"login": "osgi", "id": 2, "node_id": "O_2"},
        "sender": _actor(actor_type=sender_type),
        "issue": issue,
        "comment": {
            "id": 100,
            "node_id": "IC_100",
            "user": _actor(actor_type=sender_type),
            "body": body,
            "created_at": "2026-10-02T10:00:00Z",
            "updated_at": "2026-10-02T10:00:00Z",
        },
        "repository": {
            "id": 3,
            "node_id": "R_3",
            "name": repo_name,
            "full_name": f"osgi/{repo_name}",
            "private": False,
            "owner": _actor("osgi", "Organization"),
            "default_branch": "main",
        },
    }


async def _receive(payload: dict, handlers: list[CommentHandler]):
    async def targets_config_repo(repo_name: str, installation_id: int) -> bool:
        return repo_name == ".eclipsefdn"

    with (
        patch("otterdog.webapp.webhook.comment_handlers", handlers),
        patch("otterdog.webapp.webhook.targets_config_repo", AsyncMock(side_effect=targets_config_repo)),
    ):
        await on_issue_comment_received(payload)


@pytest.mark.parametrize(
    "scope, repo_name, is_pull_request, expected",
    [
        (CommentScope.CONFIG_REPO_PULL_REQUEST, ".eclipsefdn", True, True),
        (CommentScope.CONFIG_REPO_PULL_REQUEST, "org.osgi.annotation", True, False),
        (CommentScope.CONFIG_REPO_PULL_REQUEST, ".eclipsefdn", False, False),
        (CommentScope.PULL_REQUEST, "org.osgi.annotation", True, True),
        (CommentScope.PULL_REQUEST, "org.osgi.annotation", False, False),
        (CommentScope.ANY, "org.osgi.annotation", False, True),
        (CommentScope.ANY, ".eclipsefdn", False, True),
    ],
)
async def test_handler_is_invoked_according_to_its_scope(scope, repo_name, is_pull_request, expected):
    handler = RecordingHandler(scope, "recheck")

    await _receive(_payload("/otterdog recheck", repo_name, is_pull_request), [handler])

    assert handler.processed == ([f"{repo_name}#7"] if expected else [])


async def test_only_the_first_matching_handler_runs():
    first = RecordingHandler(CommentScope.ANY, "status")
    second = RecordingHandler(CommentScope.ANY, "status")

    await _receive(_payload("/otterdog status", "org.osgi.annotation", False), [first, second])

    assert first.processed == ["org.osgi.annotation#7"]
    assert second.processed == []


async def test_comments_of_bots_are_ignored():
    handler = RecordingHandler(CommentScope.ANY, "status")

    await _receive(_payload("/otterdog status", "org.osgi.annotation", False, sender_type="Bot"), [handler])

    assert handler.processed == []


async def test_deleted_comments_are_ignored():
    handler = RecordingHandler(CommentScope.ANY, "status")
    payload = _payload("/otterdog status", "org.osgi.annotation", False)
    payload["action"] = "deleted"

    await _receive(payload, [handler])

    assert handler.processed == []
