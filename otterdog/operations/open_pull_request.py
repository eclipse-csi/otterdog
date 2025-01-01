#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import filecmp
from typing import TYPE_CHECKING

from aiofiles import open

from otterdog.providers.github import GitHubProvider
from otterdog.utils import get_approval

from . import Operation
from .local_plan import LocalPlanOperation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig
    from otterdog.providers.github.rest import RestApi


class OpenPullRequestOperation(Operation):
    """
    Creates a pull request for local configuration changes of an organization in its meta-data repository.
    """

    def __init__(self, branch: str, title: str, author: str | None):
        super().__init__()
        self._branch = branch
        self._title = title
        self._author = author

    @property
    def branch(self) -> str:
        return self._branch

    @property
    def title(self) -> str:
        return self._title

    @property
    def author(self) -> str | None:
        return self._author

    def pre_execute(self) -> None:
        self.printer.println("Open PR for local configuration changes:")

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

        org_file_name = jsonnet_config.org_config_file
        if not await self.check_config_file_exists(org_file_name):
            return 1

        try:
            credentials = self.get_credentials(org_config, only_token=True)
        except RuntimeError as ex:
            self.printer.print_error(f"invalid credentials\n{ex!s}")
            return 1

        self.printer.level_up()

        try:
            async with open(org_file_name) as file:
                local_configuration = await file.read()

            async with GitHubProvider(credentials) as provider:
                rest_api = provider.rest_api

                try:
                    default_branch = await rest_api.repo.get_default_branch(
                        org_config.github_id, org_config.config_repo
                    )

                    current_definition = await provider.get_content(
                        github_id,
                        org_config.config_repo,
                        f"otterdog/{github_id}.jsonnet",
                        default_branch,
                    )

                    current_config_file = org_config.jsonnet_config.org_config_file + "-BASE"
                    async with open(current_config_file, "w") as file:
                        await file.write(current_definition)

                    if filecmp.cmp(current_config_file, org_config.jsonnet_config.org_config_file):
                        self.printer.println("no local changes, no PR has been opened")
                        return 0

                    self.printer.println("The following changes compared to the current configuration exist locally:")
                    self.printer.println()
                    self.printer.level_up()

                    try:
                        operation = LocalPlanOperation("-BASE", "*", False, False, "")
                        operation.init(self.config, self.printer)
                        valid_config = await operation.generate_diff(org_config)
                    finally:
                        self.printer.level_down()

                    if valid_config != 0:
                        self.printer.println("the local configuration contains validation error")
                        return 1

                    self.printer.println()
                    self.printer.println(
                        "Do you want to open a PR with these changes? "
                        "(Only 'yes' or 'y' will be accepted as approval)\n"
                    )

                    self.printer.print("[bold]Enter a value:[/] ")
                    if not get_approval():
                        self.printer.println("\nOpen PR cancelled.")
                        return 1

                    pr_number = await self._create_pull_request(
                        rest_api,
                        org_config,
                        default_branch,
                        local_configuration,
                    )

                    self.printer.println(
                        f"created pull request #{pr_number} at "
                        f"https://github.com/{org_config.github_id}/{org_config.config_repo}/pull/{pr_number}"
                    )
                except RuntimeError as e:
                    self.printer.print_error(
                        "failed to open pull request in repo "
                        f"'{org_config.github_id}/{org_config.config_repo}': {e!s}"
                    )
                    return 1

            return 0
        finally:
            self.printer.level_down()

    async def _create_pull_request(
        self,
        rest_api: RestApi,
        org_config: OrganizationConfig,
        default_branch: str,
        local_configuration: str,
    ) -> str:
        default_branch_data = await rest_api.reference.get_branch_reference(
            org_config.github_id,
            org_config.config_repo,
            default_branch,
        )
        default_branch_sha = default_branch_data["object"]["sha"]
        branch_name = f"otterdog/{self.branch}"

        await rest_api.reference.create_reference(
            org_config.github_id,
            org_config.config_repo,
            branch_name,
            default_branch_sha,
        )

        await rest_api.content.update_content(
            org_config.github_id,
            org_config.config_repo,
            f"otterdog/{org_config.github_id}.jsonnet",
            local_configuration,
            branch_name,
        )

        if self.author is not None:
            body = f"This PR has been created automatically on behalf of @{self.author} using the otterdog cli."
        else:
            body = "This PR has been created automatically using the otterdog cli."

        pull_request_data = await rest_api.pull_request.create_pull_request(
            org_config.github_id,
            org_config.config_repo,
            self.title,
            branch_name,
            default_branch,
            body,
        )

        return pull_request_data["number"]
