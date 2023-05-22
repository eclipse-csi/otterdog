# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Style, Fore  # type: ignore

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization

from . import Operation


class ShowOperation(Operation):
    def __init__(self):
        super().__init__()

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
                organization = \
                    GitHubOrganization.load_from_file(github_id,
                                                      self.jsonnet_config.get_org_config_file(github_id),
                                                      self.config,
                                                      False)
            except RuntimeError as ex:
                self.printer.print_warn(f"failed to load configuration: {str(ex)}")
                return 1

            self.print_dict(organization.settings.to_model_dict(),
                            f"{Style.BRIGHT}settings{Style.RESET_ALL}",
                            "",
                            Fore.BLACK)

            for webhook in organization.webhooks:
                self.printer.print()
                self.print_dict(webhook.to_model_dict(),
                                f"{Style.BRIGHT}webhook{Style.RESET_ALL}",
                                "",
                                Fore.BLACK)

            for repo in organization.repositories:
                repo_data = repo.to_model_dict(False)

                self.printer.print()
                self.print_dict(repo_data,
                                f"{Style.BRIGHT}repository[\"{repo.name}\"]{Style.RESET_ALL}",
                                "",
                                Fore.BLACK)

                for rule in repo.branch_protection_rules:
                    self.printer.print()
                    self.print_dict(rule.to_model_dict(),
                                    f"{Style.BRIGHT}branch_protection_rule[repo=\"{repo.name}\"]{Style.RESET_ALL}",
                                    "",
                                    Fore.BLACK)

            return 0

        finally:
            self.printer.level_down()
