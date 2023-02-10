# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import argparse
import os
import sys
import traceback

import utils
from fetch import FetchOperation
from verify import VerifyOperation
from update import UpdateOperation
from config import OtterdogConfig

CONFIG_FILE = "otterdog.json"

# main entry point
if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.realpath(__file__))
    # get the parent dir of the script root as the source files
    # are contained inside the otterdog directory.
    parent_dir = os.path.dirname(script_dir)

    # command line parsing.
    parser = argparse.ArgumentParser(prog="otterdog.sh",
                                     description="sync / modify github settings for an organization.")

    subparsers = parser.add_subparsers(dest="action", required=True)

    verify_parser = subparsers.add_parser("verify")
    sync_parser = subparsers.add_parser("fetch")
    update_parser = subparsers.add_parser("update")

    for subparser in [verify_parser, sync_parser, update_parser]:
        subparser.add_argument("organization", nargs="*", help="the github id of the organization")
        subparser.add_argument("--config", "-c", help=f"configuration file, defaults to '{CONFIG_FILE}'",
                               action="store", default=CONFIG_FILE)
        subparser.add_argument("--verbose", "-v", action="count", default=0)

    args = parser.parse_args()

    utils.init(args.verbose)

    try:
        config = OtterdogConfig.from_file(args.config)
        jsonnet_config = config.jsonnet_config

        exit_code = 0
        for organization in args.organization:
            org_config = config.organization_config(organization)

            # execute the requested action with the credential data and config.
            match args.action:
                case "verify":
                    utils.print_info("verify configuration for organization '{}'".format(organization))
                    exit_code = max(exit_code, VerifyOperation(config).execute(org_config))

                case "fetch":
                    utils.print_info("fetch configuration for organization '{}'".format(organization))
                    exit_code = max(exit_code, FetchOperation(config).execute(org_config))

                case "update":
                    utils.print_info("update configuration for organization '{}'".format(organization))
                    exit_code = max(exit_code, UpdateOperation(config).execute(org_config))

                case _:
                    utils.print_err(f"unexpected action {args.action}")
                    sys.exit(2)

        sys.exit(exit_code)

    except Exception as e:
        if utils.is_debug_enabled():
            exc_info = sys.exc_info()
            traceback.print_exc(exc_info)

        utils.exit_with_message(str(e), 1)
