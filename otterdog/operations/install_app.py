#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.providers.github import GitHubProvider

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class InstallAppOperation(Operation):
    """
    Installs a GitHub app for an organization.
    """

    def __init__(self, app_slug: str):
        super().__init__()
        self._app_slug = app_slug
        self._app_id: int | None = None

    @property
    def app_slug(self) -> str:
        return self._app_slug

    @property
    def app_id(self) -> int | None:
        return self._app_id

    def pre_execute(self) -> None:
        self.printer.println(f"Installing GitHub app '{self.app_slug}':")

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        github_id = org_config.github_id

        self._print_project_header(org_config, org_index, org_count)
        self.printer.level_up()

        try:
            try:
                credentials = self.get_credentials(org_config)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            async with GitHubProvider(credentials) as provider:
                rest_api = provider.rest_api

                current_app_installations = await rest_api.org.get_app_installations(github_id)
                for app_installation in current_app_installations:
                    installed_app_slug = app_installation["app_slug"]
                    if installed_app_slug == self.app_slug:
                        self.printer.println("app already installed, skipping.")
                        return 0

                org_int_id = str(await rest_api.org.get_id(github_id))
                await provider.web_client.install_github_app(org_int_id, self.app_slug)

            self.printer.println("app installed.")
            return 0
        finally:
            self.printer.level_down()
