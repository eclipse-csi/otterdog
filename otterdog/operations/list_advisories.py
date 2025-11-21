#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from otterdog.providers.github import GitHubProvider
from otterdog.utils import format_date_for_csv, is_info_enabled

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class ListAdvisoriesOperation(Operation):
    """
    Lists repository security advisories for an organization.
    """

    # CSV fields
    CSV_FIELDS: Final[tuple[str, ...]] = (
        "organization",
        "created_at",
        "updated_at",
        "published_at",
        "state",
        "severity",
        "ghsa_id",
        "cve_id",
        "html_url",
        "summary",
    )

    def __init__(self, states: list[str], details: bool):
        super().__init__()
        # if states contains "all", then we will get all advisories
        if "all" in states:
            states = ["triage", "draft", "published", "closed"]
        self._states = states
        self._details = details

    @property
    def states(self) -> list[str]:
        return self._states

    @property
    def details(self) -> bool:
        return self._details

    def pre_execute(self) -> None:
        if is_info_enabled():
            self.printer.println(f"Listing {self.states} repository security advisories:")
        if not self.details:
            self.printer.println(",".join(self.CSV_FIELDS))

    def post_execute(self) -> None:
        pass

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        github_id = org_config.github_id

        if is_info_enabled():
            self._print_project_header(org_config, org_index, org_count)
            self.printer.level_up()

        try:
            try:
                credentials = self.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{e!s}")
                return 1

            advisories = []
            for state in self.states:
                async with GitHubProvider(credentials) as provider:
                    advisories_for_state = await provider.rest_api.org.get_security_advisories(github_id, state)
                    advisories += advisories_for_state

            if not self.details:
                if is_info_enabled():
                    self.printer.println(f"Found {len(advisories)} advisories with state '{self.states}'.")
                    self.printer.println()

            for advisory in advisories:
                if not self.details:
                    cve_id = advisory["cve_id"] if advisory["cve_id"] is not None else "NO_CVE"
                    summary = advisory["summary"].replace('"', '""')

                    formatted_values = {
                        "organization": org_config.name,
                        "created_at": format_date_for_csv(advisory["created_at"]),
                        "updated_at": format_date_for_csv(advisory["updated_at"]),
                        "published_at": format_date_for_csv(advisory["published_at"]),
                        "state": advisory["state"],
                        "severity": advisory["severity"],
                        "ghsa_id": advisory["ghsa_id"],
                        "cve_id": cve_id,
                        "html_url": advisory["html_url"],
                        "summary": summary,
                    }

                    assert (  # noqa: S101
                        list(formatted_values.keys()) == list(self.CSV_FIELDS)
                    ), f"CSV fields mismatch! Expected {list(self.CSV_FIELDS)}, got {list(formatted_values.keys())}"

                    csv_values = [f'"{formatted_values[field]}"' for field in self.CSV_FIELDS]
                    self.printer.println(",".join(csv_values))
                else:
                    self.print_dict(advisory, f"advisory['{advisory['ghsa_id']}']", "", "black")

            return 0
        finally:
            if is_info_enabled():
                self.printer.level_down()
