# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

import utils
from github import Github
from config import OtterdogConfig, OrganizationConfig
from operation import Operation
from organization import load_from_github


class FetchOperation(Operation):
    def __init__(self, config: OtterdogConfig):
        self.config = config
        self.jsonnet_config = self.config.jsonnet_config

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        credentials = self.config.get_credentials(org_config)
        gh_client = Github(credentials)

        organization = load_from_github(github_id, gh_client)
        output = organization.write_jsonnet_config(self.jsonnet_config)

        output_dir = self.jsonnet_config.orgs_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        output_file_name = self.jsonnet_config.get_org_config_file(github_id)
        utils.print_info(f"writing configuration to file '{output_file_name}'")

        with open(output_file_name, "w") as file:
            file.write(output)

        return 0
