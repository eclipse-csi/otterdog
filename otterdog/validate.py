# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from colorama import Fore, Style

from operation import Operation
from config import OtterdogConfig, OrganizationConfig
import organization as org


class ValidateOperation(Operation):
    def __init__(self, config: OtterdogConfig):
        self.config = config
        self.jsonnet_config = config.jsonnet_config

    def execute(self, org_config: OrganizationConfig) -> int:
        print(f"{Style.BRIGHT}[{org_config.name}]{Style.RESET_ALL}", end='')

        github_id = org_config.github_id
        org_file_name = self.jsonnet_config.get_org_config_file(github_id)

        if not os.path.exists(org_file_name):
            print(f"{Fore.RED} failed:{Style.RESET_ALL} configuration file '{org_file_name}' does not exist")
            return 1

        try:
            org.load_from_file(github_id, self.jsonnet_config.get_org_config_file(github_id))
        except RuntimeError as ex:
            print(f"{Fore.RED} failed:{Style.RESET_ALL} failed to load configuration: {str(ex)}")
            return 1

        print(f"{Fore.GREEN} success")
        return 0
