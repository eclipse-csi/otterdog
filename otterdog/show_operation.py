# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Style, Fore

import organization as org
from config import OtterdogConfig, OrganizationConfig
from operation import Operation
from utils import IndentingPrinter


class ShowOperation(Operation):
    def __init__(self):
        self.config = None
        self.jsonnet_config = None
        self._printer = None

    @property
    def printer(self) -> IndentingPrinter:
        return self._printer

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        self.config = config
        self.jsonnet_config = self.config.jsonnet_config
        self._printer = printer

    def pre_execute(self) -> None:
        self.printer.print(f"Showing resources defined in configuration '{self.config.config_file}'")

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
                organization = org.load_from_file(github_id, self.jsonnet_config.get_org_config_file(github_id))
            except RuntimeError as ex:
                self.printer.print_warn(f"failed to load configuration: {str(ex)}")
                return 1

            self.print_dict(organization.get_settings(), f"{Style.BRIGHT}settings{Style.RESET_ALL}", "", Fore.BLACK)

            for webhook in organization.get_webhooks():
                self.printer.print()
                self.print_dict(webhook, f"{Style.BRIGHT}webhook{Style.RESET_ALL}", "", Fore.BLACK)

            for repo in organization.get_repos():
                repo_name = repo["name"]
                repo_data = repo.copy()
                branch_protection_rules = repo_data.pop("branch_protection_rules")

                self.printer.print()
                self.print_dict(repo_data,
                                f"{Style.BRIGHT}repository[\"{repo['name']}\"]{Style.RESET_ALL}",
                                "", Fore.BLACK)

                for rule in branch_protection_rules:
                    self.printer.print()
                    self.print_dict(rule,
                                    f"{Style.BRIGHT}branch_protection_rule[repo=\"{repo_name}\"]{Style.RESET_ALL}",
                                    "", Fore.BLACK)

            return 0

        finally:
            self.printer.level_down()
