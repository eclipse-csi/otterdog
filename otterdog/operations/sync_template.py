#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import associate_by_key, is_set_and_present

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


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

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        await jsonnet_config.init_template()

        self._print_project_header(org_config, org_index, org_count)
        self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file
            if not await self.check_config_file_exists(org_file_name):
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name)
            except RuntimeError as ex:
                self.printer.print_error(f"failed to load configuration: {ex!s}")
                return 1

            try:
                credentials = self.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            async with GitHubProvider(credentials) as provider:
                rest_api = provider.rest_api

                repositories_by_name = associate_by_key(organization.repositories, lambda r: r.name)
                repo = repositories_by_name.get(self.repo)
                if repo is not None and repo.archived is False:
                    if is_set_and_present(repo.template_repository):
                        self.printer.println(f'Syncing repository["[bold]{repo.name}[/]"]')
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
