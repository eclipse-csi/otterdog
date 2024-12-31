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

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class CheckTokenPermissionsOperation(Operation):
    """
    Checks the granted permissions for the otterdog-token.
    """

    EXPECTED_SCOPES = frozenset(["admin:org", "admin:org_hook", "delete_repo", "repo", "workflow"])

    def __init__(self, list_granted_scopes: bool):
        super().__init__()
        self._list_granted_scopes = list_granted_scopes

    @property
    def list_granted_scopes(self) -> bool:
        return self._list_granted_scopes

    def pre_execute(self) -> None:
        self.printer.println("Checking token permissions:")

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        self._print_project_header(org_config, org_index, org_count)
        self.printer.level_up()

        try:
            try:
                credentials = self.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            async with GitHubProvider(credentials) as provider:
                scopes = await provider.rest_api.meta.get_scopes()

                if self._list_granted_scopes is True:
                    self.printer.println(f"[green]Granted scopes[/]: {scopes}")

                missing_scopes = self._get_missing_scopes(scopes)
                if len(missing_scopes) > 0:
                    scope_string = ", ".join(missing_scopes)
                    self.printer.println(f"[red]Missing scopes[/]: {scope_string}")
                    return 1

            return 0
        finally:
            self.printer.level_down()

    def _get_missing_scopes(self, scopes: str) -> list[str]:
        missing_scopes = []
        granted_scopes = {s.strip() for s in scopes.split(",") if len(s.strip()) > 0}
        for scope in self.EXPECTED_SCOPES:
            if scope not in granted_scopes:
                missing_scopes.append(scope)

        return missing_scopes
