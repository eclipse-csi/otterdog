# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import importlib.metadata
import sys
import traceback
from typing import Any, Optional

import click
from click.shell_completion import CompletionItem

from .config import OtterdogConfig
from .operations import Operation
from .operations.apply_operation import ApplyOperation
from .operations.canonical_diff_operation import CanonicalDiffOperation
from .operations.dispatch_workflow import DispatchWorkflowOperation
from .operations.fetch_operation import FetchOperation
from .operations.list_apps_operation import ListAppsOperation
from .operations.import_operation import ImportOperation
from .operations.local_plan_operation import LocalPlanOperation
from .operations.plan_operation import PlanOperation
from .operations.push_operation import PushOperation
from .operations.show_live_operation import ShowLiveOperation
from .operations.show_operation import ShowOperation
from .operations.show_default_operation import ShowDefaultOperation
from .operations.sync_template_operation import SyncTemplateOperation
from .operations.validate_operation import ValidateOperation
from .operations.web_login_operation import WebLoginOperation
from .utils import IndentingPrinter, init, is_debug_enabled, print_error

_CONFIG_FILE = "otterdog.json"

_DISTRIBUTION_METADATA = importlib.metadata.metadata("otterdog")
_VERSION = _DISTRIBUTION_METADATA["Version"]

_CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=120)

_CONFIG: Optional[OtterdogConfig] = None


def complete_organizations(ctx, param, incomplete):
    config_file = ctx.params.get("config")
    if config_file is None:
        config_file = _CONFIG_FILE

    try:
        config = OtterdogConfig.from_file(config_file, False)
        out = []
        for org in config.organization_configs.keys():
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
        init(verbose)

        config_file = ctx.params.pop("config")
        local_mode = ctx.params.pop("local")

        try:
            _CONFIG = OtterdogConfig.from_file(config_file, local_mode)
        except Exception as e:
            if is_debug_enabled():
                traceback.print_exception(e)

            print_error(str(e))
            sys.exit(2)

        return super().invoke(ctx)


@click.group(context_settings=_CONTEXT_SETTINGS)
@click.version_option(version=_VERSION, prog_name="otterdog.sh")
def cli():
    """
    Managing GitHub organizations at scale.
    """


@cli.command(cls=StdCommand)
def validate(organizations: list[str]):
    """
    Validates the configuration for organizations.
    """
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
    _execute_operation(organizations, ShowDefaultOperation(markdown))


@cli.command(cls=StdCommand)
@click.option(
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
def fetch_config(organizations: list[str], force, pull_request):
    """
    Fetches the configuration from the corresponding config repo of an organization.
    """
    _execute_operation(organizations, FetchOperation(force_processing=force, pull_request=pull_request))


@cli.command(cls=StdCommand)
@click.option("-m", "--message", help="commit messaged")
def push_config(organizations: list[str], message):
    """
    Pushes the local configuration to the corresponding config repo of an organization.
    """
    _execute_operation(organizations, PushOperation(push_message=message))


@cli.command(cls=StdCommand)
@click.option("--json", is_flag=True, show_default=True, default=False, help="use json format for output")
def list_apps(organizations: list[str], json):
    """
    Lists all app installations for the organization.
    """
    _execute_operation(organizations, ListAppsOperation(json))


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
    help="updates webhook with secrets regardless of changes",
)
@click.option(
    "--update-filter",
    show_default=True,
    default=".*",
    help="a valid python regular expression to match webhook urls / secret names to be included for update",
)
def plan(organizations: list[str], no_web_ui, update_webhooks, update_secrets, update_filter):
    """
    Show changes that would be applied by otterdog based on the current configuration
    compared to the current live configuration at GitHub.
    """
    _execute_operation(
        organizations,
        PlanOperation(
            no_web_ui=no_web_ui,
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
    default="-HEAD",
    help="suffix to append to the configuration for comparison",
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
    help="updates webhook with secrets regardless of changes",
)
@click.option(
    "--update-filter",
    show_default=True,
    default=".*",
    help="a valid python regular expression to match webhook urls / secret names to be included for update",
)
def local_plan(organizations: list[str], suffix, update_webhooks, update_secrets, update_filter):
    """
    Show changes that would be applied by otterdog based on the current configuration
    compared to another local configuration.
    """
    _execute_operation(
        organizations,
        LocalPlanOperation(
            suffix=suffix, update_webhooks=update_webhooks, update_secrets=update_secrets, update_filter=update_filter
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
    help="updates webhook with secrets regardless of changes",
)
@click.option(
    "--update-filter",
    show_default=True,
    default=".*",
    help="a valid python regular expression to match webhook urls / secret names to be included for update",
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
    update_webhooks,
    update_secrets,
    update_filter,
    delete_resources,
):
    """
    Apply changes based on the current configuration to the live configuration at GitHub.
    """
    _execute_operation(
        organizations,
        ApplyOperation(
            force_processing=force,
            no_web_ui=no_web_ui,
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
    help="repository to sync (default: all repos created from a template)",
)
def sync_template(organizations: list[str], repo):
    """
    Sync contents of repositories created from a template repository.
    """
    _execute_operation(organizations, SyncTemplateOperation(repo=repo))


@cli.command(cls=StdCommand)
def canonical_diff(organizations: list[str]):
    """
    Displays a diff of the current configuration to a canonical version.
    """
    _execute_operation(organizations, CanonicalDiffOperation())


@cli.command(cls=StdCommand, short_help="Open a browser window logged in to the GitHub organization.")
def web_login(organizations: list[str]):
    """
    Opens a new browser window and logins to GitHub with the bot account for the organization.
    """
    _execute_operation(organizations, WebLoginOperation())


def _execute_operation(organizations: list[str], operation: Operation):
    printer = IndentingPrinter(sys.stdout)
    printer.println()

    try:
        exit_code = 0
        config = _CONFIG

        assert config is not None

        operation.init(config, printer)
        operation.pre_execute()

        # if no organization has been specified as argument,
        # process all organizations found in the configuration.
        if len(organizations) == 0:
            organizations = list(config.organization_configs.keys())

        for organization in organizations:
            printer.println()
            org_config = config.get_organization_config(organization)
            exit_code = max(exit_code, operation.execute(org_config))

        sys.exit(exit_code)

    except Exception as e:
        if is_debug_enabled():
            traceback.print_exception(e)

        print_error(str(e))
        sys.exit(2)


if __name__ == "__main__":
    cli()
