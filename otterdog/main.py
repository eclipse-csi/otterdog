# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import argparse
import sys
import traceback

from . import utils
from .config import OtterdogConfig
from .operations.apply_operation import ApplyOperation
from .operations.fetch_operation import FetchOperation
from .operations.push_operation import PushOperation
from .operations.import_operation import ImportOperation
from .operations.plan_operation import PlanOperation
from .operations.show_operation import ShowOperation
from .operations.validate_operation import ValidateOperation

CONFIG_FILE = "otterdog.json"


# main entry point
def main(arguments=None):
    if not arguments:
        arguments = sys.argv[1:]

    # command line parsing.
    parser = argparse.ArgumentParser(prog="otterdog.sh",
                                     description="Manages GitHub organizations and repositories.")

    subparsers = parser.add_subparsers(dest="subcommand",
                                       required=True,
                                       title="subcommands",
                                       description="valid subcommands")

    plan_parser = subparsers.add_parser("plan", help="Show changes required by the current configuration")
    fetch_parser = subparsers.add_parser("fetch-config",
                                         help="Fetches the configuration from the corresponding config "
                                              "repo of an organization")
    push_parser = subparsers.add_parser("push-config",
                                        help="Pushes the local configuration to the corresponding config "
                                             "repo of an organization")
    import_parser = subparsers.add_parser("import", help="Imports existing resources for a GitHub organization")
    apply_parser = subparsers.add_parser("apply", help="Create or update organizations / repos on GitHub")
    validate_parser = subparsers.add_parser("validate", help="Check whether the configuration is valid")
    show_parser = subparsers.add_parser("show")

    for subparser in [plan_parser,
                      fetch_parser,
                      push_parser,
                      import_parser,
                      apply_parser,
                      validate_parser,
                      show_parser]:
        subparser.add_argument("organization", nargs="*", help="the github id of the organization")
        subparser.add_argument("--config", "-c", help=f"configuration file, defaults to '{CONFIG_FILE}'",
                               action="store", default=CONFIG_FILE)
        subparser.add_argument("--local", action="store_true", default=False, help="does not update the default config")
        subparser.add_argument("--force", "-f", action="store_true", default=False, help="skips interactive approvals")
        subparser.add_argument("--verbose", "-v", action="count", default=0, help="enable more verbose output")

    for subparser in [plan_parser, apply_parser]:
        subparser.add_argument("--no-web-ui", "-n", action="store_true", default=False,
                               help="skip settings retrieved via web ui")

    args = parser.parse_args(arguments)
    utils.init(args.verbose)

    printer = utils.IndentingPrinter()
    printer.print()

    try:
        if args.__contains__("no_web_ui"):
            no_web_ui = args.no_web_ui
        else:
            no_web_ui = False

        config = OtterdogConfig.from_file(args.config, args.force, args.local, no_web_ui)

        exit_code = 0

        subcommand = args.subcommand
        if subcommand == "plan":
            operation = PlanOperation()
        elif subcommand == "fetch-config":
            operation = FetchOperation()
        elif subcommand == "push-config":
            operation = PushOperation()
        elif subcommand == "import":
            operation = ImportOperation()
        elif subcommand == "apply":
            operation = ApplyOperation()
        elif subcommand == "validate":
            operation = ValidateOperation()
        elif subcommand == "show":
            operation = ShowOperation()
        else:
            raise RuntimeError(f"unexpected action '{args.action}'")

        operation.init(config, printer)
        operation.pre_execute()

        # if no organization has been specified as argument, process all organizations
        # found in the configuration.
        organizations = args.organization
        if len(organizations) == 0:
            organizations = [k for k, _ in config.organization_configs.items()]

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
    main(sys.argv[1:])
