#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import functools
import json
import os.path
import posixpath
import re
from collections.abc import Callable, Coroutine, Mapping, MutableMapping
from importlib.resources import files
from logging import getLogger
from typing import TYPE_CHECKING, Any, TypeVar, cast
from urllib.parse import quote

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

import otterdog
from otterdog import resources
from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.jsonnet import JsonnetConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import PrettyFormatter, associate_by_key, parse_template_url
from otterdog.webapp.db.service import (
    find_scorecard_result,
    get_active_installations,
    get_blueprints,
    get_blueprints_status,
    get_configuration_by_project_name,
    get_configuration_sources,
    get_configurations,
    get_installation_by_github_id,
    get_installation_by_project_name,
    get_installations,
    get_merged_pull_requests_count,
    get_open_or_incomplete_pull_requests_count,
    get_policies_status,
    get_scorecard_results,
    get_statistics,
)
from otterdog.webapp.tasks import get_organization_config
from otterdog.webapp.utils import get_otterdog_config, get_project_base_url, get_temporary_base_directory

from . import blueprint

if TYPE_CHECKING:
    from otterdog.webapp.auth import User

_PAGE_NOT_FOUND = "home/page-404.html"

logger = getLogger(__name__)


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

    two_factor_percentage = (
        float(stats.projects_with_two_factor_auth_enforced) / float(stats.total_projects) * 100.0
        if stats.total_projects > 0
        else 0
    )

    secret_scanning_data = [
        stats.active_repos - stats.repos_with_secret_scanning - stats.repos_with_secret_scanning_and_protection,
        stats.repos_with_secret_scanning,
        stats.repos_with_secret_scanning_and_protection,
    ]

    secret_scanning_percentage = (
        (
            float(stats.repos_with_secret_scanning + stats.repos_with_secret_scanning_and_protection)
            / float(stats.active_repos)
            * 100.0
        )
        if stats.active_repos > 0
        else 0
    )

    dependabot_data = [
        stats.active_repos - stats.repos_with_dependabot_alerts - stats.repos_with_dependabot_security_updates,
        stats.repos_with_dependabot_alerts,
        stats.repos_with_dependabot_security_updates,
    ]

    dependabot_percentage = (
        (
            float(stats.repos_with_dependabot_alerts + stats.repos_with_dependabot_security_updates)
            / float(stats.active_repos)
            * 100.0
        )
        if stats.active_repos > 0
        else 0
    )

    branch_protection_data = [
        stats.active_repos - stats.repos_with_branch_protection,
        stats.repos_with_branch_protection,
    ]

    branch_protection_percentage = (
        float(stats.repos_with_branch_protection) / float(stats.active_repos) * 100.0 if stats.active_repos > 0 else 0
    )

    private_vulnerability_reporting_data = [
        stats.active_repos - stats.repos_with_private_vulnerability_reporting,
        stats.repos_with_private_vulnerability_reporting,
    ]

    private_vulnerability_reporting_percentage = (
        (float(stats.repos_with_private_vulnerability_reporting) / float(stats.active_repos) * 100.0)
        if stats.active_repos > 0
        else 0
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
    installation = await get_installation_by_github_id(org_name)
    if installation is None:
        return await render_template(_PAGE_NOT_FOUND), 404
    else:
        return redirect(url_for(".project", project_name=installation.project_name))


@blueprint.route("/organizations/<org_name>/<path:subpath>")
async def organization_catch_all_redirect(org_name: str, subpath: str):
    installation = await get_installation_by_github_id(org_name)
    if installation is None:
        return await render_template(_PAGE_NOT_FOUND), 404
    else:
        return redirect(url_for(".project", project_name=installation.project_name) + "/" + subpath)


@blueprint.route("/projects/<project_name>")
async def project(project_name: str):
    installation = await get_installation_by_project_name(project_name)
    config = await get_configuration_by_project_name(project_name)

    if config is None or installation is None:
        return await render_template(_PAGE_NOT_FOUND), 404

    from otterdog.models.github_organization import GitHubOrganization
    from otterdog.webapp.db.service import get_policies

    github_organization = GitHubOrganization.from_model_data(config.config)
    policies = [x.model_dump() for x in await get_policies(config.github_id)]
    policies_status = {x.id.policy_type: x.model_dump() for x in await get_policies_status(config.github_id)}
    blueprints = [x.model_dump() for x in await get_blueprints(config.github_id)]

    all_blueprints_status = await get_blueprints_status(config.github_id)
    blueprints_status: dict[str, list[dict]] = {}
    for status in all_blueprints_status:
        blueprint_id = status.id.blueprint_id
        status_list = blueprints_status.setdefault(blueprint_id, [])
        status_list.append(status.model_dump())

    scorecard_results = {m.id.repo_name: m.model_dump() for m in await get_scorecard_results(config.github_id)}

    template = installation.base_template
    template_ref = "N/A"
    if template is not None:
        components = template.rsplit("@", 1)
        if len(components) == 2:
            template_ref = components[1]
    else:
        template = "#"

    base_template = {"url": template, "ref": template_ref}

    return await render_home_template(
        "organization.html",
        project_url=get_project_base_url() + config.project_name,
        project_name=config.project_name,
        github_id=config.github_id,
        base_template=base_template,
        config=github_organization,
        policies=policies,
        policies_status=policies_status,
        blueprints=blueprints,
        blueprints_status=blueprints_status,
        secret_scanning_data=json.dumps(_get_secret_scanning_data(github_organization)),
        branch_protection_data=json.dumps(_get_branch_protection_data(github_organization)),
        scorecard_results=scorecard_results,
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
    import contextlib

    import aiofiles

    installation = await get_installation_by_project_name(project_name)
    if installation is None:
        return await render_template(_PAGE_NOT_FOUND), 404

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
                f"{jsonnet_config.create_org}('<project-name>', '<github-id>')",
                "settings",
            )
        )

        elements = [
            ("org-role", "Organization Role", f"{jsonnet_config.create_org_role}('<name>')"),
            ("org-ruleset", "Organization Ruleset", f"{jsonnet_config.create_org_ruleset}('<name>')"),
            ("org-team", "Organization Team", f"{jsonnet_config.create_org_team}('<name>')"),
            ("org-secret", "Organization Secret", f"{jsonnet_config.create_org_secret}('<name>')"),
            (
                "org-dependabot-secret",
                "Organization Dependabot Secret",
                f"{jsonnet_config.create_org_dependabot_secret}('<name>')",
            ),
            (
                "org-codespaces-secret",
                "Organization Codespaces Secret",
                f"{jsonnet_config.create_org_codespaces_secret}('<name>')",
            ),
            ("org-variable", "Organization Variable", f"{jsonnet_config.create_org_variable}('<name>')"),
            ("org-webhook", "Organization Webhook", f"{jsonnet_config.create_org_webhook}('<url>')"),
            (
                "org-custom-property",
                "Organization Custom Property",
                f"{jsonnet_config.create_org_custom_property}('<name>')",
            ),
            ("repo", "Repository", f"{jsonnet_config.create_repo}('<name>')"),
            ("repo-secret", "Repository Secret", f"{jsonnet_config.create_repo_secret}('<name>')"),
            (
                "repo-dependabot-secret",
                "Repository Dependabot Secret",
                f"{jsonnet_config.create_repo_dependabot_secret}('<name>')",
            ),
            (
                "repo-codespaces-secret",
                "Repository Codespaces Secret",
                f"{jsonnet_config.create_repo_codespaces_secret}('<name>')",
            ),
            ("repo-variable", "Repository Variable", f"{jsonnet_config.create_repo_variable}('<name>')"),
            ("repo-webhook", "Repository Webhook", f"{jsonnet_config.create_repo_webhook}('<url>')"),
            ("environment", "Environment", f"{jsonnet_config.create_environment}('<name>')"),
            ("environment-secret", "Environment Secret", f"{jsonnet_config.create_environment_secret}('<name>')"),
            ("environment-variable", "Environment Variable", f"{jsonnet_config.create_environment_variable}('<name>')"),
            ("bpr", "Branch Protection Rule", f"{jsonnet_config.create_branch_protection_rule}('<pattern>')"),
            ("repo-ruleset", "Repository Ruleset", f"{jsonnet_config.create_repo_ruleset}('<name>')"),
            ("ruleset-pull-request", "Pull Request Settings", f"{jsonnet_config.create_pull_request}()"),
            ("ruleset-status-check", "Status Check Settings", f"{jsonnet_config.create_status_checks}()"),
            ("ruleset-merge-queue", "Merge Queue Settings", f"{jsonnet_config.create_merge_queue}()"),
        ]

        for element_id, name, function in elements:
            # if evaluation fails, the default config might not define this resource
            with contextlib.suppress(RuntimeError):
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


# the example template of otterdog, which the configuration guides of the documentation are validated with,
# it is shipped with the otterdog package
EXAMPLE_TEMPLATE = "example"
_EXAMPLE_TEMPLATE_DIR = os.path.join(os.path.dirname(otterdog.__file__), "resources", "defaults")
_EXAMPLE_TEMPLATE_FILE = "otterdog-defaults.libsonnet"


@blueprint.route("/playground")
async def global_playground():
    otterdog_config = await get_otterdog_config()

    try:
        base_template = otterdog_config.default_base_template
    except RuntimeError:
        return await render_template(_PAGE_NOT_FOUND), 404

    # the global playground can also use the example template of otterdog instead of the one of the instance
    example_template = await _example_template()
    templates = None
    if example_template is not None:
        selected = request.args.get("template") == EXAMPLE_TEMPLATE
        templates = [
            {"value": "", "label": "This instance", "selected": not selected},
            {"value": EXAMPLE_TEMPLATE, "label": "Otterdog example", "selected": selected},
        ]
        if selected:
            return await _render_playground(example_template, None, templates=templates, example=True)

    return await _render_playground(await _default_template(otterdog_config, base_template), None, templates=templates)


@blueprint.route("/projects/<project_name>/playground")
async def playground(project_name: str):
    import aiofiles

    installation = await get_installation_by_project_name(project_name)
    if installation is None:
        return await render_template(_PAGE_NOT_FOUND), 404

    base_dir = get_temporary_base_directory()
    async with aiofiles.tempfile.TemporaryDirectory(dir=base_dir) as work_dir:
        org_config = await get_organization_config(installation, "", base_dir, work_dir)

        # the playground starts with the current configuration of the organization, once it has been fetched
        organization = None
        config = await get_configuration_by_project_name(project_name)
        if config is not None and config.jsonnet is not None:
            # the stored sha is the one of the file, not of a commit: link the default branch,
            # whose configuration is fetched again on each push to the configuration repository
            repo_url = f"https://github.com/{config.github_id}/{org_config.config_repo}"
            path = f"otterdog/{config.github_id}.jsonnet"
            organization = {
                "name": project_name,
                "jsonnet": config.jsonnet,
                "url": f"{repo_url}/blob/HEAD/{path}",
                # the editor of GitHub needs a branch, known once the configuration has been fetched again
                "edit_url": None if config.branch is None else f"{repo_url}/edit/{quote(config.branch)}/{path}",
            }

        return await _render_playground(await _instance_template(org_config), project_name, organization)


# The validation of the configurations evaluated by the playground, with the validations of otterdog that only depend
# on the configuration and on the default configuration, like `otterdog validate` without the ones depending on the
# current state of the organization on GitHub. The evaluated configuration is posted by the playground once asked to
# validate it, it is neither stored nor applied.


@blueprint.route("/playground/validate", methods=["POST"])
async def validate_global_playground():
    import aiofiles

    example = request.args.get("template") == EXAMPLE_TEMPLATE
    origin = await _validation_origin("the global playground" + (" with the example template" if example else ""))

    data = await _posted_configuration(origin)
    if isinstance(data, tuple):
        return data

    async def validate():
        otterdog_config = await get_otterdog_config()

        base_dir = get_temporary_base_directory()
        async with aiofiles.tempfile.TemporaryDirectory(dir=base_dir) as work_dir:
            if example:
                jsonnet_config = await _example_jsonnet_config(work_dir)
                if jsonnet_config is None:
                    logger.warning("rejecting a validation for %s: the example template is not available", origin)
                    return {"error": "the example template of otterdog is not available"}, 404
            else:
                try:
                    base_template = otterdog_config.default_base_template
                except RuntimeError:
                    logger.warning("rejecting a validation for %s: no default base template is configured", origin)
                    return {"error": "no default configuration is configured"}, 404
                jsonnet_config = _default_org_config(otterdog_config, base_template, base_dir, work_dir).jsonnet_config

            return await _validate_playground_configuration(otterdog_config, jsonnet_config, data, origin)

    result = await _validation_slots.run(validate)
    return _too_many_validations(origin) if result is None else result


@blueprint.route("/projects/<project_name>/playground/validate", methods=["POST"])
async def validate_playground(project_name: str):
    import aiofiles

    # the name of the project in the url is neither logged nor returned, only the one of a known project
    installation = await get_installation_by_project_name(project_name)
    if installation is None:
        logger.warning(
            "rejecting a validation for %s", await _validation_origin("the playground of an unknown project")
        )
        return {"error": "unknown project"}, 404

    origin = await _validation_origin(f"the playground of project '{installation.project_name}'")

    data = await _posted_configuration(origin)
    if isinstance(data, tuple):
        return data

    async def validate():
        otterdog_config = await get_otterdog_config()

        base_dir = get_temporary_base_directory()
        async with aiofiles.tempfile.TemporaryDirectory(dir=base_dir) as work_dir:
            org_config = await get_organization_config(installation, "", base_dir, work_dir)
            return await _validate_playground_configuration(otterdog_config, org_config.jsonnet_config, data, origin)

    result = await _validation_slots.run(validate)
    return _too_many_validations(origin) if result is None else result


async def _validation_origin(playground: str) -> str:
    """Returns the playground and the user asking for a validation, for the logs."""

    try:
        if await current_user.is_authenticated:
            username = await cast("User", current_user).username
            return f"{playground} by user '{username}'"
    except KeyError:
        # the users cannot log in if the authentication is not configured
        pass
    return f"{playground} by an anonymous user"


_NOT_A_CONFIGURATION = {"error": "an evaluated configuration of an organization is expected"}


async def _posted_configuration(origin: str) -> dict[str, Any] | tuple[dict[str, Any], int]:
    """
    Returns the configuration posted as json to be validated, otherwise the response rejecting the request. The body
    is read up to PLAYGROUND_VALIDATION_MAX_SIZE bytes, whether its length is announced or not, e.g. when it is sent in
    chunks, in BODY_TIMEOUT seconds like any body.
    """

    from werkzeug.exceptions import RequestTimeout

    max_size = current_app.config["PLAYGROUND_VALIDATION_MAX_SIZE"]
    too_large = {"error": f"the configuration must not exceed {max_size} bytes"}, 413

    async def read() -> bytes | None:
        body = bytearray()
        async for chunk in request.body:
            body.extend(chunk)
            if len(body) > max_size:
                return None
        return bytes(body)

    if request.content_length is not None and request.content_length > max_size:
        body = None
    else:
        try:
            body = await asyncio.wait_for(read(), timeout=request.body_timeout)
        except TimeoutError:
            raise RequestTimeout() from None

    if body is None:
        logger.warning("rejecting a validation for %s: larger than %d bytes", origin, max_size)
        return too_large

    try:
        data = json.loads(body) if request.is_json else None
    except (ValueError, RecursionError):
        data = None
    if not isinstance(data, dict):
        logger.warning("rejecting a validation for %s: no evaluated configuration", origin)
        return _NOT_A_CONFIGURATION, 400
    return data


_T = TypeVar("_T")


class _ValidationSlots:
    """
    The validations of the configurations posted by the playground running concurrently in the worker process, at most
    PLAYGROUND_MAX_CONCURRENT_VALIDATIONS: the other ones are rejected at once, rather than waiting and piling up.
    """

    def __init__(self) -> None:
        # the tasks of the running validations, referenced until they complete
        self._tasks: set[asyncio.Task] = set()

    @property
    def running(self) -> int:
        return len(self._tasks)

    async def run(self, validate: Callable[[], Coroutine[Any, Any, _T]]) -> _T | None:
        """
        Runs a validation if a slot is free, returns its result, None if no slot is free. The validation runs in its
        own task, shielded from the cancellation of the request, e.g. when its client disconnects: its work offloaded
        to threads cannot be stopped, so it keeps its slot and its working directory until it completes.
        """

        if self.running >= current_app.config["PLAYGROUND_MAX_CONCURRENT_VALIDATIONS"]:
            return None

        task = asyncio.create_task(validate())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return await asyncio.shield(task)


_validation_slots = _ValidationSlots()


def _too_many_validations(origin: str) -> tuple[dict[str, Any], int, dict[str, str]]:
    logger.warning("rejecting a validation for %s: %d validations are running", origin, _validation_slots.running)
    return {"error": "too many validations are running, try again in a moment"}, 503, {"Retry-After": "5"}


# the names of the project and of the organization are passed to the default configuration as jsonnet strings
_VALIDATED_NAME = re.compile(r"[\w.-]+")


async def _validate_playground_configuration(
    otterdog_config: OtterdogConfig, jsonnet_config: JsonnetConfig, data: dict[str, Any], origin: str
) -> dict[str, Any]:
    """
    Validates an evaluated configuration, returns its problems {severity, message}, severity being 'error', 'warning'
    or 'info'. The origin of the validation, see _validation_origin, is logged with its result, but not the values of
    the configuration, which are posted by the user.
    """

    import time
    from asyncio import to_thread

    from otterdog.config import CredentialResolver

    start = time.perf_counter()
    try:
        # validated with the json schema of otterdog, which takes a while for large configurations
        organization, unknown_properties = await to_thread(
            GitHubOrganization.from_model_data_with_unknown_properties, data
        )
    except Exception as ex:
        # e.g. a value not valid for the json schema of otterdog
        messages = str(ex).splitlines()
        logger.info("rejecting a validation for %s: %d error(s) reading the configuration", origin, len(messages))
        return {"problems": [{"severity": "error", "message": message} for message in messages]}

    for name in (organization.project_name, organization.github_id):
        if _VALIDATED_NAME.fullmatch(name) is None:
            logger.warning("rejecting a validation for %s: invalid name of the project or organization", origin)
            message = f"the name '{name}' can only contain letters, digits, '.', '_' and '-' to be validated"
            return {"problems": [{"severity": "error", "message": message}]}

    await jsonnet_config.init_template()
    # without provider, the validation never waits, e.g. evaluating the default configuration, it is run apart too
    context = await to_thread(
        asyncio.run,
        organization.validate(otterdog_config, jsonnet_config, CredentialResolver(otterdog_config), None),
    )
    # otterdog only logs the unknown properties, which it ignores
    problems = [
        {
            "severity": "warning",
            "message": f"{path or 'organization'} has the unknown property '{name}', which otterdog ignores",
        }
        for path, name in unknown_properties
    ]
    problems.extend(
        {"severity": failure_type.name.lower(), "message": _plain_text(message)}
        for failure_type, message in context.validation_failures
    )

    counts = {severity: sum(problem["severity"] == severity for problem in problems) for severity in _SEVERITIES}
    logger.info(
        "validated a configuration for %s in %d ms: %d error(s), %d warning(s), %d info(s)",
        origin,
        (time.perf_counter() - start) * 1000,
        *counts.values(),
    )
    return {"problems": problems}


_SEVERITIES = ("error", "warning", "info")


def _plain_text(message: str) -> str:
    """
    Returns a message of otterdog without the markup of the console: the headers of the objects, e.g.
    '[bold]repository[/]\\[name="[bold]my-repo[/]"]', are in bold, the values of the configuration in them escaped.
    Unlike rich, it does not fail on values looking like markup, e.g. '[/x]'.
    """

    return message.replace("[bold]", "").replace("[/]", "").replace("\\[", "[")


async def _example_jsonnet_config(work_dir: str) -> JsonnetConfig | None:
    """Returns the example template of otterdog vendored in a working directory, None if it is not available."""

    import aiofiles.os
    from aioshutil import copytree

    if not await aiofiles.os.path.isfile(os.path.join(_EXAMPLE_TEMPLATE_DIR, _EXAMPLE_TEMPLATE_FILE)):
        return None

    # local only, the url only names the vendored directory and the file of the template, like in the playground
    jsonnet_config = JsonnetConfig(
        "playground", work_dir, f"https://github.com/eclipse-csi/otterdog-defaults#{_EXAMPLE_TEMPLATE_FILE}@main", True
    )
    await copytree(_EXAMPLE_TEMPLATE_DIR, jsonnet_config.template_dir)
    return jsonnet_config


async def _render_playground(
    template: dict[str, Any],
    project_name: str | None,
    organization: dict[str, str | None] | None = None,
    templates: list[dict[str, Any]] | None = None,
    example: bool = False,
) -> str:
    # otterdog validates the configurations with the same default configuration as the playground
    if project_name is not None:
        validation_url = url_for("home_blueprint.validate_playground", project_name=project_name)
    elif example:
        validation_url = url_for("home_blueprint.validate_global_playground", template=EXAMPLE_TEMPLATE)
    else:
        validation_url = url_for("home_blueprint.validate_global_playground")

    return await render_home_template(
        "playground.html",
        project_name=project_name,
        jsonnet_files=template["files"],
        default_config=template["default_config"],
        default_configuration=template["link"],
        templates=templates,
        examples=_playground_examples(),
        reference=_playground_reference(),
        schemas=_playground_schemas(),
        documentation_url=current_app.config["DOCUMENTATION_URL"],
        organization=organization,
        validation_url=validation_url,
    )


async def _default_template(otterdog_config: OtterdogConfig, base_template: str) -> dict[str, Any]:
    """Returns the files of the default base template of the instance, see _instance_template."""

    import aiofiles

    base_dir = get_temporary_base_directory()
    async with aiofiles.tempfile.TemporaryDirectory(dir=base_dir) as work_dir:
        return await _instance_template(_default_org_config(otterdog_config, base_template, base_dir, work_dir))


def _default_org_config(
    otterdog_config: OtterdogConfig, base_template: str, base_dir: str, work_dir: str
) -> OrganizationConfig:
    """Returns the configuration of an organization using the default base template of the instance."""

    return OrganizationConfig.of(
        "playground",
        "playground",
        otterdog_config.default_config_repo,
        base_template,
        {"provider": "inmemory", "api_token": ""},
        base_dir,
        work_dir,
    )


async def _instance_template(org_config: OrganizationConfig) -> dict[str, Any]:
    import aiofiles

    jsonnet_config = org_config.jsonnet_config
    await jsonnet_config.init_template()

    # the files of the template are next to its default configuration in its repository
    repo_url, file, ref = parse_template_url(org_config.base_template)
    directory = posixpath.dirname(file)

    files = []
    async for jsonnet_file in jsonnet_config.jsonnet_template_files():
        name = os.path.basename(jsonnet_file)
        async with aiofiles.open(jsonnet_file) as f:
            files.append(
                {
                    "filename": f"vendor/{jsonnet_config.base_template_repo_name}/{name}",
                    "content": await f.read(),
                    "url": f"{repo_url}/blob/{ref}/{posixpath.join(directory, name)}",
                }
            )

    return {
        "files": files,
        "default_config": f"vendor/{jsonnet_config.base_template_repo_name}/{jsonnet_config.base_template_file_name}",
        "link": _default_configuration_link(org_config.base_template),
    }


async def _example_template() -> dict[str, Any] | None:
    import aiofiles
    import aiofiles.os

    if not await aiofiles.os.path.isfile(os.path.join(_EXAMPLE_TEMPLATE_DIR, _EXAMPLE_TEMPLATE_FILE)):
        return None

    # link the template of the running release, development versions are built from the main branch
    ref = f"v{otterdog.__version__}" if re.fullmatch(r"\d+\.\d+\.\d+", otterdog.__version__) else "main"
    url = f"https://github.com/eclipse-csi/otterdog/blob/{ref}/otterdog/resources/defaults"

    # vendored like the default configurations used in the documentation
    files = []
    for name in sorted(await aiofiles.os.listdir(_EXAMPLE_TEMPLATE_DIR)):
        if name.endswith(".libsonnet"):
            async with aiofiles.open(os.path.join(_EXAMPLE_TEMPLATE_DIR, name)) as f:
                files.append(
                    {
                        "filename": f"vendor/otterdog-defaults/{name}",
                        "content": await f.read(),
                        "url": f"{url}/{name}",
                    }
                )

    return {
        "files": files,
        "default_config": f"vendor/otterdog-defaults/{_EXAMPLE_TEMPLATE_FILE}",
        "link": {
            "url": f"{url}/{_EXAMPLE_TEMPLATE_FILE}",
            "label": f"eclipse-csi/otterdog/otterdog/resources/defaults/{_EXAMPLE_TEMPLATE_FILE}@{ref}",
        },
    }


def _default_configuration_link(base_template: str) -> dict[str, str]:
    # the base template has the format https://github.com/<owner>/<repo>#<file>@<ref>
    repo_url, file, ref = parse_template_url(base_template)
    return {
        "url": f"{repo_url}/blob/{ref}/{file}",
        "label": f"{repo_url.removeprefix('https://github.com/')}/{file}@{ref}",
    }


@functools.cache
def _playground_examples() -> list[dict[str, Any]]:
    # generated from the configuration guides of the documentation with `make playground-examples`
    with open(os.path.join(os.path.dirname(__file__), "playground-examples.json")) as file:
        return json.load(file)["pages"]


@functools.cache
def _playground_reference() -> dict[str, Any]:
    # generated from the reference of the documentation with `make playground-examples`, describes the properties
    # completed by the playground
    with open(os.path.join(os.path.dirname(__file__), "playground-reference.json")) as file:
        return json.load(file)


@functools.cache
def _playground_schemas() -> dict[str, Any]:
    # the schemas otterdog validates configurations with, the playground validates the evaluated ones with them
    schemas = files(resources).joinpath("schemas")
    return {
        schema.name: json.loads(schema.read_text()) for schema in schemas.iterdir() if schema.name.endswith(".json")
    }


@blueprint.route("/projects/<project_name>/repos/<repo_name>")
async def repository(project_name: str, repo_name: str):
    config = await get_configuration_by_project_name(project_name)

    if config is None:
        return await render_template(_PAGE_NOT_FOUND), 404

    from otterdog.models.github_organization import GitHubOrganization

    github_organization = GitHubOrganization.from_model_data(config.config)

    repo_config = next(filter(lambda x: x.name == repo_name, github_organization.repositories), None)
    if repo_config is None:
        return await render_template(_PAGE_NOT_FOUND), 404

    scorecard_result = await find_scorecard_result(config.github_id, repo_name)

    return await render_home_template(
        "repository.html",
        project_name=project_name,
        github_id=config.github_id,
        config=github_organization,
        repo_name=repo_name,
        repo_config=repo_config,
        scorecard_result=scorecard_result,
    )


@blueprint.route("/admin/organizations")
async def organizations():
    return await render_home_template(
        "organizations.html",
        installations=await get_installations(),
    )


@blueprint.route("/scorecard/checks")
async def scorecards():
    return await render_home_template("scorecards.html")


@blueprint.route("/admin/pullrequests")
async def pullrequests():
    return await render_home_template("pullrequests.html")


@blueprint.route("/admin/blueprints")
async def blueprints():
    return await render_home_template("blueprints.html")


@blueprint.route("/admin/policies")
async def policies():
    all_orgs = [x.github_id for x in await get_installations()]
    aggregate_status = {}
    for github_id in all_orgs:
        org_status = {x.id.policy_type: x.status for x in await get_policies_status(github_id)}
        _merge_policy_status(aggregate_status, org_status)

    return await render_home_template("policies.html", policy_status=aggregate_status)


def _merge_policy_status(aggregate_status: MutableMapping[str, Any], org_status: Mapping[str, Any]) -> None:
    def merge_dict(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, int]:
        return {k: a.get(k, 0) + b.get(k, 0) for k in set(a).union(set(b))}

    for policy_type, status in org_status.items():
        if policy_type in aggregate_status:
            aggregate_status[policy_type] = merge_dict(aggregate_status[policy_type], status)
        else:
            aggregate_status.update({policy_type: status})


@blueprint.route("/admin/template-impact")
async def template_impact():
    """The impact of a change of the default base template on the projects using it, evaluated in the browser."""

    otterdog_config = await get_otterdog_config()
    try:
        base_template = otterdog_config.default_base_template
    except RuntimeError:
        return await render_template(_PAGE_NOT_FOUND), 404

    template = await _default_template(otterdog_config, base_template)
    return await render_home_template(
        "template-impact.html",
        jsonnet_files=template["files"],
        default_config=template["default_config"],
        default_configuration=template["link"],
    )


@blueprint.route("/admin/template-impact/configurations")
async def template_impact_configurations():
    """
    Returns the configurations of the projects using the default base template, which the page of the impact of the
    template evaluates with the default configuration as published and as edited, to list the projects whose
    configuration changes. The configuration of a project is null until it has been fetched with its jsonnet source.
    """

    otterdog_config = await get_otterdog_config()
    try:
        base_template = otterdog_config.default_base_template
    except RuntimeError:
        return {"projects": []}

    installations = [
        installation
        for installation in await get_active_installations()
        if installation.base_template == base_template and installation.project_name is not None
    ]
    sources = await get_configuration_sources([installation.github_id for installation in installations])
    return {
        "projects": [
            {"name": installation.project_name, "jsonnet": sources.get(installation.github_id)}
            for installation in sorted(installations, key=lambda installation: installation.project_name or "")
        ]
    }


@blueprint.route("/admin/tasks")
async def tasks():
    return await render_home_template("tasks.html")


@blueprint.route("/<template>")
async def route_template(template: str):
    try:
        endpoint = template.rstrip(".html") if template.endswith(".html") else template

        return redirect(url_for(f".{endpoint}"))
    except BuildError:
        return await render_template(_PAGE_NOT_FOUND), 404


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
    from otterdog import __version__

    return await render_template(
        f"home/{template_name}",
        segments=get_segments(request),
        projects=await get_project_navigation(),
        version=__version__,
        **context,
    )
