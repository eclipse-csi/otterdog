# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Fore, Style

import organization as org
from config import OtterdogConfig, OrganizationConfig
from operation import Operation
from utils import IndentingPrinter


class ValidateOperation(Operation):
    def __init__(self):
        self.config = None
        self.jsonnet_config = None
        self.printer = None

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        self.config = config
        self.jsonnet_config = self.config.jsonnet_config
        self.printer = printer

        self.printer.print(f"Validating configuration at '{config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.print(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = self.jsonnet_config.get_org_config_file(github_id)

            if not os.path.exists(org_file_name):
                self.printer.print_warn(f"configuration file '{org_file_name}' does not yet exist, run fetch first")
                return 1

            try:
                org.load_from_file(github_id, self.jsonnet_config.get_org_config_file(github_id))
            except RuntimeError as ex:
                self.printer.print_error(f"Validation failed\nfailed to load configuration: {str(ex)}")
                return 1

            self.printer.print(f"{Fore.GREEN}Validation succeeded{Style.RESET_ALL}")
            return 0

        finally:
            self.printer.level_down()
