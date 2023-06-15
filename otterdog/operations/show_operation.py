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
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import print_error

from . import Operation


class ShowOperation(Operation):
    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        self.printer.println(f"Showing resources defined in configuration '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file

            if not os.path.exists(org_file_name):
                print_error(f"configuration file '{org_file_name}' does not yet exist, run fetch first")
                return 1

            try:
                organization = \
                    GitHubOrganization.load_from_file(github_id,
                                                      org_file_name,
                                                      self.config,
                                                      False)
            except RuntimeError as ex:
                print_error(f"failed to load configuration: {str(ex)}")
                return 1

            for model_object, parent_object in organization.get_model_objects():
                header = f"{Style.BRIGHT}{model_object.model_object_name}{Style.RESET_ALL}"

                if model_object.is_keyed():
                    key = model_object.get_key()
                    header = header + f"[{key}={Style.BRIGHT}\"{model_object.get_key_value()}\"{Style.RESET_ALL}"

                    if parent_object is not None:
                        header = header + f", {parent_object.model_object_name}=" \
                                          f"{Style.BRIGHT}\"{parent_object.get_key_value()}\"{Style.RESET_ALL}"

                    header = header + "]"

                self.printer.println()
                self.print_dict(model_object.to_model_dict(), header, "", Fore.BLACK)

            return 0

        finally:
            self.printer.level_down()
