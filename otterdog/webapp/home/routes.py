#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from jinja2 import TemplateNotFound
from quart import current_app, redirect, render_template, request, url_for

from otterdog.utils import associate_by_key
from otterdog.webapp.db.service import (
    get_active_organizations,
    get_configurations,
    get_organizations,
    get_tasks,
)
from otterdog.webapp.tasks.fetch_config import FetchConfigTask

from . import blueprint


@blueprint.route("/")
def route_default():
    return redirect(url_for(".index"))


@blueprint.route("/index.html")
async def index():
    orgs = await get_organizations()
    configs = await get_configurations()
    configs_by_key = associate_by_key(configs, lambda x: x.github_id)
    return await render_template(
        "home/index.html", segment="index", org_count=len(orgs), organizations=orgs, configurations=configs_by_key
    )


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
    return {}, 200


@blueprint.route("/init")
async def init():
    from otterdog.webapp.db.service import update_installations

    await update_installations()

    for org in await get_active_organizations():
        current_app.add_background_task(FetchConfigTask(org.installation_id, org.github_id, org.config_repo))

    return {}, 200


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
