# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Style

import organization as org
from config import OtterdogConfig, OrganizationConfig
from operation import Operation
from utils import IndentingPrinter


class ShowOperation(Operation):
    def __init__(self, config: OtterdogConfig):
        self.config = config
        self.jsonnet_config = config.jsonnet_config

    def execute(self, org_config: OrganizationConfig, printer: IndentingPrinter) -> int:
        github_id = org_config.github_id

        printer.print(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        printer.level_up()

        try:
            org_file_name = self.jsonnet_config.get_org_config_file(github_id)

            if not os.path.exists(org_file_name):
                printer.print_warn(f"configuration file '{org_file_name}' does not yet exist, run fetch first")
                return 1

            try:
                organization = org.load_from_file(github_id, self.jsonnet_config.get_org_config_file(github_id))
            except RuntimeError as ex:
                printer.print_warn(f"failed to load configuration: {str(ex)}")
                return 1

            for repo in organization.get_repos():
                printer.print(f"repository {Style.BRIGHT}{repo['name']}{Style.RESET_ALL}")

            return 0

        finally:
            printer.level_down()
