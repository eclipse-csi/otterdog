#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import secrets
from logging import getLogger
from typing import Any
from urllib.parse import urlencode

import aiohttp
from quart import current_app, redirect, render_template, request, session, url_for
from quart_auth import current_user, login_user, logout_user

from otterdog.webapp.db.models import UserModel

from . import User, blueprint

logger = getLogger(__name__)

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"

# session key of the state of a pending authorization on GitHub
_OAUTH_STATE_KEY = "github_oauth_state"

# Login


@blueprint.route("/login")
async def login_view():
    if not await current_user.is_authenticated:
        return await render_template("auth/login.html")
    return redirect(url_for("home_blueprint.index"))


@blueprint.route("/github")
async def login_github():
    # GitHub sends the state back unchanged, the callback only accepts the one stored
    # in the session of the user, which protects the login against cross-site request forgery
    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE_KEY] = state

    params = {"client_id": current_app.config["GITHUB_CLIENT_ID"], "state": state}
    return redirect(f"{_GITHUB_AUTHORIZE_URL}?{urlencode(params)}")


@blueprint.route("/logout")
async def logout():
    logout_user()
    return redirect(url_for("home_blueprint.index"))


@blueprint.route("/github/authorized")
async def authorized():
    next_url = url_for("home_blueprint.index")

    # the state is only valid for a single authorization
    expected_state = session.pop(_OAUTH_STATE_KEY, None)
    state = request.args.get("state")
    code = request.args.get("code")

    if (
        expected_state is None
        or state is None
        or not secrets.compare_digest(state.encode(), expected_state.encode())
        or code is None
    ):
        logger.warning("rejecting GitHub authorization callback: missing or unexpected state or code")
        return redirect(next_url)

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as http_session:
        oauth_token = await _retrieve_access_token(http_session, code)
        account_info = None if oauth_token is None else await _retrieve_github_user(http_session, oauth_token)

    if account_info is not None:
        node_id = account_info["node_id"]
        username = account_info["login"]
        email = account_info["email"]

        async def update_user():
            from otterdog.webapp.db.service import get_user, save_user

            user_model = await get_user(node_id)
            if user_model is None:
                user_model = UserModel(node_id=node_id, username=username, email=email)
                await save_user(user_model)

            # update eclipse specific data
            eclipse_userdata = _retrieve_eclipse_user(username)
            if eclipse_userdata is not None:
                eclipse_user = eclipse_userdata["name"]
                full_name = eclipse_userdata["full_name"]

                user_model.full_name = full_name

                project_data = _retrieve_eclipse_projects(eclipse_user)
                if project_data is not None:
                    projects = list(project_data.keys())
                    user_model.projects = projects

                await save_user(user_model)

        await update_user()

        user = User(node_id)
        login_user(user)

    return redirect(next_url)


async def _retrieve_access_token(http_session: aiohttp.ClientSession, code: str) -> str | None:
    data = {
        "client_id": current_app.config["GITHUB_CLIENT_ID"],
        "client_secret": current_app.config["GITHUB_CLIENT_SECRET"],
        "code": code,
    }

    async with http_session.post(
        _GITHUB_ACCESS_TOKEN_URL, data=data, headers={"Accept": "application/json"}
    ) as response:
        if not response.ok:
            logger.warning("failed to retrieve GitHub access token: HTTP %d", response.status)
            return None

        token_data = await response.json()

    # GitHub reports an invalid or expired code with a successful response
    access_token = token_data.get("access_token")
    if access_token is None:
        logger.warning("failed to retrieve GitHub access token: %s", token_data.get("error"))

    return access_token


async def _retrieve_github_user(http_session: aiohttp.ClientSession, oauth_token: str) -> dict[str, Any] | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {oauth_token}",
    }

    async with http_session.get(_GITHUB_USER_URL, headers=headers) as response:
        if not response.ok:
            logger.warning("failed to retrieve GitHub user: HTTP %d", response.status)
            return None

        return await response.json()


def _retrieve_eclipse_user(github_id: str) -> dict[str, Any] | None:
    from requests import get

    response = get(f"https://api.eclipse.org/github/profile/{github_id}", timeout=10)

    if response.status_code == 200:
        return response.json()
    else:
        return None


def _retrieve_eclipse_projects(eclipse_user: str) -> dict[str, Any] | None:
    from requests import get

    response = get(f"https://api.eclipse.org/account/profile/{eclipse_user}/projects", timeout=10)

    if response.status_code == 200:
        return response.json()
    else:
        return None
