#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
from typing import Optional

from otterdog.config import OrganizationConfig
from otterdog.jsonnet import JsonnetConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider

from .plan import PlanOperation


class LocalPlanOperation(PlanOperation):
    def __init__(self, suffix: str, update_webhooks: bool, update_secrets: bool, update_filter: str) -> None:
        super().__init__(
            no_web_ui=False, update_webhooks=update_webhooks, update_secrets=update_secrets, update_filter=update_filter
        )

        self.suffix = suffix
        self._other_org: Optional[GitHubOrganization] = None

    @property
    def other_org(self) -> GitHubOrganization:
        assert self._other_org is not None
        return self._other_org

    def pre_execute(self) -> None:
        self.printer.println("Printing local diff:")
        self.print_legend()

    def verbose_output(self):
        return False

    def resolve_secrets(self) -> bool:
        return False

    def setup_github_client(self, org_config: OrganizationConfig) -> GitHubProvider:
        return GitHubProvider(None)

    async def load_current_org(self, github_id: str, jsonnet_config: JsonnetConfig) -> GitHubOrganization:
        other_org_file_name = jsonnet_config.org_config_file + self.suffix

        if not os.path.exists(other_org_file_name):
            raise RuntimeError(f"configuration file '{other_org_file_name}' does not exist")

        return GitHubOrganization.load_from_file(github_id, other_org_file_name, self.config)
