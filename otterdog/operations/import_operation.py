# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Style

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import Github

from . import Operation


class ImportOperation(Operation):
    def __init__(self, force_processing: bool, no_web_ui: bool):
        super().__init__()
        self.force_processing = force_processing
        self.no_web_ui = no_web_ui

    def pre_execute(self) -> None:
        self.printer.print(f"Importing resources for configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.print(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")

        org_file_name = self.jsonnet_config.get_org_config_file(github_id)

        if os.path.exists(org_file_name) and not self.force_processing:
            self.printer.print(f"\n{Style.BRIGHT}Definition already exists{Style.RESET_ALL} at "
                               f"'{org_file_name}'.\n"
                               f"  Performing this action will overwrite its contents.\n"
                               f"  Do you want to continue?\n"
                               f"  Only 'yes' will be accepted to approve.\n\n")

            self.printer.print(f"  {Style.BRIGHT}Enter a value:{Style.RESET_ALL} ", end='')
            answer = input()
            if answer != "yes":
                self.printer.print("\nImport cancelled.")
                return 1

        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            gh_client = Github(credentials)

            if self.no_web_ui is True:
                self.printer.print_warn("The Web UI will not be queried as '--no-web-ui' has been specified, "
                                        "the resulting config will be incomplete")

            organization = \
                GitHubOrganization.load_from_provider(github_id,
                                                      self.jsonnet_config,
                                                      gh_client,
                                                      self.no_web_ui,
                                                      self.printer)

            ignored_keys = gh_client.web_org_settings if self.no_web_ui else set()
            output = organization.to_jsonnet(self.jsonnet_config, ignored_keys)

            output_dir = self.jsonnet_config.orgs_dir
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            with open(org_file_name, "w") as file:
                file.write(output)

            self.printer.print(f"organization definition written to '{org_file_name}'")

            return 0
        finally:
            self.printer.level_down()
