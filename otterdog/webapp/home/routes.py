#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import os.path
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

from otterdog.jsonnet import JsonnetConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import PrettyFormatter, associate_by_key
from otterdog.webapp.db.service import (
    get_active_installations,
    get_configuration_by_github_id,
    get_configuration_by_project_name,
    get_configurations,
    get_installation_by_project_name,
    get_installations,
    get_merged_pull_requests_count,
    get_open_or_incomplete_pull_requests,
    get_open_or_incomplete_pull_requests_count,
    get_statistics,
    get_tasks,
)
from otterdog.webapp.tasks import get_organization_config
from otterdog.webapp.utils import get_temporary_base_directory

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
    from otterdog.webapp.db.service import get_policies

    github_organization = GitHubOrganization.from_model_data(config.config)
    policies = [x.model_dump() for x in await get_policies(config.github_id)]

    return await render_home_template(
        "organization.html",
        project_name=config.project_name,
        github_id=config.github_id,
        config=github_organization,
        policies=policies,
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


@blueprint.route("/projects/<project_name>/defaults")
async def defaults(project_name: str):
    import aiofiles

    installation = await get_installation_by_project_name(project_name)
    if installation is None:
        return await render_template("home/page-404.html"), 404

    default_elements = []

    base_dir = get_temporary_base_directory()
    async with aiofiles.tempfile.TemporaryDirectory(dir=base_dir) as work_dir:
        org_config = await get_organization_config(installation, "", base_dir, work_dir)

        jsonnet_config = org_config.jsonnet_config
        await jsonnet_config.init_template()

        default_elements.append(
            _get_snippet(
                jsonnet_config,
                "org",
                "GitHub Organization",
                f"{jsonnet_config.create_org}('<github-id>')",
                "settings",
            )
        )

        elements = [
            ("org-webhook", "Organization Webhook", f"{jsonnet_config.create_org_webhook}('<url>')"),
            ("org-secret", "Organization Secret", f"{jsonnet_config.create_org_secret}('<name>')"),
            ("org-variable", "Organization Variable", f"{jsonnet_config.create_org_variable}('<name>')"),
            (
                "org-custom-property",
                "Organization Custom Property",
                f"{jsonnet_config.create_org_custom_property}('<name>')",
            ),
            ("repo-webhook", "Repository Webhook", f"{jsonnet_config.create_repo_webhook}('<url>')"),
            ("repo-secret", "Repository Secret", f"{jsonnet_config.create_repo_secret}('<name>')"),
            ("repo-variable", "Repository Variable", f"{jsonnet_config.create_repo_variable}('<name>')"),
            ("environment", "Environment", f"{jsonnet_config.create_environment}('<name>')"),
            ("bpr", "Branch Protection Rule", f"{jsonnet_config.create_branch_protection_rule}('<pattern>')"),
            ("repo-ruleset", "Repository Ruleset", f"{jsonnet_config.create_repo_ruleset}('<name>')"),
            ("ruleset-pull-request", "Pull Request Settings", f"{jsonnet_config.create_pull_request}()"),
            ("ruleset-status-check", "Status Check Settings", f"{jsonnet_config.create_status_checks}()"),
            ("ruleset-merge-queue", "Merge Queue Settings", f"{jsonnet_config.create_merge_queue}()"),
        ]

        for element_id, name, function in elements:
            default_elements.append(_get_snippet(jsonnet_config, element_id, name, function))

    return await render_home_template(
        "defaults.html",
        project_name=project_name,
        default_elements=default_elements,
    )


def _get_snippet(
    jsonnet_config: JsonnetConfig,
    element_id: str,
    name: str,
    function: str,
    key: str | None = None,
) -> dict[str, Any]:
    data = _evaluate_default(jsonnet_config, function)
    if key is not None:
        data = {key: data[key]}

    return {
        "id": element_id,
        "name": name,
        "content": f"orgs.{function} = {_format_model(data)}",
    }


def _format_model(data) -> str:
    return PrettyFormatter().format(data)


def _evaluate_default(jsonnet_config: JsonnetConfig, function: str) -> dict[str, Any]:
    from otterdog.utils import jsonnet_evaluate_snippet

    try:
        snippet = f"(import '{jsonnet_config.template_file}').{function}"
        return jsonnet_evaluate_snippet(snippet)
    except RuntimeError as ex:
        raise RuntimeError(f"failed to evaluate snippet: {ex}") from ex


@blueprint.route("/projects/<project_name>/playground")
async def playground(project_name: str):
    import aiofiles

    installation = await get_installation_by_project_name(project_name)
    if installation is None:
        return await render_template("home/page-404.html"), 404

    jsonnet_files = []

    base_dir = get_temporary_base_directory()
    async with aiofiles.tempfile.TemporaryDirectory(dir=base_dir) as work_dir:
        org_config = await get_organization_config(installation, "", base_dir, work_dir)

        jsonnet_config = org_config.jsonnet_config
        await jsonnet_config.init_template()

        async for jsonnet_file in jsonnet_config.jsonnet_template_files():
            async with aiofiles.open(jsonnet_file) as f:
                filename = os.path.basename(jsonnet_file)
                file_id = os.path.splitext(filename)[0]
                jsonnet_files.append(
                    {
                        "id": file_id,
                        "filename": filename,
                        "content": await f.read(),
                    }
                )

    return await render_home_template(
        "playground.html",
        project_name=project_name,
        jsonnet_files=jsonnet_files,
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


@blueprint.route("/<template>")
async def route_template(template: str):
    try:
        endpoint = template.rstrip(".html") if template.endswith(".html") else template

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
    # TODO: cache project navigation in db instead of dynamically generating it for each request
    installations = await get_active_installations()

    navigation = {}

    for installation in installations:
        if installation.project_name is None:
            continue

        levels = installation.project_name.split(".")

        top_level = levels[0]

        # if the project_name is a tlp, e.g. ee4j, add a second level with the same name
        # to support multiple projects under the same tlp, e.g. ee4j and ee4j.jakartaee-platform,
        # which will be transformed to ee4j.ee4j.
        if len(levels) == 1:
            levels.append(top_level)

        curr = navigation.get(top_level, {})
        remainder = "".join(levels[1:])
        curr.update({remainder: installation})
        navigation[top_level] = curr

    return navigation


async def render_home_template(template_name: str, **context: Any) -> str:
    return await render_template(
        f"home/{template_name}",
        segments=get_segments(request),
        projects=await get_project_navigation(),
        **context,
    )
