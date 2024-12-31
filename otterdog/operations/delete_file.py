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
from otterdog.utils import associate_by_key

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


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
                    collected_error = None
                    repo_name = f"{github_id}/{repo.name}"
                    self.printer.print(
                        f"Deleting file '[bold]{self.path}[/]' " f"in repository '[bold]{repo_name}[/]': "
                    )

                    try:
                        deleted_file = await rest_api.content.delete_content(
                            github_id, repo.name, self.path, self.message
                        )
                    except RuntimeError as e:
                        collected_error = e

                    if deleted_file is True:
                        self.printer.println("[green]succeeded[/]")
                    else:
                        self.printer.println("[red]succeeded[/]")

                    if collected_error is not None:
                        self.printer.println()
                        self.printer.print_error(f"failure deleting file\n{collected_error!s}")
                        return 1
            return 0

        finally:
            self.printer.level_down()
