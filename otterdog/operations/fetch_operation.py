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
from otterdog.providers.github import GitHubProvider
from otterdog.utils import print_error, get_approval

from . import Operation


class FetchOperation(Operation):
    def __init__(self, force_processing: bool, pull_request: str):
        super().__init__()
        self.force_processing = force_processing
        self.pull_request = pull_request

    def pre_execute(self) -> None:
        self.printer.println(f"Fetching organization definitions for configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")

        org_file_name = jsonnet_config.org_config_file

        if os.path.exists(org_file_name) and not self.force_processing:
            self.printer.println(
                f"\n{Style.BRIGHT}Definition already exists{Style.RESET_ALL} at "
                f"'{org_file_name}'.\n"
                f"  Performing this action will overwrite its contents.\n"
                f"  Do you want to continue?\n"
                f"  Only 'yes' or 'y' will be accepted to approve.\n"
            )

            self.printer.print(f"  {Style.BRIGHT}Enter a value:{Style.RESET_ALL} ")
            if not get_approval():
                self.printer.println("\nFetch cancelled.")
                return 1

        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                print_error(f"invalid credentials\n{str(e)}")
                return 1

            gh_client = GitHubProvider(credentials)

            try:
                if self.pull_request is not None:
                    ref = gh_client.get_ref_for_pull_request(
                        org_config.github_id, org_config.config_repo, self.pull_request
                    )
                else:
                    ref = None

                definition = gh_client.get_content(
                    org_config.github_id,
                    org_config.config_repo,
                    f"otterdog/{github_id}.jsonnet",
                    ref,
                )
            except RuntimeError:
                print_error(f"failed to fetch definition from repo '{org_config.config_repo}'")
                return 1

            output_dir = jsonnet_config.org_dir
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            with open(org_file_name, "w") as file:
                file.write(definition)

            if ref is not None:
                self.printer.println(
                    f"organization definition fetched from pull request " f"#{self.pull_request} to '{org_file_name}'"
                )
            else:
                self.printer.println(f"organization definition fetched from default branch to '{org_file_name}'")

            return 0
        finally:
            self.printer.level_down()
