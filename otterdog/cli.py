#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import sys
from typing import Any

import click
from click.shell_completion import CompletionItem

from otterdog.cache import set_github_cache
from otterdog.logging import CONSOLE_STDOUT, init_logging, print_error, print_exception
from otterdog.providers.github.cache.file import file_cache

from . import __version__
from .config import OtterdogConfig
from .operations import Operation
from .utils import IndentingPrinter, unwrap

_CONFIG_FILE = "otterdog.json"
_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"], "max_content_width": 120}

_CONFIG: OtterdogConfig | None = None


def complete_organizations(ctx, param, incomplete):
    config_file = ctx.params.get("config")
    if config_file is None:
        config_file = _CONFIG_FILE

    try:
        config = OtterdogConfig.from_file(config_file, False)
        out = []
        for org in config.organization_names + config.project_names:
            if incomplete in org:
                out.append(CompletionItem(org))
        return out

    except RuntimeError:
        return []


class StdCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context_settings = _CONTEXT_SETTINGS
        self.params.insert(
            0,
            click.Option(
                ["-v", "--verbose"],
                count=True,
                help="enable verbose output (-vvv for more verbose output)",
            ),
        )

        self.params.insert(
            0,
            click.Option(
                ["-c", "--config"],
                default=_CONFIG_FILE,
                show_default=True,
                type=click.Path(True, True, False),
                help="configuration file to use",
            ),
        )

        self.params.insert(
            0,
            click.Option(
                ["--local"],
                is_flag=True,
                default=False,
                show_default=True,
                help="work in local mode, not updating the referenced default config",
            ),
        )

        self.params.insert(0, click.Argument(["organizations"], nargs=-1, shell_complete=complete_organizations))

    def invoke(self, ctx: click.Context) -> Any:
        global _CONFIG

        verbose = ctx.params.pop("verbose")
        init_logging(verbose)

        config_file = ctx.params.pop("config")
        local_mode = ctx.params.pop("local")

        try:
            _CONFIG = OtterdogConfig.from_file(config_file, local_mode)
        except Exception as exc:
            print_exception(exc)
            sys.exit(2)

        return super().invoke(ctx)


class SingletonCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context_settings = _CONTEXT_SETTINGS
        self.params.insert(
            0,
            click.Option(
                ["-v", "--verbose"],
                count=True,
                help="enable verbose output (-vvv for more verbose output)",
            ),
        )

        self.params.insert(
            0,
            click.Option(
                ["-c", "--config"],
                default=_CONFIG_FILE,
                show_default=True,
                type=click.Path(True, True, False),
                help="configuration file to use",
            ),
        )

        self.params.insert(
            0,
            click.Option(
                ["--local"],
                is_flag=True,
                default=False,
                show_default=True,
                help="work in local mode, not updating the referenced default config",
            ),
        )

    def invoke(self, ctx: click.Context) -> Any:
        global _CONFIG

        verbose = ctx.params.pop("verbose")
        init_logging(verbose)

        config_file = ctx.params.pop("config")
        local_mode = ctx.params.pop("local")

        try:
            _CONFIG = OtterdogConfig.from_file(config_file, local_mode)
        except Exception as exc:
            print_exception(exc)
            sys.exit(2)

        return super().invoke(ctx)


@click.group(context_settings=_CONTEXT_SETTINGS)
@click.version_option(version=__version__, prog_name="otterdog.sh")
def cli():
    """
    Managing GitHub organizations at scale.
    """


@cli.command(cls=StdCommand)
def validate(organizations: list[str]):
    """
    Validates the configuration for organizations.
    """
    from otterdog.operations.validate import ValidateOperation

    _execute_operation(organizations, ValidateOperation())


@cli.command(cls=StdCommand)
@click.option(
    "--markdown",
    is_flag=True,
    default=False,
    help="output in markdown format",
)
@click.option(
    "--output-dir",
    show_default=True,
    type=click.Path(False, False, True),
    default="docs",
    help="output directory for generated markdown files",
)
def show(organizations: list[str], markdown, output_dir):
    """
    Displays the full configuration for organizations.
    """
    from otterdog.operations.show import ShowOperation

    _execute_operation(organizations, ShowOperation(markdown, output_dir))


@cli.command(cls=StdCommand)
@click.option(
    "-n",
    "--no-web-ui",
    is_flag=True,
    show_default=True,
    default=False,
    help="skip settings retrieved via web ui",
)
def show_live(organizations: list[str], no_web_ui):
    """
    Displays the live configuration for organizations.
    """
    from otterdog.operations.show_live import ShowLiveOperation

    _execute_operation(organizations, ShowLiveOperation(no_web_ui=no_web_ui))


@cli.command(cls=StdCommand)
@click.option(
    "--markdown",
    is_flag=True,
    default=False,
    help="output in markdown format",
)
def show_default(organizations: list[str], markdown):
    """
    Displays the default configuration for organizations.
    """
    from otterdog.operations.show_default import ShowDefaultOperation

    _execute_operation(organizations, ShowDefaultOperation(markdown))


@cli.command(cls=StdCommand)
@click.option(
    "-r",
    "--repo",
    show_default=True,
    default=".eclipsefdn",
    help="the repo to dispatch workflows for",
)
@click.option(
    "--workflow",
    help="the name of the workflow to dispatch",
)
def dispatch_workflow(organizations: list[str], repo, workflow):
    """
    Dispatches a workflow in a repo of an organization.
    """
    from otterdog.operations.dispatch_workflow import DispatchWorkflowOperation

    _execute_operation(organizations, DispatchWorkflowOperation(repo, workflow))


@cli.command(cls=StdCommand)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    show_default=True,
    default=False,
    help="skips interactive approvals",
)
@click.option(
    "-p",
    "--pull-request",
    help="fetch from pull request number instead of default branch",
)
@click.option(
    "-r",
    "--ref",
    help="ref to use, defaults to HEAD",
)
@click.option(
    "-s",
    "--suffix",
    show_default=True,
    default="",
    help="suffix to append to the configuration for comparison",
)
def fetch_config(organizations: list[str], force, pull_request, suffix, ref):
    """
    Fetches the configuration from the corresponding config repo of an organization.
    """
    from otterdog.operations.fetch_config import FetchOperation

    _execute_operation(
        organizations, FetchOperation(force_processing=force, pull_request=pull_request, suffix=suffix, ref=ref)
    )


@cli.command(cls=StdCommand)
@click.option("-m", "--message", help="commit message")
@click.option(
    "-n",
    "--no-diff",
    is_flag=True,
    show_default=True,
    default=False,
    help="disables displaying diff to current live config",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    show_default=True,
    default=False,
    help="skips interactive approvals",
)
def push_config(organizations: list[str], no_diff, force, message):
    """
    Pushes the local configuration to the corresponding config repo of an organization.
    """
    from otterdog.operations.push_config import PushOperation

    _execute_operation(
        organizations, PushOperation(show_diff=not no_diff, force_processing=force, push_message=message)
    )


@cli.command(cls=StdCommand, short_help="Opens a pull request for local configuration changes.")
@click.option("-b", "--branch", required=True, help="branch name")
@click.option("-t", "--title", required=True, help="PR title")
@click.option("-a", "--author", help="GitHub handle of author")
def open_pr(organizations: list[str], branch, title, author):
    """
    Opens a pull request for local configuration changes in the corresponding config repo of an organization.
    """
    from otterdog.operations.open_pull_request import OpenPullRequestOperation

    _execute_operation(organizations, OpenPullRequestOperation(branch=branch, title=title, author=author))


@cli.command(cls=StdCommand)
@click.option("--json", is_flag=True, show_default=True, default=False, help="use json format for output")
def list_apps(organizations: list[str], json):
    """
    Lists all app installations for the organization.
    """
    from otterdog.operations.list_apps import ListAppsOperation

    _execute_operation(organizations, ListAppsOperation(json))


@cli.command(cls=StdCommand)
@click.option("--two-factor-disabled", is_flag=True, help="show members that have two factor authentication disabled")
def list_members(organizations: list[str], two_factor_disabled: bool):
    """
    Lists members of the organization.
    """
    from otterdog.operations.list_members import ListMembersOperation

    _execute_operation(organizations, ListMembersOperation(two_factor_disabled))


@cli.command(cls=SingletonCommand)
def list_projects():
    """
    Lists all configured projects and their corresponding GitHub id.
    """
    from otterdog.operations.list_projects import ListProjectsOperation

    _execute_operation([], ListProjectsOperation())


@cli.command(cls=StdCommand)
@click.option("-b", "--blueprint-id", required=False, help="blueprint id")
def list_blueprints(organizations: list[str], blueprint_id):
    """
    List blueprints.
    """
    from otterdog.operations.list_blueprints import ListBlueprintsOperation

    _execute_operation(organizations, ListBlueprintsOperation(blueprint_id))


@cli.command(cls=StdCommand)
@click.option("-b", "--blueprint-id", required=False, help="blueprint id")
def approve_blueprints(organizations: list[str], blueprint_id):
    """
    Approved remediation PRs for blueprints.
    """
    from otterdog.operations.approve_blueprints import ApproveBlueprintsOperation

    _execute_operation(organizations, ApproveBlueprintsOperation(blueprint_id))


@cli.command(cls=StdCommand, name="import")
@click.option(
    "-f",
    "--force",
    is_flag=True,
    show_default=True,
    default=False,
    help="skips interactive approvals",
)
@click.option(
    "-n",
    "--no-web-ui",
    is_flag=True,
    show_default=True,
    default=False,
    help="skip settings retrieved via web ui",
)
def import_command(organizations: list[str], force, no_web_ui):
    """
    Imports existing resources for a GitHub organization.
    """
    from otterdog.operations.import_configuration import ImportOperation

    _execute_operation(organizations, ImportOperation(force_processing=force, no_web_ui=no_web_ui))


@cli.command(cls=StdCommand, short_help="Show changes to live configuration on GitHub.")
@click.option(
    "-n",
    "--no-web-ui",
    is_flag=True,
    show_default=True,
    default=False,
    help="skip settings retrieved via web ui",
)
@click.option(
    "-r",
    "--repo-filter",
    show_default=True,
    default="*",
    help="a valid shell pattern to match repository names to be included",
)
@click.option(
    "--update-webhooks",
    is_flag=True,
    show_default=True,
    default=False,
    help="updates webhook with secrets regardless of changes",
)
@click.option(
    "--update-secrets",
    is_flag=True,
    show_default=True,
    default=False,
    help="updates secrets regardless of changes",
)
@click.option(
    "--update-filter",
    show_default=True,
    default="*",
    help="a valid shell pattern to match webhook urls / secret names to be included for update",
)
def plan(organizations: list[str], no_web_ui, repo_filter, update_webhooks, update_secrets, update_filter):
    """
    Show changes that would be applied by otterdog based on the current configuration
    compared to the current live configuration at GitHub.
    """
    from otterdog.operations.plan import PlanOperation

    _execute_operation(
        organizations,
        PlanOperation(
            no_web_ui=no_web_ui,
            repo_filter=repo_filter,
            update_webhooks=update_webhooks,
            update_secrets=update_secrets,
            update_filter=update_filter,
        ),
    )


@cli.command(cls=StdCommand, short_help="Show changes to another local configuration.")
@click.option(
    "-s",
    "--suffix",
    show_default=True,
    default="-BASE",
    help="suffix to append to the configuration for comparison",
)
@click.option(
    "-r",
    "--repo-filter",
    show_default=True,
    default="*",
    help="a valid shell pattern to match repository names to be included",
)
@click.option(
    "--update-webhooks",
    is_flag=True,
    show_default=True,
    default=False,
    help="updates webhook with secrets regardless of changes",
)
@click.option(
    "--update-secrets",
    is_flag=True,
    show_default=True,
    default=False,
    help="updates secrets regardless of changes",
)
@click.option(
    "--update-filter",
    show_default=True,
    default="*",
    help="a valid shell pattern to match webhook urls / secret names to be included for update",
)
def local_plan(organizations: list[str], suffix, repo_filter, update_webhooks, update_secrets, update_filter):
    """
    Show changes that would be applied by otterdog based on the current configuration
    compared to another local configuration.
    """
    from otterdog.operations.local_plan import LocalPlanOperation

    _execute_operation(
        organizations,
        LocalPlanOperation(
            suffix=suffix,
            repo_filter=repo_filter,
            update_webhooks=update_webhooks,
            update_secrets=update_secrets,
            update_filter=update_filter,
        ),
    )


@cli.command(cls=StdCommand)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    show_default=True,
    default=False,
    help="skips interactive approvals",
)
@click.option(
    "-n",
    "--no-web-ui",
    is_flag=True,
    show_default=True,
    default=False,
    help="skip settings retrieved via web ui",
)
@click.option(
    "-r",
    "--repo-filter",
    show_default=True,
    default="*",
    help="a valid shell pattern to match repository names to be included",
)
@click.option(
    "--update-webhooks",
    is_flag=True,
    show_default=True,
    default=False,
    help="updates webhook with secrets regardless of changes",
)
@click.option(
    "--update-secrets",
    is_flag=True,
    show_default=True,
    default=False,
    help="updates secrets regardless of changes",
)
@click.option(
    "--update-filter",
    show_default=True,
    default="*",
    help="a valid shell pattern to match webhook urls / secret names to be included for update",
)
@click.option(
    "-d",
    "--delete-resources",
    is_flag=True,
    show_default=True,
    default=False,
    help="enables deletion of resources if they are missing in the definition",
)
def apply(
    organizations: list[str],
    force,
    no_web_ui,
    repo_filter,
    update_webhooks,
    update_secrets,
    update_filter,
    delete_resources,
):
    """
    Apply changes based on the current configuration to the live configuration at GitHub.
    """
    from otterdog.operations.apply import ApplyOperation

    _execute_operation(
        organizations,
        ApplyOperation(
            force_processing=force,
            no_web_ui=no_web_ui,
            repo_filter=repo_filter,
            update_webhooks=update_webhooks,
            update_secrets=update_secrets,
            update_filter=update_filter,
            delete_resources=delete_resources,
        ),
    )


@cli.command(cls=StdCommand)
@click.option(
    "-s",
    "--suffix",
    show_default=True,
    default="-BASE",
    help="suffix to append to the configuration for comparison",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    show_default=True,
    default=False,
    help="skips interactive approvals",
)
@click.option(
    "-n",
    "--no-web-ui",
    is_flag=True,
    show_default=True,
    default=False,
    help="skip settings retrieved via web ui",
)
@click.option(
    "-r",
    "--repo-filter",
    show_default=True,
    default="*",
    help="a valid shell pattern to match repository names to be included",
)
@click.option(
    "--update-webhooks",
    is_flag=True,
    show_default=True,
    default=False,
    help="updates webhook with secrets regardless of changes",
)
@click.option(
    "--update-secrets",
    is_flag=True,
    show_default=True,
    default=False,
    help="updates secrets regardless of changes",
)
@click.option(
    "--update-filter",
    show_default=True,
    default="*",
    help="a valid shell pattern to match webhook urls / secret names to be included for update",
)
@click.option(
    "-d",
    "--delete-resources",
    is_flag=True,
    show_default=True,
    default=False,
    help="enables deletion of resources if they are missing in the definition",
)
def local_apply(
    organizations: list[str],
    force,
    no_web_ui,
    repo_filter,
    update_webhooks,
    update_secrets,
    update_filter,
    delete_resources,
    suffix,
):
    """
    Apply changes based on the current configuration to another local configuration.
    """
    from otterdog.operations.local_apply import LocalApplyOperation

    _execute_operation(
        organizations,
        LocalApplyOperation(
            suffix=suffix,
            force_processing=force,
            no_web_ui=no_web_ui,
            repo_filter=repo_filter,
            update_webhooks=update_webhooks,
            update_secrets=update_secrets,
            update_filter=update_filter,
            delete_resources=delete_resources,
        ),
    )


@cli.command(cls=StdCommand)
@click.option(
    "-r",
    "--repo",
    required=True,
    help="repository to sync",
)
def sync_template(organizations: list[str], repo):
    """
    Sync contents of repositories created from a template repository.
    """
    from otterdog.operations.sync_template import SyncTemplateOperation

    _execute_operation(organizations, SyncTemplateOperation(repo=repo))


@cli.command(cls=StdCommand)
@click.option(
    "-r",
    "--repo",
    required=True,
    help="repository to use",
)
@click.option(
    "--path",
    help="the path of the content to be deleted",
)
@click.option("-m", "--message", help="commit messaged")
def delete_file(organizations: list[str], repo, path, message):
    """
    Delete files in a repository.
    """
    from otterdog.operations.delete_file import DeleteFileOperation

    _execute_operation(organizations, DeleteFileOperation(repo=repo, path=path, message=message))


@cli.command(cls=StdCommand)
def canonical_diff(organizations: list[str]):
    """
    Displays a diff of the current configuration to a canonical version.
    """
    from otterdog.operations.canonical_diff import CanonicalDiffOperation

    _execute_operation(organizations, CanonicalDiffOperation())


@cli.command(cls=StdCommand, short_help="Open a browser window logged in to the GitHub organization.")
def web_login(organizations: list[str]):
    """
    Opens a new browser window and logins to GitHub with the bot account for the organization.
    """
    from otterdog.operations.web_login import WebLoginOperation

    _execute_operation(organizations, WebLoginOperation())


@cli.command(cls=StdCommand, short_help="Installs a GitHub app for an organization.")
@click.option(
    "-a",
    "--app-slug",
    required=True,
    help="GitHub app slug",
)
def install_app(app_slug: str, organizations: list[str]):
    """
    Installs a GitHub App.
    """
    from otterdog.operations.install_app import InstallAppOperation

    _execute_operation(organizations, InstallAppOperation(app_slug))


@cli.command(cls=StdCommand, short_help="Uninstalls a GitHub app for an organization.")
@click.option(
    "-a",
    "--app-slug",
    required=True,
    help="GitHub app slug",
)
def uninstall_app(app_slug: str, organizations: list[str]):
    """
    Uninstalls a GitHub App.
    """
    from otterdog.operations.uninstall_app import UninstallAppOperation

    _execute_operation(organizations, UninstallAppOperation(app_slug))


@cli.command(cls=StdCommand, short_help="Reviews permission updates for GitHub apps.")
@click.option(
    "-a",
    "--app-slug",
    required=False,
    default=None,
    help="GitHub app slug",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    show_default=True,
    default=False,
    help="skips interactive approvals",
)
@click.option(
    "-g",
    "--grant",
    is_flag=True,
    show_default=True,
    default=False,
    help="approve requested permissions",
)
def review_permissions(app_slug, grant, force, organizations: list[str]):
    """
    Reviews permission updates for installed apps.
    """
    from otterdog.operations.review_app_permissions import ReviewAppPermissionsOperation

    _execute_operation(organizations, ReviewAppPermissionsOperation(app_slug, grant, force))


@cli.command(cls=StdCommand, short_help="Lists repository security advisories for an organization.")
@click.option(
    "-s",
    "--state",
    type=click.Choice(["triage", "draft", "published", "closed", "all"], case_sensitive=False),
    multiple=True,
    default=["triage", "draft"],
    show_default=True,
    help="list advisories by state",
)
@click.option(
    "-d",
    "--details",
    is_flag=True,
    show_default=True,
    default=False,
    help="display advisory details",
)
def list_advisories(state: list[str], details: bool, organizations: list[str]):
    """
    Lists repository security advisories for an organization.
    """
    from otterdog.operations.list_advisories import ListAdvisoriesOperation

    _execute_operation(organizations, ListAdvisoriesOperation(state, details))


@cli.command(cls=StdCommand, short_help="Checks granted scopes for the otterdog token.")
@click.option(
    "-l",
    "--list-granted-scopes",
    is_flag=True,
    show_default=True,
    default=False,
    help="display granted scopes",
)
def check_token_permissions(list_granted_scopes: bool, organizations: list[str]):
    """
    Checks the granted scopes for the otterdog-token.
    """
    from otterdog.operations.check_token_permissions import CheckTokenPermissionsOperation

    _execute_operation(organizations, CheckTokenPermissionsOperation(list_granted_scopes))


@cli.command(short_help="Installs required dependencies.")
def install_deps():
    """
    Installs required dependencies.
    """

    import subprocess

    process = subprocess.Popen(args=["playwright", "install", "firefox"], stdout=subprocess.PIPE)
    for c in iter(lambda: process.stdout.read(1), b""):
        sys.stdout.buffer.write(c)
    sys.stdout.flush()

    status = process.wait()

    if status != 0:
        print_error(f"could not install required dependencies: {status}")


def _execute_operation(organizations: list[str], operation: Operation):
    printer = IndentingPrinter(CONSOLE_STDOUT)

    try:
        exit_code = 0
        config = unwrap(_CONFIG)

        set_github_cache(file_cache())

        operation.init(config, printer)
        operation.pre_execute()

        # if no organization has been specified as argument,
        # process all organizations found in the configuration.
        if len(organizations) == 0:
            organizations = config.organization_names

        total_num_orgs = len(organizations)
        current_org_number = 1
        for organization in organizations:
            org_config = config.get_organization_config(organization)
            exit_code = max(exit_code, asyncio.run(operation.execute(org_config, current_org_number, total_num_orgs)))
            current_org_number += 1

        operation.post_execute()
        sys.exit(exit_code)

    except Exception as exc:
        print_exception(exc)
        sys.exit(2)


if __name__ == "__main__":
    cli()
