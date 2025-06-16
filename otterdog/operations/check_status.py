#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from json import dumps as json_dumps
from typing import TYPE_CHECKING

from .diff_operation import DiffOperation, DiffStatus

if TYPE_CHECKING:
    from typing import Any

    from otterdog.config import OrganizationConfig, OtterdogConfig
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.models import LivePatch, ModelObject
    from otterdog.models.github_organization import GitHubOrganization
    from otterdog.utils import Change, IndentingPrinter

    from .validate import ValidationStatus


class CheckStatusOperation(DiffOperation):
    """
    Check the status of current configuration (validity and wether it is in sync with the GitHub live configuration)
    """

    def __init__(
        self,
        no_web_ui: bool,
        repo_filter: str,
    ):
        super().__init__(no_web_ui, repo_filter, False, False, "*")
        self.orgs_status: list[Any] = []

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None: ...

    def post_execute(self) -> None:
        self.printer.println(json_dumps(self.orgs_status, indent=2))

    def resolve_secrets(self) -> bool:
        return False

    async def handle_finish(
        self, org_id: str, diff_status: DiffStatus, validation_status: ValidationStatus, patches: list[LivePatch]
    ) -> int:
        self.orgs_status.append(
            {
                "org_id": org_id,
                "validation_status": {
                    "is_valid": validation_status.total_notices() == 0,
                    "infos": validation_status.infos,
                    "warnings": validation_status.warnings,
                    "errors": validation_status.errors,
                },
                "sync_status": {
                    "in_sync": validation_status.total_notices() == 0 and not patches,
                    "additions": diff_status.additions,
                    "changes": diff_status.differences,
                    "deletions": diff_status.deletions,
                },
            }
        )

        return 0

    async def validate(self, expected_org: GitHubOrganization, jsonnet_config: JsonnetConfig) -> ValidationStatus:
        return await self._validator.validate(expected_org, jsonnet_config, self.gh_client, False)

    def handle_validation_status(self, validation_status: ValidationStatus) -> bool:
        return validation_status.errors == 0

    def _print_project_header(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> None: ...

    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> None: ...

    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> None: ...

    def handle_modified_object(
        self,
        org_id: str,
        modified_object: dict[str, Change[Any]],
        forced_update: bool,
        current_object: ModelObject,
        expected_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> int:
        settings_to_change = 0
        for k, _v in modified_object.items():
            if not current_object.is_read_only_key(k):
                settings_to_change += 1

        return settings_to_change
