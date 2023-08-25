# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************
import json

from colorama import Style

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider
from otterdog.utils import print_error

from . import Operation


class ListAppsOperation(Operation):
    def __init__(self, json_output: bool):
        super().__init__()
        self.json_output = json_output

    def pre_execute(self) -> None:
        self.printer.println(f"Listing app installations for configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.println(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                print_error(f"invalid credentials\n{str(e)}")
                return 1

            gh_client = GitHubProvider(credentials)

            apps = gh_client.rest_api.org.get_app_installations(github_id)

            if self.json_output:
                for app in apps:
                    filtered = {key: app[key] for key in ["app_id", "app_slug", "permissions"]}
                    self.printer.println()
                    self.printer.println(json.dumps(filtered, indent=2))

            else:
                for app in apps:
                    filtered = {key: app[key] for key in ["app_id", "permissions"]}
                    self.printer.println()
                    self.print_dict(filtered, f"app['{app['app_slug']}']", "", "")

            return 0
        finally:
            self.printer.level_down()
