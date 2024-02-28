#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from quart import current_app, redirect, render_template, request, url_for
from werkzeug.routing import BuildError

from otterdog.utils import associate_by_key
from otterdog.webapp.db.service import (
    get_active_installations,
    get_configuration_by_project_name,
    get_configurations,
    get_installations,
    get_merged_pull_requests_count,
    get_open_or_incomplete_pull_requests,
    get_open_or_incomplete_pull_requests_count,
    get_statistics,
    get_tasks,
)
from otterdog.webapp.tasks.fetch_all_pull_requests import FetchAllPullRequestsTask
from otterdog.webapp.tasks.fetch_config import FetchConfigTask

from . import blueprint


@blueprint.route("/")
def route_default():
    return redirect(url_for(".index"))


@blueprint.route("/index")
async def index():
    installations = await get_installations()
    configurations = await get_configurations()
    configurations_by_key = associate_by_key(configurations, lambda x: x.github_id)
    statistics = await get_statistics()
    return await render_home_template(
        "index.html",
        open_pull_request_count=await get_open_or_incomplete_pull_requests_count(),
        merged_pull_request_count=await get_merged_pull_requests_count(),
        installations=installations,
        configurations=configurations_by_key,
        total_repository_count=statistics[1],
    )


@blueprint.route("/projects/<project_name>")
async def project(project_name: str):
    config = await get_configuration_by_project_name(project_name)

    if config is None:
        return await render_template("home/page-404.html"), 404

    from otterdog.models.github_organization import GitHubOrganization

    github_organization = GitHubOrganization.from_model_data(config.config)

    return await render_home_template(
        "organization.html",
        project_name=project_name,
        github_id=config.github_id,
        config=github_organization,
    )


@blueprint.route("/projects/<project_name>/repos/<repo_name>")
async def repository(project_name: str, repo_name: str):
    config = await get_configuration_by_project_name(project_name)

    if config is None:
        return await render_template("home/page-404.html"), 404

    from otterdog.models.github_organization import GitHubOrganization

    github_organization = GitHubOrganization.from_model_data(config.config)

    repo_config = next(filter(lambda x: x.name == repo_name, github_organization.repositories), None)
    if repo_config is None:
        return await render_template("home/page-404.html"), 404

    return await render_home_template(
        "repository.html",
        project_name=project_name,
        github_id=config.github_id,
        config=github_organization,
        repo_name=repo_name,
        repo_config=repo_config,
    )


@blueprint.route("/admin/organizations")
async def organizations():
    return await render_home_template(
        "organizations.html",
        installations=await get_installations(),
    )


@blueprint.route("/admin/pullrequests")
async def pullrequests():
    open_pull_requests = await get_open_or_incomplete_pull_requests()

    return await render_home_template(
        "pullrequests.html",
        open_pull_requests=open_pull_requests,
    )


@blueprint.route("/admin/tasks")
async def tasks():
    latest_tasks = await get_tasks(100)
    return await render_home_template(
        "tasks.html",
        tasks=latest_tasks,
    )


@blueprint.route("/health")
async def health():
    return {}, 200


@blueprint.route("/init")
async def init():
    from otterdog.webapp.db.service import update_installations

    await update_installations()

    for installation in await get_active_installations():
        current_app.add_background_task(
            FetchConfigTask(
                installation.installation_id,
                installation.github_id,
                installation.config_repo,
            )
        )
        current_app.add_background_task(
            FetchAllPullRequestsTask(
                installation.installation_id,
                installation.github_id,
                installation.config_repo,
            )
        )

    return {}, 200


@blueprint.route("/<template>")
async def route_template(template: str):
    try:
        if template.endswith(".html"):
            endpoint = template.rstrip(".html")
        else:
            endpoint = template

        return redirect(url_for(f".{endpoint}"))
    except BuildError:
        return await render_template("home/page-404.html"), 404
    except:  # noqa: E722
        return await render_template("home/page-500.html"), 500


# Helper - Extract current page name from request
def get_segments(request):
    try:
        segments = request.path.split("/")

        if len(segments) == 1 and segments[0] == "":
            segments = ["index"]

        segments = list(filter(lambda x: x, segments))
        return segments

    except:  # noqa: E722
        return None


async def get_project_navigation():
    installations = await get_active_installations()

    navigation = {}

    for installation in installations:
        levels = installation.project_name.split(".")
        if len(levels) == 1:
            navigation[levels[0]] = installation
        else:
            curr = navigation.get(levels[0], {})
            remainder = "".join(levels[1:])
            curr.update({remainder: installation})
            navigation[levels[0]] = curr

    return navigation


async def render_home_template(template_name: str, **context: Any) -> str:
    return await render_template(
        f"home/{template_name}",
        segments=get_segments(request),
        projects=await get_project_navigation(),
        **context,
    )
