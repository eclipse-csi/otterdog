# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import click
import importlib.metadata
import sys
import traceback
from typing import Any, Optional

from . import utils
from .config import OtterdogConfig
from .operations import Operation
from .operations.apply_operation import ApplyOperation
from .operations.canonical_diff_operation import CanonicalDiffOperation
from .operations.fetch_operation import FetchOperation
from .operations.import_operation import ImportOperation
from .operations.local_plan_operation import LocalPlanOperation
from .operations.plan_operation import PlanOperation
from .operations.push_operation import PushOperation
from .operations.show_operation import ShowOperation
from .operations.sync_template_operation import SyncTemplateOperation
from .operations.validate_operation import ValidateOperation

_CONFIG_FILE = "otterdog.json"

_DISTRIBUTION_METADATA = importlib.metadata.metadata('otterdog')
_VERSION = _DISTRIBUTION_METADATA['Version']

_CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

_CONFIG: Optional[OtterdogConfig] = None


class StdCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context_settings = _CONTEXT_SETTINGS
        self.params.insert(0, click.Option(["-v", "--verbose"], count=True,
                                           help="enable verbose output (-vv for more verbose output)"))

        self.params.insert(0, click.Option(["-c", "--config"], default=_CONFIG_FILE, show_default=True,
                                           type=click.Path(True, True, False),
                                           help="configuration file to use"))

        self.params.insert(0, click.Option(["--local"], is_flag=True, default=False, show_default=True,
                                           help="work in local mode, not updating the referenced default config"))

        self.params.insert(0, click.Argument(["organizations"], nargs=-1))

    def invoke(self, ctx: click.Context) -> Any:
        global _CONFIG

        verbose = ctx.params.pop("verbose")
        utils.init(verbose)

        config_file = ctx.params.pop("config")
        local_mode = ctx.params.pop("local")

        try:
            _CONFIG = OtterdogConfig.from_file(config_file, local_mode)
        except Exception as e:
            if utils.is_debug_enabled():
                traceback.print_exception(e)

            utils.print_error(str(e))
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
def show(organizations: list[str]):
    """
    Displays the full configuration for organizations.
    """
    _execute_operation(organizations, ShowOperation())


@cli.command(cls=StdCommand)
@click.option("-f", "--force", is_flag=True, show_default=True, default=False,
              help="skips interactive approvals")
@click.option("-p", "--pull-request",
              help="fetch from pull request number instead of default branch")
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


@cli.command(cls=StdCommand, name="import")
@click.option("-f", "--force", is_flag=True, show_default=True, default=False,
              help="skips interactive approvals")
@click.option("-n", "--no-web-ui", is_flag=True, show_default=True, default=False,
              help="skip settings retrieved via web ui")
def import_command(organizations: list[str], force, no_web_ui):
    """
    Imports existing resources for a GitHub organization.
    """
    _execute_operation(organizations, ImportOperation(force_processing=force, no_web_ui=no_web_ui))


@cli.command(cls=StdCommand)
@click.option("-n", "--no-web-ui", is_flag=True, show_default=True, default=False,
              help="skip settings retrieved via web ui")
@click.option("-u", "--update-webhooks", is_flag=True, show_default=True, default=False,
              help="updates webhook with secrets regardless of changes")
def plan(organizations: list[str], no_web_ui, update_webhooks):
    """
    Show changes that would be applied by otterdog based on the current configuration
    compared to the current live configuration at GitHub.
    """
    _execute_operation(organizations, PlanOperation(no_web_ui=no_web_ui, update_webhooks=update_webhooks))


@cli.command(cls=StdCommand)
@click.option("-s", "--suffix", show_default=True, default="-HEAD",
              help="suffix to append to the configuration for comparison")
@click.option("-u", "--update-webhooks", is_flag=True, show_default=True, default=False,
              help="updates webhook with secrets regardless of changes")
def local_plan(organizations: list[str], suffix, update_webhooks):
    """
    Show changes that would be applied by otterdog based on the current configuration
    compared to another local configuration.
    """
    _execute_operation(organizations, LocalPlanOperation(suffix=suffix, update_webhooks=update_webhooks))


@cli.command(cls=StdCommand)
@click.option("-f", "--force", is_flag=True, show_default=True, default=False,
              help="skips interactive approvals")
@click.option("-n", "--no-web-ui", is_flag=True, show_default=True, default=False,
              help="skip settings retrieved via web ui")
@click.option("-u", "--update-webhooks", is_flag=True, show_default=True, default=False,
              help="updates webhook with secrets regardless of changes")
@click.option("-d", "--delete-resources", is_flag=True, show_default=True, default=False,
              help="enables deletion of resources if they are missing in the definition")
def apply(organizations: list[str], force, no_web_ui, update_webhooks, delete_resources):
    """
    Apply changes based on the current configuration to the live configuration at GitHub.
    """
    _execute_operation(organizations, ApplyOperation(force_processing=force,
                                                     no_web_ui=no_web_ui,
                                                     update_webhooks=update_webhooks,
                                                     delete_resources=delete_resources))


@cli.command(cls=StdCommand)
@click.option("-r", "--repo", default=None,
              help="repository to sync (default: all repos created from a template)")
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


def _execute_operation(organizations: list[str], operation: Operation):
    printer = utils.IndentingPrinter()
    printer.print()

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
            printer.print()
            org_config = config.organization_config(organization)
            exit_code = max(exit_code, operation.execute(org_config))

        sys.exit(exit_code)

    except Exception as e:
        if utils.is_debug_enabled():
            traceback.print_exception(e)

        utils.print_error(str(e))
        sys.exit(2)


if __name__ == '__main__':
    cli()
