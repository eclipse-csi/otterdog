#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.providers.github import GitHubProvider
from otterdog.utils import get_approval

from . import Operation

if TYPE_CHECKING:
    from typing import Any

    from otterdog.config import OrganizationConfig


class ReviewAppPermissionsOperation(Operation):
    """
    Reviews permission updates of installed GitHub apps for an organization.
    """

    def __init__(self, app_slug: str | None, grant: bool, force: bool):
        super().__init__()
        self._app_slug = app_slug
        self._grant = grant
        self._force = force

    @property
    def app_slug(self) -> str | None:
        return self._app_slug

    @property
    def grant(self) -> bool:
        return self._grant

    @property
    def force(self) -> bool:
        return self._force

    def pre_execute(self) -> None:
        self.printer.println("Reviewing permission updates for app installations:")

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
                credentials = self.get_credentials(org_config, only_token=False)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            async with GitHubProvider(credentials) as provider:
                apps = await provider.rest_api.org.get_app_installations(github_id)

                async with provider.web_client.get_logged_in_page() as page:
                    requested_permissions = await provider.web_client.get_requested_permission_updates(github_id, page)

                    for installation_id, permissions in requested_permissions.items():
                        app_slug = _get_app_slug_by_installation_id(apps, installation_id)
                        if app_slug is None:
                            self.printer.print_error(f"failed to process app installation with id '{installation_id}'")
                            continue

                        if self.app_slug is not None and self.app_slug != app_slug:
                            continue

                        self.printer.println()
                        self.print_dict(permissions, f"app['{app_slug}']", "", "black")

                        if self.grant is True:
                            if self.force is False:
                                self.printer.println()
                                self.printer.println("[bold]Approve[/] requested permissions?")
                                self.printer.println(
                                    "  Do you want to continue? (Only 'yes' or 'y' will be accepted to approve)\n"
                                )

                                self.printer.print("[bold]Enter a value:[/] ")
                                if not get_approval():
                                    self.printer.println("\nApproval cancelled.")
                                    continue

                            await provider.web_client.approve_requested_permission_updates(
                                github_id,
                                installation_id,
                                page,
                            )
                            self.printer.println()
                            self.printer.println("requested permissions approved.")

            return 0

        finally:
            self.printer.level_down()


def _get_app_slug_by_installation_id(installed_apps: list[dict[str, Any]], install_id: str) -> str | None:
    for app in installed_apps:
        if str(app["id"]) == install_id:
            return app["app_slug"]

    return None
