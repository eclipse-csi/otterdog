#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import hashlib
import hmac
import json
import logging

import pytest
from quart import Quart

from otterdog.webapp.webhook.github_webhook import GitHubWebhook, _describe_event

SECRET = b"secret"
ENDPOINT = "/github-webhook/receive"


@pytest.fixture
def webhook_app():
    app = Quart(__name__)
    app.config["GITHUB_WEBHOOK_ENDPOINT"] = ENDPOINT
    app.config["GITHUB_WEBHOOK_SECRET"] = SECRET

    webhook = GitHubWebhook()
    webhook.init_app(app)
    return app, webhook


async def _post(app, event_type: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(SECRET, body, hashlib.sha1).hexdigest()
    headers = {
        "X-Hub-Signature": f"sha1={signature}",
        "X-Github-Event": event_type,
        "X-Github-Delivery": "delivery-1",
        "content-type": "application/json",
    }
    return await app.test_client().post(ENDPOINT, data=body, headers=headers)


async def test_null_field_does_not_prevent_processing(webhook_app, caplog):
    app, webhook = webhook_app
    received = []

    @webhook.hook("pull_request")
    async def on_pull_request(data):
        received.append(data)

    payload = {"action": "opened", "sender": None, "pull_request": {"number": 1}, "repository": None}
    with caplog.at_level(logging.WARNING):
        response = await _post(app, "pull_request", payload)

    assert response.status_code == 204
    assert received == [payload]
    assert "could not format webhook delivery delivery-1 for event 'pull_request' (TypeError" in caplog.text
    assert "null fields=['repository', 'sender']" in caplog.text


async def test_missing_field_is_only_logged_at_debug_level(webhook_app, caplog):
    app, _ = webhook_app

    with caplog.at_level(logging.INFO):
        response = await _post(app, "membership", {"action": "added", "sender": {"login": "user"}})

    assert response.status_code == 204
    assert "could not format" not in caplog.text
    assert "membership (delivery-1)" in caplog.text


async def test_event_is_described(webhook_app, caplog):
    app, _ = webhook_app

    payload = {
        "action": "opened",
        "sender": {"login": "user"},
        "pull_request": {"number": 1},
        "repository": {"full_name": "org/repo"},
    }
    with caplog.at_level(logging.INFO):
        response = await _post(app, "pull_request", payload)

    assert response.status_code == 204
    assert "user opened pull #1 in org/repo (delivery-1)" in caplog.text


async def test_hook_failure_is_logged_with_event_context(webhook_app, caplog):
    app, webhook = webhook_app

    @webhook.hook("issue_comment")
    async def on_issue_comment(_data):
        raise RuntimeError("boom")

    payload = {"action": "created", "sender": {"login": "user"}, "repository": {"full_name": "org/repo"}}
    with caplog.at_level(logging.ERROR):
        response = await _post(app, "issue_comment", payload)

    assert response.status_code == 500
    assert "failed to process webhook delivery delivery-1 for event 'issue_comment'" in caplog.text
    assert "on_issue_comment" in caplog.text
    assert "repository='org/repo'" in caplog.text


async def test_invalid_signature_is_logged(webhook_app, caplog):
    app, _ = webhook_app

    headers = {
        "X-Hub-Signature": "sha1=invalid",
        "X-Github-Event": "ping",
        "X-Github-Delivery": "delivery-1",
        "content-type": "application/json",
    }
    with caplog.at_level(logging.WARNING):
        response = await app.test_client().post(ENDPOINT, data=b"{}", headers=headers)

    assert response.status_code == 400
    assert "rejecting webhook delivery delivery-1: invalid signature" in caplog.text


def test_describe_event_handles_unexpected_payloads():
    assert _describe_event([]) == "payload of type 'list'"
    assert "repository=None" in _describe_event({"repository": "not-a-dict"})
