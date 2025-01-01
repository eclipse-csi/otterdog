#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from aiofiles import open, os, ospath

from otterdog.providers.github import GitHubProvider

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class FetchOperation(Operation):
    """
    Fetches the current configuration from the meta-data repository of an organization.
    """

    def __init__(self, force_processing: bool, pull_request: str, suffix: str = "", ref: str | None = None):
        super().__init__()
        self._force_processing = force_processing
        self._pull_request = pull_request
        self._suffix = suffix
        self._ref = ref

    @property
    def force_processing(self) -> bool:
        return self._force_processing

    @property
    def pull_request(self) -> str:
        return self._pull_request

    @property
    def suffix(self) -> str:
        return self._suffix

    @property
    def ref(self) -> str | None:
        return self._ref

    def pre_execute(self) -> None:
        self.printer.println("Fetching organization configurations:")

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config

        self._print_project_header(org_config, org_index, org_count)

        org_file_name = jsonnet_config.org_config_file + self.suffix
        if not await self.check_config_file_overwrite_if_exists(org_file_name, self.force_processing):
            return 1

        self.printer.level_up()

        try:
            try:
                credentials = self.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            async with GitHubProvider(credentials) as provider:
                try:
                    if self.pull_request is not None:
                        ref = await provider.get_ref_for_pull_request(
                            org_config.github_id, org_config.config_repo, self.pull_request
                        )
                    else:
                        ref = self.ref

                    definition = await provider.get_content(
                        org_config.github_id,
                        org_config.config_repo,
                        f"otterdog/{github_id}.jsonnet",
                        ref,
                    )
                except RuntimeError:
                    self.printer.print_error(f"failed to fetch definition from repo '{org_config.config_repo}'")
                    return 1

            output_dir = jsonnet_config.org_dir
            if not await ospath.exists(output_dir):
                await os.makedirs(output_dir)

            async with open(org_file_name, "w") as file:
                await file.write(definition)

            if self.pull_request is not None:
                self.printer.println(
                    f"organization definition fetched from pull request " f"#{self.pull_request} to '{org_file_name}'"
                )
            else:
                self.printer.println(f"organization definition fetched from default branch to '{org_file_name}'")

            return 0
        finally:
            self.printer.level_down()
