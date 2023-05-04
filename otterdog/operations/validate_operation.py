# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Fore, Style

from otterdog.config import OtterdogConfig, OrganizationConfig
from otterdog.utils import IndentingPrinter
from otterdog.models import FailureType
from otterdog.models.github_organization import GitHubOrganization, load_github_organization_from_file

from . import Operation


class ValidateOperation(Operation):
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
        self.printer.print(f"Validating configuration at '{self.config.config_file}'")

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
                organization = \
                    load_github_organization_from_file(github_id,
                                                       self.jsonnet_config.get_org_config_file(github_id),
                                                       self.config,
                                                       False)
            except RuntimeError as ex:
                self.printer.print_error(f"Validation failed\nfailed to load configuration: {str(ex)}")
                return 1

            return self.validate(organization)
        finally:
            self.printer.level_down()

    def validate(self, organization: GitHubOrganization) -> int:
        context = organization.validate()

        validation_warnings = 0
        validation_errors = 0

        for failure_type, message in context.validation_failures:
            match failure_type:
                case FailureType.WARNING:
                    self.printer.print_warn(message)
                    validation_warnings += 1

                case FailureType.ERROR:
                    self.printer.print_error(message)
                    validation_errors += 1

        validation_failures = validation_warnings + validation_errors

        if validation_failures == 0:
            self.printer.print(f"{Fore.GREEN}Validation succeeded{Style.RESET_ALL}")
        else:
            self.printer.print(f"{Fore.RED}Validation failed{Style.RESET_ALL}: "
                               f"{validation_warnings} warning(s), {validation_errors} error(s)")

        return validation_failures
