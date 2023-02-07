# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

import utils
from credentials import Credentials
from github import Github
from jsonnet_config import JsonnetConfig
from operations import Operation
from organization import load_from_github


class FetchOperation(Operation):
    def __init__(self, credentials: Credentials):
        self.gh = Github(credentials)

    def execute(self, org_id: str, config: JsonnetConfig) -> int:
        organization = load_from_github(org_id, self.gh)
        output = organization.write_jsonnet_config(config)

        output_dir = config.get_orgs_config_dir()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        output_file_name = config.get_org_config_file(org_id)
        utils.print_info(f"writing configuration to file '{output_file_name}'")

        with open(output_file_name, "w") as file:
            file.write(output)

        return 0
