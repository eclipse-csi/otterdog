#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class ListProjectsOperation(Operation):
    """
    Lists projects and their associated GitHub ID.
    """

    def __init__(self):
        super().__init__()
        self._table = Table(title="Projects", box=box.ROUNDED)

    @property
    def table(self) -> Table:
        return self._table

    def pre_execute(self) -> None:
        self.table.add_column("Project name", justify="left", style="cyan", no_wrap=True)
        self.table.add_column("GitHub ID", style="magenta")
        self.table.add_column("Index", justify="right", style="green")

    def post_execute(self) -> None:
        self.printer.console.print(self.table)

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        self.table.add_row(org_config.name, org_config.github_id, str(org_index or -1))
        return 0
