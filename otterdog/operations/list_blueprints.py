#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

from otterdog.utils import unwrap
from otterdog.webapp.db.models import BlueprintStatusModel

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class ListBlueprintsOperation(Operation):
    """
    Lists remediation PRs for blueprints.
    """

    def __init__(self, blueprint_id: str | None):
        super().__init__()
        self._blueprint_id = blueprint_id
        self._table = Table(title="Projects", box=box.ROUNDED)
        self._blueprints_by_org: dict[str, list[BlueprintStatusModel]] = {}

    @property
    def blueprint_id(self) -> str | None:
        return self._blueprint_id

    @property
    def table(self) -> Table:
        return self._table

    def pre_execute(self) -> None:
        import requests

        items = []
        params = {
            "pageIndex": 1,
            "pageSize": 50,
        }

        base_url = unwrap(self._config).base_url
        if base_url is None:
            raise RuntimeError("no base_url set which is required when using operation 'list-blueprints'")

        while True:
            response = requests.get(f"{base_url}/api/blueprints/remediations", params=params, timeout=10)
            response_json = response.json()
            items.extend(response_json["data"])
            if len(items) >= response_json["itemsCount"]:
                break
            else:
                params["pageIndex"] = params["pageIndex"] + 1

        self.table.add_column("Index", justify="left", style="cyan")
        self.table.add_column("Blueprint ID", justify="left", style="cyan", no_wrap=True)
        self.table.add_column("GitHub ID", style="magenta")
        self.table.add_column("Repo", justify="left", style="green")
        self.table.add_column("PR", justify="left", style="red")

        for item in items:
            blueprint_status = BlueprintStatusModel.model_validate(item)

            if self._skip_blueprint(blueprint_status):
                continue

            blueprints = self._blueprints_by_org.setdefault(blueprint_status.id.org_id, [])
            blueprints.append(blueprint_status)

    def _skip_blueprint(self, blueprint: BlueprintStatusModel) -> bool:
        if self.blueprint_id is not None and blueprint.id.blueprint_id != self.blueprint_id:
            return True

        return False

    def post_execute(self) -> None:
        self.printer.console.print(self.table)

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        blueprints = self._blueprints_by_org.get(org_config.github_id, [])
        for blueprint in blueprints:
            pr_url = (
                f"https://github.com/{blueprint.id.org_id}/{blueprint.id.repo_name}/pull/{blueprint.remediation_pr}"
            )

            self.table.add_row(
                f"{len(self.table.rows) + 1}",
                blueprint.id.blueprint_id,
                blueprint.id.org_id,
                blueprint.id.repo_name,
                pr_url,
            )

        return 0
