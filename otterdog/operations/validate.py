#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.logging import is_info_enabled
from otterdog.models import FailureType
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig
    from otterdog.jsonnet import JsonnetConfig


class ValidateOperation(Operation):
    """
    Validates local organization configurations.
    """

    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        self.printer.println("Validating organization configurations:")

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        await jsonnet_config.init_template()

        self._print_project_header(org_config, org_index, org_count)
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file
            if not await self.check_config_file_exists(org_file_name):
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name)
            except RuntimeError as ex:
                self.printer.print_error(f"Validation failed\nfailed to load configuration: {ex!s}")
                return 1

            try:
                credentials = self.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            async with GitHubProvider(credentials) as provider:
                validation_infos, validation_warnings, validation_errors = await self.validate(
                    organization, jsonnet_config, provider
                )
                validation_count = validation_infos + validation_warnings + validation_errors

            if validation_count == 0:
                self.printer.println("[green]Validation succeeded[/]")
            else:
                if validation_errors == 0:
                    self.printer.println(
                        f"[green]Validation succeeded[/]': "
                        f"{validation_infos} info(s), {validation_warnings} warning(s), "
                        f"{validation_errors} error(s)"
                    )
                else:
                    self.printer.println(
                        f"[red]Validation failed[/]: "
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

    async def validate(
        self,
        organization: GitHubOrganization,
        jsonnet_config: JsonnetConfig,
        provider: GitHubProvider,
    ) -> tuple[int, int, int]:
        if organization.secrets_resolved is True:
            raise RuntimeError("validation requires an unresolved model.")

        context = await organization.validate(self.config, jsonnet_config, self.credential_resolver, provider)

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
