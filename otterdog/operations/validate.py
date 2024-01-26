#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os

from otterdog.config import OrganizationConfig
from otterdog.models import FailureType
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import is_info_enabled, style

from . import Operation


class ValidateOperation(Operation):
    """
    Validates local organization configurations.
    """

    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        self.printer.println("Validating organization configurations:")

    async def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file

            if not os.path.exists(org_file_name):
                self.printer.print_error(
                    f"configuration file '{org_file_name}' does not yet exist, run 'fetch-config' or 'import' first."
                )
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name, self.config)
            except RuntimeError as ex:
                self.printer.print_error(f"Validation failed\nfailed to load configuration: {str(ex)}")
                return 1

            validation_infos, validation_warnings, validation_errors = self.validate(
                organization, jsonnet_config.template_dir
            )
            validation_count = validation_infos + validation_warnings + validation_errors

            if validation_count == 0:
                self.printer.println(style("Validation succeeded", fg="green"))
            else:
                if validation_errors == 0:
                    self.printer.println(
                        f"{style('Validation succeeded', fg='green')}: "
                        f"{validation_infos} info(s), {validation_warnings} warning(s), "
                        f"{validation_errors} error(s)"
                    )
                else:
                    self.printer.println(
                        f"{style('Validation failed', fg='red')}: "
                        f"{validation_infos} info(s), {validation_warnings} warning(s), "
                        f"{validation_errors} error(s)"
                    )

            if validation_infos > 0 and not is_info_enabled():
                self.printer.level_up()
                self.printer.println(
                    "in order to print validation infos, enable printing info messages by adding '-v' flag."
                )
                self.printer.level_down()

            return validation_errors
        finally:
            self.printer.level_down()

    def validate(self, organization: GitHubOrganization, template_dir: str) -> tuple[int, int, int]:
        if organization.secrets_resolved is True:
            raise RuntimeError("validation requires an unresolved model.")

        context = organization.validate(template_dir)

        validation_infos = 0
        validation_warnings = 0
        validation_errors = 0

        for failure_type, message in context.validation_failures:
            match failure_type:
                case FailureType.INFO:
                    self.printer.print_info(message)
                    validation_infos += 1

                case FailureType.WARNING:
                    self.printer.print_warn(message)
                    validation_warnings += 1

                case FailureType.ERROR:
                    self.printer.print_error(message)
                    validation_errors += 1

        return validation_infos, validation_warnings, validation_errors
