#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from quart import Blueprint, Response
from quart_auth import AuthUser, current_user

from otterdog.webapp.utils import is_cache_control_enabled

blueprint = Blueprint("auth_blueprint", __name__, url_prefix="")


@blueprint.after_request
async def after_request_func(response: Response):
    if is_cache_control_enabled() and response.status_code == 200:
        if await current_user.is_authenticated:
            response.cache_control.no_cache = True
        else:
            response.cache_control.max_age = 60
            response.cache_control.public = True
            response.vary = "Cookie"

    return response


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
