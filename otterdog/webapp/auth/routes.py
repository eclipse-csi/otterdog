#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from quart import redirect, render_template, url_for
from quart_auth import Unauthorized, current_user, logout_user

from . import blueprint

# Login


@blueprint.route("/login", methods=["GET", "POST"])
async def login_view():
    if not await current_user.is_authenticated:
        return await render_template("auth/login.html")
    return redirect(url_for("home_blueprint.index"))


@blueprint.route("/logout")
async def logout():
    logout_user()
    return redirect(url_for("home_blueprint.index"))


# Errors


@blueprint.errorhandler(Unauthorized)
async def redirect_to_login(*_: Exception):
    return redirect(url_for(".login"))
