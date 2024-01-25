#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import associate_by_key, style

from . import Operation


class DeleteFileOperation(Operation):
    """
    Deletes a file identified by its path in an organization repository.
    """

    def __init__(self, repo: str, path: str, message: str):
        super().__init__()
        self._repo = repo
        self._path = path
        self._message = message

    @property
    def repo(self) -> str:
        return self._repo

    @property
    def path(self) -> str:
        return self._path

    @property
    def message(self) -> str:
        return self._message

    def pre_execute(self) -> None:
        self.printer.println(f"Deleting file '{self._path}' in organization repository '{self.repo}':")

    async def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file

            if not os.path.exists(org_file_name):
                self.printer.print_error(
                    f"configuration file '{org_file_name}' does not yet exist, run 'fetch-config' or 'import' first."
                )
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name, self.config)
            except RuntimeError as ex:
                self.printer.print_error(f"failed to load configuration: {str(ex)}")
                return 1

            try:
                credentials = self.config.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with GitHubProvider(credentials) as provider:
                rest_api = provider.rest_api

                repositories_by_name = associate_by_key(organization.repositories, lambda r: r.name)
                repo = repositories_by_name.get(self.repo)
                if repo is not None and repo.archived is False:
                    collected_error = None
                    repo_name = f"{github_id}/{repo.name}"
                    self.printer.print(
                        f"Deleting file '{style(self.path, bright=True)}' "
                        f"in repository '{style(repo_name, bright=True)}': "
                    )

                    try:
                        deleted_file = await rest_api.content.delete_content(
                            github_id, repo.name, self.path, self.message
                        )
                    except RuntimeError as e:
                        collected_error = e

                    if deleted_file is True:
                        self.printer.println(style("succeeded", fg="green"))
                    else:
                        self.printer.println(style("failed", fg="red"))

                    if collected_error is not None:
                        self.printer.println()
                        self.printer.print_error(f"failure deleting file\n{str(collected_error)}")
                        return 1
            return 0

        finally:
            self.printer.level_down()
