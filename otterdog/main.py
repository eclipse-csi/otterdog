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

import utils
from fetch import FetchOperation
from plan import PlanOperation
from apply import ApplyOperation
from validate import ValidateOperation
from show import ShowOperation
from config import OtterdogConfig

CONFIG_FILE = "otterdog.json"

# main entry point
if __name__ == '__main__':
    # command line parsing.
    parser = argparse.ArgumentParser(prog="otterdog.sh",
                                     description="sync / modify github settings for an organization.")

    subparsers = parser.add_subparsers(dest="action", required=True)

    plan_parser = subparsers.add_parser("plan")
    sync_parser = subparsers.add_parser("fetch")
    apply_parser = subparsers.add_parser("apply")
    validate_parser = subparsers.add_parser("validate")
    show_parser = subparsers.add_parser("show")

    for subparser in [plan_parser, sync_parser, apply_parser, validate_parser, show_parser]:
        subparser.add_argument("organization", nargs="*", help="the github id of the organization")
        subparser.add_argument("--config", "-c", help=f"configuration file, defaults to '{CONFIG_FILE}'",
                               action="store", default=CONFIG_FILE)
        subparser.add_argument("--verbose", "-v", action="count", default=0, help="enable more verbose output")

    args = parser.parse_args()

    utils.init(args.verbose)

    printer = utils.IndentingPrinter()
    printer.print()

    try:
        config = OtterdogConfig.from_file(args.config)
        jsonnet_config = config.jsonnet_config

        exit_code = 0

        match args.action:
            case "plan":
                printer.print(f"Planning execution for configuration at '{config.config_file}'")
                operation = PlanOperation(config)

            case "fetch":
                printer.print(f"Fetching resources for configuration at '{config.config_file}'")
                operation = FetchOperation(config)

            case "apply":
                printer.print(f"Execute changes for configuration at '{config.config_file}'")
                operation = ApplyOperation(config)

            case "validate":
                printer.print(f"Validating configuration at '{config.config_file}'")
                operation = ValidateOperation(config)

            case "show":
                printer.print(f"Showing resources defined in configuration '{config.config_file}'")
                operation = ShowOperation(config)

            case _:
                operation = None
                raise RuntimeError(f"unexpected action '{args.action}'")

        # if no organization has been specified as argument, process all configured ones.
        organizations = args.organization
        if len(organizations) == 0:
            organizations = [k for k, _ in config.organization_configs.items()]

        for organization in organizations:
            printer.print()
            org_config = config.organization_config(organization)

            # execute the requested action with the credential data and config.
            exit_code = max(exit_code, operation.execute(org_config, printer))

        sys.exit(exit_code)

    except Exception as e:
        if utils.is_debug_enabled():
            traceback.print_exception(e)

        utils.print_error(str(e))
        sys.exit(2)
