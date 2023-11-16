# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************
import os

from colorama import Style, Fore

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider
from otterdog.utils import print_error, is_info_enabled

from . import Operation
from ..models.github_organization import GitHubOrganization


class ListMembersOperation(Operation):
    def __init__(self, two_factor_disabled: bool):
        super().__init__()
        self.two_factor_disabled = two_factor_disabled

    def pre_execute(self) -> None:
        if is_info_enabled():
            self.printer.println(f"Listing members for configuration at '{self.config.config_file}'")

    def post_execute(self) -> None:
        pass

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file

            if not os.path.exists(org_file_name):
                print_error(
                    f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first"
                )
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name, self.config)
            except RuntimeError as ex:
                print_error(f"failed to load configuration: {str(ex)}")
                return 1

            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                print_error(f"invalid credentials\n{str(e)}")
                return 1

            with GitHubProvider(credentials) as provider:
                members = provider.rest_api.org.list_members(github_id, self.two_factor_disabled)

            if self.two_factor_disabled is True:
                all_members = provider.rest_api.org.list_members(github_id, False)
                two_factor_status = (
                    f"{Fore.GREEN}enabled{Style.RESET_ALL}"
                    if organization.settings.two_factor_requirement is True
                    else f"{Fore.RED}disabled{Style.RESET_ALL}"
                )

                member_status = (
                    f"{Fore.GREEN}{len(members)}{Style.RESET_ALL}"
                    if len(members) == 0
                    else f"{Fore.RED}{len(members)}{Style.RESET_ALL}"
                )

                self.printer.println(
                    f"Found {member_status} / {len(all_members)} members with 2FA disabled. "
                    f"Organization has 2FA '{two_factor_status}'"
                )
            else:
                self.printer.println(f"Found {len(members)} members.")

            return 0
        finally:
            self.printer.level_down()
