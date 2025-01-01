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
from aioshutil import copy

from otterdog.models import PatchContext
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider

from . import Operation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from otterdog.config import OrganizationConfig
    from otterdog.models.webhook import Webhook


class ImportOperation(Operation):
    """
    Imports the current live configuration for organizations.
    """

    def __init__(self, force_processing: bool, no_web_ui: bool):
        super().__init__()
        self._force_processing = force_processing
        self._no_web_ui = no_web_ui

    @property
    def force_processing(self) -> bool:
        return self._force_processing

    @property
    def no_web_ui(self) -> bool:
        return self._no_web_ui

    def pre_execute(self) -> None:
        self.printer.println("Importing resources:")

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
        if not await self.check_config_file_overwrite_if_exists(org_file_name, self.force_processing):
            return 1

        if await ospath.exists(org_file_name):
            sync_from_previous_config = True
            backup_file = f"{org_file_name}.bak"
            await copy(org_file_name, backup_file)
            self.printer.println(f"\nExisting definition copied to '[bold]{backup_file}[/]'.\n")
        else:
            sync_from_previous_config = False

        self.printer.level_up()

        try:
            try:
                credentials = self.get_credentials(org_config)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            if self.no_web_ui is True:
                self.printer.print_warn(
                    "the Web UI will not be queried as '--no-web-ui' has been specified, "
                    "the resulting config will be incomplete."
                )

            async with GitHubProvider(credentials) as provider:
                organization = await GitHubOrganization.load_from_provider(
                    org_config.name,
                    github_id,
                    jsonnet_config,
                    provider,
                    self.no_web_ui,
                    exclude_teams=self.config.exclude_teams_pattern,
                )

            # copy secrets from existing configuration if it is present.
            if sync_from_previous_config:
                previous_organization = GitHubOrganization.load_from_file(github_id, org_file_name)

                self.printer.println("Copying secrets from previous configuration.")
                organization.copy_secrets(previous_organization)

                self.printer.print("Masking webhooks from previous configuration... ")
                masked_urls = 0
                for org_webhook in previous_organization.webhooks:
                    if org_webhook.url.endswith("*"):
                        masked_urls += _mask_webhook_url(organization.webhooks, org_webhook)

                for repo in previous_organization.repositories:
                    for repo_webhook in repo.webhooks:
                        if repo_webhook.url.endswith("*"):
                            new_repo = organization.get_repository(repo.name)
                            if new_repo is not None:
                                masked_urls += _mask_webhook_url(new_repo.webhooks, repo_webhook)

                self.printer.println(f"{masked_urls} URLs have been masked.")

            context = PatchContext(github_id, organization.settings)
            output = organization.to_jsonnet(jsonnet_config, context)

            output_dir = jsonnet_config.org_dir
            if not await ospath.exists(output_dir):
                await os.makedirs(output_dir)

            async with open(org_file_name, "w") as file:
                await file.write(output)

            self.printer.println(f"Organization definition written to '{org_file_name}'.")

            return 0
        finally:
            self.printer.level_down()


def _mask_webhook_url(webhooks: Sequence[Webhook], masked_webhook: Webhook) -> int:
    stripped_url = masked_webhook.url.rstrip("*")
    for webhook in webhooks:
        if webhook.url.startswith(stripped_url):
            webhook.url = masked_webhook.url
            return 1

    return 0
