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
from git import InvalidGitRepositoryError, Repo
from git.config import GitConfigParser

from otterdog.providers.github import GitHubProvider
from otterdog.utils import get_approval

from . import Operation
from .local_plan import LocalPlanOperation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class PushOperation(Operation):
    """
    Pushes a local configuration of an organization to its meta-data repository.
    """

    def __init__(self, show_diff: bool, force_processing: bool, push_message: str | None):
        super().__init__()
        self._show_diff = show_diff
        self._force_processing = force_processing
        self._push_message = push_message

    @property
    def show_diff(self) -> bool:
        return self._show_diff

    @property
    def push_message(self) -> str | None:
        return self._push_message

    @property
    def force_processing(self) -> bool:
        return self._force_processing

    def pre_execute(self) -> None:
        self.printer.println("Pushing organization configurations:")

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

        self.printer.level_up()

        try:
            try:
                credentials = self.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            # try to determine the git user configuration if possible
            # if no configuration can be found, omit adding author information

            try:
                git_config_reader = Repo(self.config.working_dir).config_reader()
            except InvalidGitRepositoryError:
                # if the config dir is not a git repo, just read the global config
                git_config_reader = GitConfigParser(None, read_only=True)

            if git_config_reader.has_option("user", "name"):
                author_name = git_config_reader.get_value("user", "name")
            else:
                author_name = None

            if git_config_reader.has_option("user", "email"):
                author_email = git_config_reader.get_value("user", "email")
            else:
                author_email = None

            if not author_name:
                author_name = None
                author_email = None

            async with open(org_file_name) as file:
                content = await file.read()

            async with GitHubProvider(credentials) as provider:
                try:
                    perform_update = True
                    updated_files = []

                    if self.show_diff:
                        perform_update = await self._display_diff(org_config, provider)

                    if perform_update:
                        if await provider.update_content(
                            org_config.github_id,
                            org_config.config_repo,
                            f"otterdog/{github_id}.jsonnet",
                            content,
                            None,
                            self.push_message,
                            author_name,
                            author_email,
                        ):
                            updated_files.append(f"otterdog/{github_id}.jsonnet")

                except RuntimeError as e:
                    self.printer.print_error(
                        f"failed to push definition to repo '{org_config.github_id}/{org_config.config_repo}': {e!s}"
                    )
                    return 1

            if len(updated_files) > 0:
                self.printer.println(
                    f"organization definition pushed to repo '{org_config.github_id}/{org_config.config_repo}': "
                )
                for updated_file in updated_files:
                    self.printer.println(f"  - '{updated_file}'")
            else:
                self.printer.println("no changes, nothing pushed")

            return 0
        finally:
            self.printer.level_down()

    async def _display_diff(self, org_config: OrganizationConfig, provider: GitHubProvider) -> bool:
        rest_api = provider.rest_api
        github_id = org_config.github_id

        default_branch = await rest_api.repo.get_default_branch(org_config.github_id, org_config.config_repo)

        try:
            current_definition = await provider.get_content(
                github_id,
                org_config.config_repo,
                f"otterdog/{github_id}.jsonnet",
                default_branch,
            )
        except RuntimeError:
            if not self.force_processing:
                self.printer.println()
                self.printer.println("No configuration yet available.")
                self.printer.println(
                    "Do you want to push these changes? " "(Only 'yes' or 'y' will be accepted as approval)\n"
                )

                self.printer.print("[bold]Enter a value:[/] ")
                if not get_approval():
                    self.printer.println("\npush cancelled.")
                    return False

            return True

        current_config_file = org_config.jsonnet_config.org_config_file + "-BASE"
        async with open(current_config_file, "w") as file:
            await file.write(current_definition)

        if filecmp.cmp(current_config_file, org_config.jsonnet_config.org_config_file):
            return False

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
            return False

        if not self.force_processing:
            self.printer.println()
            self.printer.println(
                "Do you want to push these changes? " "(Only 'yes' or 'y' will be accepted as approval)\n"
            )

            self.printer.print("[bold]Enter a value:[/] ")
            if not get_approval():
                self.printer.println("\npush cancelled.")
                return False

        return True
