#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest import mock

import pytest

from otterdog.webapp import webhook
from otterdog.webapp.webhook import on_push_received


def _actor(login: str) -> dict:
    return {"login": login, "id": 1, "node_id": "N", "type": "Organization"}


def _push(owner: str, repo_name: str, ref: str = "refs/heads/main", installation_id: int | None = None) -> dict:
    data = {
        "ref": ref,
        "before": "before-sha",
        "after": "after-sha",
        "repository": {
            "id": 1,
            "node_id": "R",
            "name": repo_name,
            "full_name": f"{owner}/{repo_name}",
            "private": False,
            "owner": _actor(owner),
            "default_branch": "main",
        },
        "commits": [{"added": [], "modified": ["otterdog.json"], "removed": []}],
        "created": False,
        "deleted": False,
        "forced": False,
        "sender": _actor("someone"),
    }

    if installation_id is not None:
        data["installation"] = {"id": installation_id}
        data["organization"] = {"login": owner, "id": 1, "node_id": "O"}

    return data


@pytest.fixture
def push_app(app, monkeypatch):
    """Runs the background tasks scheduled while handling a push, recording the refreshes of the otterdog config."""

    scheduled = []
    monkeypatch.setattr(app, "add_background_task", lambda func, *args: scheduled.append((func, args)))

    async def run_scheduled():
        for func, args in scheduled:
            await func(*args)

    app.run_scheduled = run_scheduled
    app.refresh_otterdog_config = mock.AsyncMock()
    app.update_installations_from_config = mock.AsyncMock()

    monkeypatch.setattr(webhook, "refresh_otterdog_config", app.refresh_otterdog_config)
    monkeypatch.setattr(webhook, "refresh_global_policies", mock.AsyncMock())
    monkeypatch.setattr(webhook, "refresh_global_blueprints", mock.AsyncMock())
    monkeypatch.setattr(webhook, "update_installations_from_config", app.update_installations_from_config)
    monkeypatch.setattr(webhook, "get_blueprints_status_for_repo", mock.AsyncMock(return_value=[]))
    # the installations sending the pushes do not have the repo of the push as config repo
    monkeypatch.setattr(webhook, "targets_config_repo", mock.AsyncMock(return_value=False))

    return app


async def _receive_push(app, data: dict) -> None:
    async with app.app_context():
        response = await on_push_received(data)
        assert response.status_code == 200
        await app.run_scheduled()


def _config_repo(app) -> tuple[str, str]:
    return app.config["OTTERDOG_CONFIG_OWNER"], app.config["OTTERDOG_CONFIG_REPO"]


async def test_push_to_otterdog_config_repo_updates_installations(push_app):
    await _receive_push(push_app, _push(*_config_repo(push_app)))

    push_app.refresh_otterdog_config.assert_awaited_once_with("after-sha")
    push_app.update_installations_from_config.assert_awaited_once()


async def test_push_to_otterdog_config_repo_received_through_an_installation_updates_installations(push_app):
    # the organization hosting the otterdog config has installed the app, without being defined in the config itself
    await _receive_push(push_app, _push(*_config_repo(push_app), installation_id=42))

    push_app.refresh_otterdog_config.assert_awaited_once_with("after-sha")
    push_app.update_installations_from_config.assert_awaited_once()


async def test_push_to_other_branch_of_otterdog_config_repo_is_ignored(push_app):
    await _receive_push(push_app, _push(*_config_repo(push_app), ref="refs/heads/feature"))

    push_app.refresh_otterdog_config.assert_not_awaited()
    push_app.update_installations_from_config.assert_not_awaited()


async def test_push_to_repo_of_an_installation_does_not_update_installations(push_app):
    await _receive_push(push_app, _push("some-org", ".eclipsefdn", installation_id=42))

    push_app.refresh_otterdog_config.assert_not_awaited()
    push_app.update_installations_from_config.assert_not_awaited()
    webhook.get_blueprints_status_for_repo.assert_awaited_once_with("some-org", ".eclipsefdn")
