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


class ValidationStatus:
    def __init__(self):
        self.infos = 0
        self.warnings = 0
        self.errors = 0

    def total_notices(self, include_infos: bool = False) -> int:
        return self.warnings + self.errors + (self.infos if include_infos else 0)


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
                validation_status = await self.validate(organization, jsonnet_config, provider)

            if validation_status.total_notices() == 0:
                self.printer.println("[green]Validation succeeded[/]")
            else:
                if validation_status.errors == 0:
                    self.printer.println(
                        f"[green]Validation succeeded[/]': "
                        f"{validation_status.infos} info(s), {validation_status.warnings} warning(s), "
                        f"{validation_status.errors} error(s)"
                    )
                else:
                    self.printer.println(
                        f"[red]Validation failed[/]: "
                        f"{validation_status.infos} info(s), {validation_status.warnings} warning(s), "
                        f"{validation_status.errors} error(s)"
                    )

            if validation_status.infos > 0 and not is_info_enabled():
                self.printer.level_up()
                self.printer.println(
                    "in order to print validation infos, enable printing info messages by adding '-v' flag."
                )
                self.printer.level_down()

            return validation_status.errors
        finally:
            self.printer.level_down()

    async def validate(
        self,
        organization: GitHubOrganization,
        jsonnet_config: JsonnetConfig,
        provider: GitHubProvider,
    ) -> ValidationStatus:
        if organization.secrets_resolved is True:
            raise RuntimeError("validation requires an unresolved model.")

        context = await organization.validate(self.config, jsonnet_config, self.credential_resolver, provider)

        validation_status = ValidationStatus()

        for failure_type, message in context.validation_failures:
            match failure_type:
                case FailureType.INFO:
                    self.printer.print_info(message)
                    validation_status.infos += 1

                case FailureType.WARNING:
                    self.printer.print_warn(message)
                    validation_status.warnings += 1

                case FailureType.ERROR:
                    self.printer.print_error(message)
                    validation_status.errors += 1

        return validation_status
