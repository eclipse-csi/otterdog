#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from quart import Blueprint, Response

from otterdog.webapp.utils import is_cache_control_enabled

blueprint = Blueprint("api_blueprint", __name__, url_prefix="/api")


@blueprint.after_request
async def after_request_func(response: Response):
    if is_cache_control_enabled() and response.status_code == 200:
        response.cache_control.max_age = 60
        response.cache_control.public = True
        response.vary = "Cookie"

    return response
