#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any, Self
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
from quart import session

from otterdog.webapp.auth import routes
from otterdog.webapp.db import service


class _Response:
    def __init__(self, status: int, data: dict[str, Any]):
        self.status = status
        self.ok = status < 400
        self._data = data

    async def json(self) -> dict[str, Any]:
        return self._data

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        return None


class _HttpSession:
    """
    Answers every request with the same response and records the requests.
    """

    def __init__(self, response: _Response):
        self.response = response
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs) -> _Response:
        self.requests.append(("POST", url, kwargs))
        return self.response

    def get(self, url: str, **kwargs) -> _Response:
        self.requests.append(("GET", url, kwargs))
        return self.response


@pytest.fixture
def oauth_app(app):
    app.config["GITHUB_CLIENT_ID"] = "client-id"
    app.config["GITHUB_CLIENT_SECRET"] = "client-secret"
    return app


@pytest.fixture
def github(monkeypatch):
    """
    Stubs the requests to GitHub, the database and the login of the user.
    """

    stubs = mock.MagicMock()
    stubs.retrieve_access_token = mock.AsyncMock(return_value="oauth-token")
    stubs.retrieve_github_user = mock.AsyncMock(
        return_value={"node_id": "node-id", "login": "octocat", "email": "octocat@example.org"}
    )
    stubs.save_user = mock.AsyncMock()

    monkeypatch.setattr(routes, "_retrieve_access_token", stubs.retrieve_access_token)
    monkeypatch.setattr(routes, "_retrieve_github_user", stubs.retrieve_github_user)
    monkeypatch.setattr(routes, "_retrieve_eclipse_user", lambda _: None)
    monkeypatch.setattr(routes, "login_user", stubs.login_user)
    monkeypatch.setattr(service, "get_user", mock.AsyncMock(return_value=None))
    monkeypatch.setattr(service, "save_user", stubs.save_user)
    return stubs


async def test_login_redirects_to_github_with_a_state_kept_in_the_session(oauth_app):
    async with oauth_app.test_request_context("/github"):
        response = await routes.login_github()
        state = session[routes._OAUTH_STATE_KEY]

    location = urlparse(response.location)
    assert response.status_code == 302
    assert f"{location.scheme}://{location.netloc}{location.path}" == routes._GITHUB_AUTHORIZE_URL
    assert parse_qs(location.query) == {"client_id": ["client-id"], "state": [state]}


async def test_login_uses_a_new_state_every_time(oauth_app):
    states = []
    for _ in range(2):
        async with oauth_app.test_request_context("/github"):
            await routes.login_github()
            states.append(session[routes._OAUTH_STATE_KEY])

    assert states[0] != states[1]


async def test_authorized_logs_in_the_github_user(oauth_app, github):
    async with oauth_app.test_request_context("/github/authorized?code=the-code&state=the-state"):
        session[routes._OAUTH_STATE_KEY] = "the-state"
        response = await routes.authorized()
        pending_state = session.get(routes._OAUTH_STATE_KEY)

    assert response.status_code == 302
    assert pending_state is None
    github.retrieve_access_token.assert_awaited_once_with(mock.ANY, "the-code")
    github.retrieve_github_user.assert_awaited_once_with(mock.ANY, "oauth-token")
    assert github.save_user.await_args.args[0].username == "octocat"
    (user,), _ = github.login_user.call_args
    assert user.auth_id == "node-id"


@pytest.mark.parametrize(
    "stored_state, query",
    [
        (None, "code=the-code&state=the-state"),
        ("the-state", "code=the-code"),
        ("the-state", "code=the-code&state=forged-state"),
        ("the-state", "code=the-code&state=th%C3%A9-state"),
        ("the-state", "state=the-state"),
    ],
    ids=["no-pending-authorization", "no-state", "unexpected-state", "non-ascii-state", "no-code"],
)
async def test_authorized_rejects_an_unexpected_callback(oauth_app, github, stored_state, query):
    async with oauth_app.test_request_context(f"/github/authorized?{query}"):
        if stored_state is not None:
            session[routes._OAUTH_STATE_KEY] = stored_state

        response = await routes.authorized()
        pending_state = session.get(routes._OAUTH_STATE_KEY)

    assert response.status_code == 302
    assert pending_state is None
    github.retrieve_access_token.assert_not_awaited()
    github.login_user.assert_not_called()


async def test_authorized_does_not_log_in_without_access_token(oauth_app, github):
    github.retrieve_access_token.return_value = None

    async with oauth_app.test_request_context("/github/authorized?code=the-code&state=the-state"):
        session[routes._OAUTH_STATE_KEY] = "the-state"
        response = await routes.authorized()

    assert response.status_code == 302
    github.retrieve_github_user.assert_not_awaited()
    github.login_user.assert_not_called()


async def test_retrieve_access_token_exchanges_the_code(oauth_app):
    http_session = _HttpSession(_Response(200, {"access_token": "oauth-token", "token_type": "bearer"}))

    async with oauth_app.app_context():
        access_token = await routes._retrieve_access_token(http_session, "the-code")  # type: ignore[arg-type]

    assert access_token == "oauth-token"
    ((method, url, kwargs),) = http_session.requests
    assert (method, url) == ("POST", routes._GITHUB_ACCESS_TOKEN_URL)
    assert kwargs["data"] == {"client_id": "client-id", "client_secret": "client-secret", "code": "the-code"}
    assert kwargs["headers"] == {"Accept": "application/json"}


@pytest.mark.parametrize(
    "response",
    [
        # GitHub reports an invalid or expired code with a successful response
        _Response(200, {"error": "bad_verification_code"}),
        _Response(502, {}),
    ],
    ids=["error", "http-error"],
)
async def test_retrieve_access_token_fails(oauth_app, response):
    async with oauth_app.app_context():
        access_token = await routes._retrieve_access_token(_HttpSession(response), "the-code")  # type: ignore[arg-type]

    assert access_token is None


async def test_retrieve_github_user_uses_the_access_token():
    http_session = _HttpSession(_Response(200, {"node_id": "node-id"}))

    account_info = await routes._retrieve_github_user(http_session, "oauth-token")  # type: ignore[arg-type]

    assert account_info == {"node_id": "node-id"}
    ((method, url, kwargs),) = http_session.requests
    assert (method, url) == ("GET", routes._GITHUB_USER_URL)
    assert kwargs["headers"]["Authorization"] == "Bearer oauth-token"


async def test_retrieve_github_user_fails():
    account_info = await routes._retrieve_github_user(_HttpSession(_Response(401, {})), "oauth-token")  # type: ignore[arg-type]

    assert account_info is None
