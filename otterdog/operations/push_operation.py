# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Optional

from colorama import Style

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider
from otterdog.utils import print_error

from . import Operation


class PushOperation(Operation):
    def __init__(self, push_message: Optional[str]):
        super().__init__()
        self.push_message = push_message

    def pre_execute(self) -> None:
        self.printer.println(f"Pushing organization definitions for configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")

        org_file_name = jsonnet_config.org_config_file

        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                print_error(f"invalid credentials\n{str(e)}")
                return 1

            with open(org_file_name, "r") as file:
                content = file.read()

            with open(jsonnet_config.jsonnet_bundle_file, "r") as file:
                bundle_content = file.read()

            gh_client = GitHubProvider(credentials)

            try:
                updated = gh_client.update_content(
                    org_config.github_id,
                    org_config.config_repo,
                    f"otterdog/{github_id}.jsonnet",
                    content,
                    self.push_message,
                )

                updated |= gh_client.update_content(
                    org_config.github_id,
                    org_config.config_repo,
                    "otterdog/jsonnetfile.json",
                    bundle_content,
                    self.push_message,
                )

                updated |= gh_client.update_content(
                    org_config.github_id,
                    org_config.config_repo,
                    "otterdog/jsonnetfile.lock.json",
                    "",
                    self.push_message,
                )

            except RuntimeError as e:
                print_error(
                    f"failed to push definition to repo '{org_config.github_id}/{org_config.config_repo}': {str(e)}"
                )
                return 1

            if updated:
                self.printer.println(
                    f"organization definition pushed to repo '{org_config.github_id}/{org_config.config_repo}'"
                )
            else:
                self.printer.println("no changes, nothing pushed")

            return 0
        finally:
            self.printer.level_down()
