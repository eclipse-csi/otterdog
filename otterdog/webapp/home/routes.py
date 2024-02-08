#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from jinja2 import TemplateNotFound
from quart import make_response, redirect, render_template, request, url_for

from otterdog.webapp.db.service import (
    get_organization_count,
    get_organizations,
    get_tasks,
)

from . import blueprint


@blueprint.route("/")
def route_default():
    return redirect(url_for(".index"))


@blueprint.route("/index.html")
async def index():
    org_count = await get_organization_count()
    return await render_template("home/index.html", segment="index", org_count=org_count)


@blueprint.route("/organizations.html")
async def organizations():
    orgs = await get_organizations()
    return await render_template("home/organizations.html", segment="organizations", organizations=orgs)


@blueprint.route("/tasks.html")
async def tasks():
    latest_tasks = await get_tasks(100)
    return await render_template("home/tasks.html", segment="tasks", tasks=latest_tasks)


@blueprint.route("/health")
async def health():
    return await make_response({}, 200)


@blueprint.route("/init")
async def init():
    from otterdog.webapp.db.service import update_organization_configs

    await update_organization_configs()
    return await make_response({}, 200)


@blueprint.route("/<template>")
async def route_template(template):
    try:
        if not template.endswith(".html"):
            template += ".html"

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return await render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return await render_template("home/page-404.html"), 404

    except:  # noqa: E722
        return await render_template("home/page-500.html"), 500


# Helper - Extract current page name from request
def get_segment(request):
    try:
        segment = request.path.split("/")[-1]

        if segment == "":
            segment = "index"

        return segment

    except:  # noqa: E722
        return None
