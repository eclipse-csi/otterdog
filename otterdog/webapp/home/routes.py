#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

from quart import (
    current_app,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from quart_auth import current_user, login_required
from werkzeug.routing import BuildError

from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import associate_by_key
from otterdog.webapp.db.service import (
    get_active_installations,
    get_configuration_by_github_id,
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
async def route_default():
    return redirect(url_for(".index"))


@blueprint.route("/robots.txt")
@blueprint.route("/favicon.ico")
async def static_from_root():
    return await send_from_directory(current_app.static_folder, request.path[1:])


@blueprint.route("/index")
async def index():
    installations = await get_installations()
    configurations = await get_configurations()
    configurations_by_key = associate_by_key(configurations, lambda x: x.github_id)
    stats = await get_statistics()

    two_factor_data = [
        stats.total_projects - stats.projects_with_two_factor_auth_enforced,
        stats.projects_with_two_factor_auth_enforced,
    ]

    two_factor_percentage = float(stats.projects_with_two_factor_auth_enforced) / float(stats.total_projects) * 100.0

    secret_scanning_data = [
        stats.active_repos - stats.repos_with_secret_scanning - stats.repos_with_secret_scanning_and_protection,
        stats.repos_with_secret_scanning,
        stats.repos_with_secret_scanning_and_protection,
    ]

    secret_scanning_percentage = (
        float(stats.repos_with_secret_scanning + stats.repos_with_secret_scanning_and_protection)
        / float(stats.active_repos)
        * 100.0
    )

    dependabot_data = [
        stats.active_repos - stats.repos_with_dependabot_alerts - stats.repos_with_dependabot_security_updates,
        stats.repos_with_dependabot_alerts,
        stats.repos_with_dependabot_security_updates,
    ]

    dependabot_percentage = (
        float(stats.repos_with_dependabot_alerts + stats.repos_with_dependabot_security_updates)
        / float(stats.active_repos)
        * 100.0
    )

    branch_protection_data = [
        stats.active_repos - stats.repos_with_branch_protection,
        stats.repos_with_branch_protection,
    ]

    branch_protection_percentage = float(stats.repos_with_branch_protection) / float(stats.active_repos) * 100.0

    private_vulnerability_reporting_data = [
        stats.active_repos - stats.repos_with_private_vulnerability_reporting,
        stats.repos_with_private_vulnerability_reporting,
    ]

    private_vulnerability_reporting_percentage = (
        float(stats.repos_with_private_vulnerability_reporting) / float(stats.active_repos) * 100.0
    )

    return await render_home_template(
        "index.html",
        open_pull_request_count=await get_open_or_incomplete_pull_requests_count(),
        merged_pull_request_count=await get_merged_pull_requests_count(),
        installations=installations,
        configurations=configurations_by_key,
        total_repository_count=stats.total_repos,
        active_repository_count=stats.active_repos,
        archived_repository_count=stats.archived_repos,
        two_factor_data=json.dumps(two_factor_data),
        two_factor_percentage=two_factor_percentage,
        secret_scanning_data=json.dumps(secret_scanning_data),
        secret_scanning_percentage=secret_scanning_percentage,
        dependabot_data=json.dumps(dependabot_data),
        dependabot_percentage=dependabot_percentage,
        branch_protection_data=json.dumps(branch_protection_data),
        branch_protection_percentage=branch_protection_percentage,
        private_vulnerability_reporting_data=json.dumps(private_vulnerability_reporting_data),
        private_vulnerability_reporting_percentage=private_vulnerability_reporting_percentage,
    )


@blueprint.route("/myprojects")
@login_required
async def myprojects():
    projects = set(await current_user.projects)

    installations = list(filter(lambda x: x.project_name in projects, await get_installations()))
    configurations = await get_configurations()
    configurations_by_key = associate_by_key(configurations, lambda x: x.github_id)
    return await render_home_template(
        "projects.html",
        title="My Projects",
        installations=installations,
        configurations=configurations_by_key,
    )


@blueprint.route("/allprojects")
async def allprojects():
    installations = await get_installations()
    configurations = await get_configurations()
    configurations_by_key = associate_by_key(configurations, lambda x: x.github_id)
    return await render_home_template(
        "projects.html",
        title="All Projects",
        installations=installations,
        configurations=configurations_by_key,
    )


@blueprint.route("/query")
async def query():
    from otterdog.webapp.api.graphql import type_defs

    return await render_home_template(
        "query.html",
        graphql_schema=type_defs,
    )


@blueprint.route("/organizations/<org_name>")
async def organization(org_name: str):
    config = await get_configuration_by_github_id(org_name)
    if config is None:
        return await render_template("home/page-404.html"), 404
    else:
        return redirect(url_for(".project", project_name=config.project_name))


@blueprint.route("/projects/<project_name>")
async def project(project_name: str):
    config = await get_configuration_by_project_name(project_name)

    if config is None:
        return await render_template("home/page-404.html"), 404

    from otterdog.models.github_organization import GitHubOrganization

    github_organization = GitHubOrganization.from_model_data(config.config)

    return await render_home_template(
        "organization.html",
        project_name=config.project_name,
        github_id=config.github_id,
        config=github_organization,
        secret_scanning_data=json.dumps(_get_secret_scanning_data(github_organization)),
        branch_protection_data=json.dumps(_get_branch_protection_data(github_organization)),
    )


def _get_secret_scanning_data(org: GitHubOrganization) -> list[int]:
    alert_mode = 0
    protection_mode = 0
    not_configured = 0

    for repo in org.repositories:
        if repo.archived is True:
            continue

        if repo.secret_scanning_push_protection == "enabled":
            protection_mode += 1
        elif repo.secret_scanning == "enabled":
            alert_mode += 1
        else:
            not_configured += 1

    return [not_configured, alert_mode, protection_mode]


def _get_branch_protection_data(org: GitHubOrganization) -> list[int]:
    protected = 0
    not_protected = 0

    for repo in org.repositories:
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


@blueprint.errorhandler(401)
async def error_unauthorized(error):
    return await render_template("home/page-401.html"), 401


@blueprint.errorhandler(Exception)
async def error_exception(error):
    import traceback

    traceback.print_exception(error)
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

        # if the project_name is a tlp, e.g. ee4j, add a second level with the same name
        # to support multiple projects under the same tlp, e.g. ee4j and ee4j.jakartaee-platform,
        # which will be transformed to ee4j.ee4j.
        if len(levels) == 1:
            levels.append(levels[0])

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
