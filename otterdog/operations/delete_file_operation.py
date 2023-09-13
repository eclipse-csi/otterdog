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
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import print_error

from . import Operation


class DeleteFileOperation(Operation):
    def __init__(self, repo: str, path: str, message: str):
        super().__init__()
        self._repo = repo
        self._path = path
        self._message = message

    def pre_execute(self) -> None:
        self.printer.println(f"Deleting file in a repo for configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file

            if not os.path.exists(org_file_name):
                print_error(
                    f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first"
                )
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name, self.config)
            except RuntimeError as ex:
                print_error(f"failed to load configuration: {str(ex)}")
                return 1

            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                print_error(f"invalid credentials\n{str(e)}")
                return 1

            rest_api = GitHubProvider(credentials).rest_api

            for repo in organization.repositories:
                if repo.archived is True:
                    continue

                if repo.name != self._repo:
                    continue

                self.printer.println(f'Deleting file in {Style.BRIGHT}repository["{repo.name}"]{Style.RESET_ALL}')

                deleted_file = rest_api.content.delete_content(github_id, repo.name, self._path, self._message)

                if deleted_file is True:
                    self.printer.level_up()
                    self.printer.println(f"deleted file '{self._path}'")
                    self.printer.level_down()

            return 0

        finally:
            self.printer.level_down()
