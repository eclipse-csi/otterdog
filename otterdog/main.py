# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import argparse
import json
import os
import sys

import utils
from bitwarden import BitwardenVault
from fetch import FetchOperation
from verify import VerifyOperation
from update import UpdateOperation
from jsonnet_config import JsonnetConfig

AUTH_JSON_FILE = "auth.json"

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
        subparser.add_argument("organization", help="the github id of the organization")
        subparser.add_argument("--auth", "-a", help=f"authorization config file, defaults to '{AUTH_JSON_FILE}'",
                               action="store", default=AUTH_JSON_FILE)
        subparser.add_argument("--data", "-d", help="data directory", action="store", default=parent_dir)
        subparser.add_argument("--verbose", "-v", action="count", default=0)

    args = parser.parse_args()

    utils.init(args.verbose)
    config = JsonnetConfig(args.data)

    organization = args.organization

    # load and parse the authorization file.
    auth_file = args.auth
    if not os.path.exists(auth_file):
        msg = f"authorization file '{auth_file}' not found"
        utils.exit_with_message(msg, 1)

    with open(auth_file) as f:
        auth_configs = json.load(f)

    # find a config matching the organization we are processing.
    auth_config = next((c for c in auth_configs["organizations"] if c.get("github_id") == organization), None)
    if auth_config is None:
        utils.exit_with_message(f"no authorization config found for organization '{organization}'", 1)

    provider_data = auth_config.get("provider")
    if provider_data is None:
        utils.exit_with_message(f"no credential provider data specified for organization '{organization}'", 1)

    provider_type = provider_data.get("type")
    match provider_type:
        case "bitwarden":
            bitwarden_vault = BitwardenVault()
            credentials = bitwarden_vault.get_credentials(organization, provider_data)

        case _:
            credentials = None
            utils.exit_with_message(f"unsupported credential provider '{provider_type}'", 1)

    # execute the requested action with the credential data and config.
    match args.action:
        case "verify":
            utils.print_info("verify configuration for organization '{}'".format(organization))
            exit_code = VerifyOperation(credentials).execute(organization, config)

        case "fetch":
            utils.print_info("fetch configuration for organization '{}'".format(organization))
            exit_code = FetchOperation(credentials).execute(organization, config)

        case "update":
            utils.print_info("update configuration for organization '{}'".format(organization))
            exit_code = UpdateOperation(credentials).execute(organization, config)

        case _:
            exit_code = 1
            utils.print_err(f"unexpected action {args.action}")

    sys.exit(exit_code)
