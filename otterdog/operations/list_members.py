#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import is_info_enabled

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class ListMembersOperation(Operation):
    """
    Prints statistical information about members of the organization.
    """

    def __init__(self, two_factor_disabled: bool):
        super().__init__()
        self._two_factor_disabled = two_factor_disabled

    @property
    def two_factor_disabled(self) -> bool:
        return self._two_factor_disabled

    @property
    def two_factor_enabled(self) -> bool:
        return self._two_factor_disabled

    def pre_execute(self) -> None:
        if is_info_enabled():
            self.printer.println("Listing organization members:")

    def post_execute(self) -> None:
        pass

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
                self.printer.print_error(f"failed to load configuration: {ex!s}")
                return 1

            try:
                credentials = self.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            async with GitHubProvider(credentials) as provider:
                members = await provider.rest_api.org.list_members(github_id, self.two_factor_disabled)

                if self.two_factor_disabled is True:
                    all_members = await provider.rest_api.org.list_members(github_id, False)
                    two_factor_status = (
                        "[green]enabled[/]"
                        if organization.settings.two_factor_requirement is True
                        else "[red]disabled[/]"
                    )

                    member_status = f"[green]{len(members)!s}[/]" if len(members) == 0 else f"[red]{len(members)!s}[/]"

                    self.printer.println(
                        f"Found {member_status} / {len(all_members)} members with 2FA disabled. "
                        f"Organization has 2FA '{two_factor_status}'"
                    )
                else:
                    self.printer.println(f"Found {len(members)} members.")

            return 0
        finally:
            self.printer.level_down()
