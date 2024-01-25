#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider
from otterdog.utils import get_approval, style

from . import Operation


class FetchOperation(Operation):
    """
    Fetches the current configuration from the meta-data repository of an organization.
    """

    def __init__(self, force_processing: bool, pull_request: str):
        super().__init__()
        self.force_processing = force_processing
        self.pull_request = pull_request

    def pre_execute(self) -> None:
        self.printer.println("Fetching organization configurations:")

    async def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config

        self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]")

        org_file_name = jsonnet_config.org_config_file

        if os.path.exists(org_file_name) and not self.force_processing:
            self.printer.println()
            self.printer.println(style("Definition already exists", bright=True) + f" at '{org_file_name}'.")
            self.printer.println("  Performing this action will overwrite its contents.")
            self.printer.println("  Do you want to continue? (Only 'yes' or 'y' will be accepted to approve)\n")

            self.printer.print(f"{style('Enter a value:', bright=True)} ")
            if not get_approval():
                self.printer.println("\nFetch cancelled.")
                return 1

        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with GitHubProvider(credentials) as provider:
                try:
                    if self.pull_request is not None:
                        ref = await provider.get_ref_for_pull_request(
                            org_config.github_id, org_config.config_repo, self.pull_request
                        )
                    else:
                        ref = None

                    definition = await provider.get_content(
                        org_config.github_id,
                        org_config.config_repo,
                        f"otterdog/{github_id}.jsonnet",
                        ref,
                    )
                except RuntimeError:
                    self.printer.print_error(f"failed to fetch definition from repo '{org_config.config_repo}'")
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
