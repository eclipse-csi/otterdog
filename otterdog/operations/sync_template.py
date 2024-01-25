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
from otterdog.utils import associate_by_key, is_set_and_present, style

from . import Operation


class SyncTemplateOperation(Operation):
    """
    Syncs the contents of repositories created from a template repository.
    """

    def __init__(self, repo: str):
        super().__init__()
        self._repo = repo

    @property
    def repo(self) -> str:
        return self._repo

    def pre_execute(self) -> None:
        self.printer.println(f"Syncing organization repos '{self.repo}' from template master:")

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
                    f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first."
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
                    if is_set_and_present(repo.template_repository):
                        self.printer.println(f'Syncing repository["{style(repo.name, bright=True)}"]')
                        updated_files = await rest_api.repo.sync_from_template_repository(
                            github_id,
                            repo.name,
                            repo.template_repository,
                            repo.post_process_template_content,
                        )

                        self.printer.level_up()
                        for file in updated_files:
                            self.printer.println(f"updated file '{file}'")
                        self.printer.level_down()

            return 0

        finally:
            self.printer.level_down()
