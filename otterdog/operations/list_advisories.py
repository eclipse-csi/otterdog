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
from otterdog.utils import style

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class ListAdvisoriesOperation(Operation):
    """
    Lists repository security advisories for an organization.
    """

    def __init__(self, state: str, details: bool):
        super().__init__()
        self._state = state
        self._details = details

    @property
    def state(self) -> str:
        return self._state

    @property
    def details(self) -> bool:
        return self._details

    def pre_execute(self) -> None:
        self.printer.println(f"Listing {self.state} repository security advisories:")

    def post_execute(self) -> None:
        pass

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        github_id = org_config.github_id

        self.printer.println(
            f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]"
            f"{self._format_progress(org_index, org_count)}"
        )
        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            async with GitHubProvider(credentials) as provider:
                advisories = await provider.rest_api.org.get_security_advisories(github_id, self.state)

            self.printer.println(f"Found {len(advisories)} advisories with state '{self.state}'.")
            if not self.details:
                self.printer.println()

            for advisory in advisories:
                if self.details:
                    self.printer.println()
                    self.print_dict(advisory, f"advisory['{advisory['ghsa_id']}']", "", "black")
                else:
                    self.printer.println(f"{advisory['ghsa_id']}, {advisory['summary']}, {advisory['cve_id']}")

            return 0
        finally:
            self.printer.level_down()
