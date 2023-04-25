#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from colorama import Style

from otterdog.config import OtterdogConfig, OrganizationConfig
from otterdog.providers.github import Github
from otterdog.utils import IndentingPrinter

from . import Operation


class PushOperation(Operation):
    def __init__(self):
        self.config = None
        self.jsonnet_config = None
        self._printer = None

    @property
    def printer(self) -> IndentingPrinter:
        return self._printer

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        self.config = config
        self.jsonnet_config = self.config.jsonnet_config
        self._printer = printer

    def pre_execute(self) -> None:
        self.printer.print(f"Pushing organization definitions for configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.print(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")

        org_file_name = self.jsonnet_config.get_org_config_file(github_id)

        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with open(org_file_name, "r") as file:
                content = file.read()

            with open(self.jsonnet_config.get_jsonnet_bundle_file(), "r") as file:
                bundle_content = file.read()

            gh_client = Github(credentials)

            try:
                message = self.config.push_message

                gh_client.update_content(org_config.github_id,
                                         self.config.config_repo,
                                         f"otterdog/{github_id}.jsonnet",
                                         content,
                                         message)

                gh_client.update_content(org_config.github_id,
                                         self.config.config_repo,
                                         f"otterdog/jsonnetfile.json",
                                         bundle_content,
                                         message)

                gh_client.update_content(org_config.github_id,
                                         self.config.config_repo,
                                         f"otterdog/jsonnetfile.lock.json",
                                         "",
                                         message)

            except RuntimeError as e:
                self.printer.print_error(f"failed to push definition to repo '{self.config.config_repo}': {str(e)}")
                return 1

            self.printer.print(f"organization definition pushed to '{org_file_name}'")

            return 0
        finally:
            self.printer.level_down()
