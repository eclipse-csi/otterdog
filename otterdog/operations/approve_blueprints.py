#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import unwrap
from otterdog.webapp.db.models import BlueprintStatusModel

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class ApproveBlueprintsOperation(Operation):
    """
    Approves and merges remediation PRs for blueprints.
    """

    def __init__(self, blueprint_id: str | None):
        super().__init__()
        self._blueprint_id = blueprint_id
        self._blueprints_by_org: dict[str, list[BlueprintStatusModel]] = {}

    @property
    def blueprint_id(self) -> str | None:
        return self._blueprint_id

    def pre_execute(self) -> None:
        import requests

        items = []
        params = {
            "pageIndex": 1,
            "pageSize": 50,
        }

        base_url = unwrap(self._config).base_url
        if base_url is None:
            raise RuntimeError("no base_url set which is required when using operation 'approve-blueprints'")

        while True:
            response = requests.get(f"{base_url}/api/blueprints/remediations", params=params, timeout=10)
            response_json = response.json()
            items.extend(response_json["data"])
            if len(items) >= response_json["itemsCount"]:
                break
            else:
                params["pageIndex"] = params["pageIndex"] + 1

        for item in items:
            blueprint_status = BlueprintStatusModel.model_validate(item)

            if self._skip_blueprint(blueprint_status):
                continue

            blueprint_list = self._blueprints_by_org.setdefault(blueprint_status.id.org_id, [])
            blueprint_list.append(blueprint_status)

    def _skip_blueprint(self, blueprint: BlueprintStatusModel) -> bool:
        if self.blueprint_id is not None and blueprint.id.blueprint_id != self.blueprint_id:
            return True

        return False

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        blueprints = self._blueprints_by_org.get(org_config.github_id, [])

        if len(blueprints) > 0:
            github_id = org_config.github_id
            jsonnet_config = org_config.jsonnet_config
            await jsonnet_config.init_template()

            self._print_project_header(org_config, org_index, org_count)
            self.printer.level_up()

            try:
                org_file_name = jsonnet_config.org_config_file
                if not await self.check_config_file_exists(org_file_name):
                    return 1

                try:
                    organization = GitHubOrganization.load_from_file(github_id, org_file_name)
                except RuntimeError as ex:
                    self.printer.print_error(f"failed to load configuration: {ex!s}")
                    return 1

                try:
                    credentials = self.get_credentials(org_config, only_token=True)
                except RuntimeError as e:
                    self.printer.print_error(f"invalid credentials\n{e!s}")
                    return 1

                async with GitHubProvider(credentials) as provider:
                    rest_api = provider.rest_api

                    for blueprint in blueprints:
                        self.printer.print(f"Merging PR #{blueprint.remediation_pr}: ")

                        repo = organization.get_repository(blueprint.id.repo_name)
                        if repo is None:
                            self.printer.println("no repo found.")
                            continue

                        if repo.allow_merge_commit is True:
                            merge_method = "merge"
                        if repo.allow_squash_merge is True:
                            merge_method = "squash"
                        if repo.allow_rebase_merge is True:
                            merge_method = "rebase"

                        result = await rest_api.pull_request.merge_pull_request(
                            blueprint.id.org_id, blueprint.id.repo_name, f"{blueprint.remediation_pr}", merge_method
                        )

                        if result["merged"] is True:
                            self.printer.println("[green]merged[/].")
                        else:
                            self.printer.println(f"[red]failed[/]: {result['message']}.")

            finally:
                self.printer.level_down()

        return 0
