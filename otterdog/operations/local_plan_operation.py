# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from colorama import Fore, Style

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization, load_github_organization_from_file
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.organization_webhook import OrganizationWebhook
from otterdog.models.repository import Repository

from .plan_operation import PlanOperation
from otterdog.providers.github import Github


class LocalPlanOperation(PlanOperation):
    def __init__(self, suffix: str, update_webhooks: bool):
        super().__init__(no_web_ui=False, update_webhooks=update_webhooks)

        self.suffix = suffix
        self.other_org: GitHubOrganization | None = None

    def pre_execute(self) -> None:
        self.printer.print(f"Printing local diff for configuration at '{self.config.config_file}'")
        self.print_legend()

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        other_org_file_name = self.jsonnet_config.get_org_config_file(github_id) + self.suffix

        if not os.path.exists(other_org_file_name):
            self.printer.print_warn(f"configuration file '{other_org_file_name}' does not exist")
            return 1

        try:
            self.other_org = load_github_organization_from_file(github_id, other_org_file_name, self.config, False)
        except RuntimeError as e:
            self.printer.print_error(f"failed to load configuration\n{str(e)}")
            return 1

        return super().execute(org_config)

    def verbose_output(self):
        return False

    def resolve_secrets(self) -> bool:
        return False

    def setup_github_client(self, org_config: OrganizationConfig) -> int:
        self.gh_client = Github(None)
        return 0

    def get_current_org_settings(self, github_id: str, settings_keys: set[str]) -> OrganizationSettings:
        return self.other_org.settings

    def get_current_webhooks(self, github_id: str) -> list[OrganizationWebhook]:
        return self.other_org.webhooks

    def get_current_repos(self, github_id: str) -> list[Repository]:
        return self.other_org.repositories
