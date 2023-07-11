# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Fore, Style

from otterdog.config import OrganizationConfig
from otterdog.models import FailureType
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import print_error, print_warn, print_info, is_info_enabled

from . import Operation


class ValidateOperation(Operation):
    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        self.printer.println(f"Validating configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file

            if not os.path.exists(org_file_name):
                print_error(
                    f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first"
                )
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name, self.config, False)
            except RuntimeError as ex:
                print_error(f"Validation failed\nfailed to load configuration: {str(ex)}")
                return 1

            validation_infos, validation_warnings, validation_errors = self.validate(organization)
            validation_count = validation_infos + validation_warnings + validation_errors

            if validation_count == 0:
                self.printer.println(f"{Fore.GREEN}Validation succeeded{Style.RESET_ALL}")
            else:
                if validation_errors == 0:
                    self.printer.println(
                        f"{Fore.GREEN}Validation succeeded{Style.RESET_ALL}: "
                        f"{validation_infos} info(s), {validation_warnings} warning(s), "
                        f"{validation_errors} error(s)"
                    )
                else:
                    self.printer.println(
                        f"{Fore.RED}Validation failed{Style.RESET_ALL}: "
                        f"{validation_infos} info(s), {validation_warnings} warning(s), "
                        f"{validation_errors} error(s)"
                    )

            if validation_infos > 0 and not is_info_enabled():
                self.printer.level_up()
                self.printer.println(
                    "in order to print validation infos, enable printing info message by " "adding '-v' flag."
                )
                self.printer.level_down()

            return validation_errors
        finally:
            self.printer.level_down()

    @staticmethod
    def validate(organization: GitHubOrganization) -> tuple[int, int, int]:
        context = organization.validate()

        validation_infos = 0
        validation_warnings = 0
        validation_errors = 0

        for failure_type, message in context.validation_failures:
            match failure_type:
                case FailureType.INFO:
                    print_info(message)
                    validation_infos += 1

                case FailureType.WARNING:
                    print_warn(message)
                    validation_warnings += 1

                case FailureType.ERROR:
                    print_error(message)
                    validation_errors += 1

        return validation_infos, validation_warnings, validation_errors
