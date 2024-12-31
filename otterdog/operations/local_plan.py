#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from aiofiles import ospath

from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import unwrap

from .plan import PlanOperation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig
    from otterdog.jsonnet import JsonnetConfig


class LocalPlanOperation(PlanOperation):
    def __init__(
        self,
        suffix: str,
        repo_filter: str,
        update_webhooks: bool,
        update_secrets: bool,
        update_filter: str,
    ) -> None:
        super().__init__(
            no_web_ui=False,
            repo_filter=repo_filter,
            update_webhooks=update_webhooks,
            update_secrets=update_secrets,
            update_filter=update_filter,
        )

        self.suffix = suffix
        self._other_org: GitHubOrganization | None = None

    @property
    def other_org(self) -> GitHubOrganization:
        return unwrap(self._other_org)

    def pre_execute(self) -> None:
        self.printer.println("Printing local diff:")
        self.print_legend()

    def verbose_output(self):
        return False

    def resolve_secrets(self) -> bool:
        return False

    def coerce_current_org(self) -> bool:
        return True

    def setup_github_client(self, org_config: OrganizationConfig) -> GitHubProvider:
        return GitHubProvider(self.get_credentials(org_config, only_token=True))

    async def load_current_org(
        self, project_name: str, github_id: str, jsonnet_config: JsonnetConfig
    ) -> GitHubOrganization:
        other_org_file_name = jsonnet_config.org_config_file + self.suffix

        if not await ospath.exists(other_org_file_name):
            raise RuntimeError(f"configuration file '{other_org_file_name}' does not exist")

        return GitHubOrganization.load_from_file(github_id, other_org_file_name)

    def preprocess_orgs(
        self, expected_org: GitHubOrganization, current_org: GitHubOrganization
    ) -> tuple[GitHubOrganization, GitHubOrganization]:
        expected_org.update_dummy_secrets("<DUMMY>")
        current_org.update_dummy_secrets("<DUMMY>")
        return expected_org, current_org
