#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from flask_dance.consumer import oauth_authorized  # type: ignore
from flask_dance.contrib.github import github, make_github_blueprint  # type: ignore
from quart import current_app
from quart_auth import AuthUser, login_user

from otterdog.webapp.db.models import UserModel

blueprint = make_github_blueprint(scope="user")


class User(AuthUser):
    def __init__(self, auth_id):
        super().__init__(auth_id)
        self._resolved = False
        self._username = None
        self._fullname = None
        self._email = None
        self._projects = []

    async def _resolve(self):
        if not self._resolved:
            from otterdog.webapp.db.service import get_user

            user = await get_user(self.auth_id)
            if user is not None:
                self._username = user.username
                self._fullname = user.full_name
                self._email = user.email
                self._projects = user.projects.copy()

                self._resolved = True

    @property
    async def username(self):
        await self._resolve()
        return self._username

    @property
    async def fullname(self):
        await self._resolve()
        return self._fullname

    @property
    async def email(self):
        await self._resolve()
        return self._email

    @property
    async def projects(self):
        await self._resolve()
        return self._projects


@oauth_authorized.connect_via(blueprint)
def github_logged_in(blueprint, token):
    info = github.get("/user")

    if info.ok:
        account_info = info.json()
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

        current_app.add_background_task(update_user)

        user = User(node_id)
        login_user(user)


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
