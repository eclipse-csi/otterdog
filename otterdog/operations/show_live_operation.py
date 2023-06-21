# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from colorama import Style, Fore

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import Github
from otterdog.utils import print_error, print_warn

from . import Operation


class ShowLiveOperation(Operation):
    def __init__(self, no_web_ui: bool):
        super().__init__()
        self.no_web_ui = no_web_ui

    def pre_execute(self) -> None:
        self.printer.println("Showing live resources for organizations")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                print_error(f"invalid credentials\n{str(e)}")
                return 1

            gh_client = Github(credentials)

            if self.no_web_ui is True:
                print_warn("the Web UI will not be queried as '--no-web-ui' has been specified, "
                           "the resulting config will be incomplete")

            organization = \
                GitHubOrganization.load_from_provider(github_id,
                                                      jsonnet_config,
                                                      gh_client,
                                                      self.no_web_ui,
                                                      self.printer)

            for model_object, parent_object in organization.get_model_objects():
                self.printer.println()
                model_header = model_object.get_model_header(parent_object)
                self.print_dict(model_object.to_model_dict(), model_header, "", Fore.BLACK)

            return 0

        finally:
            self.printer.level_down()
