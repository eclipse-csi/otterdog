#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from quart import redirect, render_template, url_for
from quart_auth import current_user, login_user, logout_user

from otterdog.webapp import oauth_github
from otterdog.webapp.db.models import UserModel

from . import User, blueprint

# Login


@blueprint.route("/login")
async def login_view():
    if not await current_user.is_authenticated:
        return await render_template("auth/login.html")
    return redirect(url_for("home_blueprint.index"))


@blueprint.route("/github")
async def login_github():
    return oauth_github.authorize()


@blueprint.route("/logout")
async def logout():
    logout_user()
    return redirect(url_for("home_blueprint.index"))


@blueprint.route("/github/authorized")
@oauth_github.authorized_handler
async def authorized(oauth_token):
    next_url = url_for("home_blueprint.index")
    if oauth_token is None:
        return redirect(next_url)

    from requests import get

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {oauth_token}",
    }

    response = get("https://api.github.com/user", headers=headers)
    if response.ok:
        account_info = response.json()
        node_id = account_info["node_id"]
        username = account_info["login"]
        email = account_info["email"]

        async def update_user():
            from otterdog.webapp.db.service import get_user, save_user

            user_model = await get_user(node_id)
            if user_model is None:
                user_model = UserModel(node_id=node_id, username=username, email=email)
                await save_user(user_model)

            assert user_model is not None

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


def _retrieve_eclipse_user(github_id: str) -> dict[str, Any] | None:
    from requests import get

    response = get(f"https://api.eclipse.org/github/profile/{github_id}")

    if response.status_code == 200:
        return response.json()
    else:
        return None


def _retrieve_eclipse_projects(eclipse_user: str) -> dict[str, Any] | None:
    from requests import get

    response = get(f"https://api.eclipse.org/account/profile/{eclipse_user}/projects")

    if response.status_code == 200:
        return response.json()
    else:
        return None
