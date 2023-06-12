# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from typing import Optional

from otterdog.config import OrganizationConfig
from otterdog.jsonnet import JsonnetConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import Github

from .plan_operation import PlanOperation


class LocalPlanOperation(PlanOperation):
    def __init__(self, suffix: str, update_webhooks: bool) -> None:
        super().__init__(no_web_ui=False, update_webhooks=update_webhooks)

        self.suffix = suffix
        self._other_org: Optional[GitHubOrganization] = None

    @property
    def other_org(self) -> GitHubOrganization:
        assert self._other_org is not None
        return self._other_org

    def pre_execute(self) -> None:
        self.printer.print(f"Printing local diff for configuration at '{self.config.config_file}'")
        self.print_legend()

    def verbose_output(self):
        return False

    def resolve_secrets(self) -> bool:
        return False

    def setup_github_client(self, org_config: OrganizationConfig) -> Github:
        return Github(None)

    def load_current_org(self, github_id: str, jsonnet_config: JsonnetConfig) -> GitHubOrganization:
        other_org_file_name = jsonnet_config.org_config_file + self.suffix

        if not os.path.exists(other_org_file_name):
            raise RuntimeError(f"configuration file '{other_org_file_name}' does not exist")

        return GitHubOrganization.load_from_file(github_id, other_org_file_name, self.config, False)
