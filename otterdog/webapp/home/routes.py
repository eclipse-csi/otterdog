#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

from quart import redirect, render_template, request, url_for
from werkzeug.routing import BuildError

from otterdog.models.github_organization import GitHubOrganization
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
    update_data_for_installation,
    update_installations_from_config,
)
from otterdog.webapp.utils import refresh_otterdog_config

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
        secret_scanning_data=json.dumps(_get_secret_scanning_data(github_organization)),
        branch_protection_data=json.dumps(_get_branch_protection_data(github_organization)),
    )


def _get_secret_scanning_data(organization: GitHubOrganization) -> list[int]:
    alert_mode = 0
    protection_mode = 0
    not_configured = 0

    for repo in organization.repositories:
        if repo.archived is True:
            continue

        if repo.secret_scanning_push_protection == "enabled":
            protection_mode += 1
        elif repo.secret_scanning == "enabled":
            alert_mode += 1
        else:
            not_configured += 1

    return [not_configured, alert_mode, protection_mode]


def _get_branch_protection_data(organization: GitHubOrganization) -> list[int]:
    protected = 0
    not_protected = 0

    for repo in organization.repositories:
        if repo.archived is True:
            continue

        if len(repo.rulesets) > 0 or len(repo.branch_protection_rules) > 0:
            protected += 1
        else:
            not_protected += 1

    return [not_protected, protected]


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
    config = await refresh_otterdog_config()
    await update_installations_from_config(config)

    for installation in await get_active_installations():
        await update_data_for_installation(installation)

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
        if installation.project_name is None:
            continue

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
