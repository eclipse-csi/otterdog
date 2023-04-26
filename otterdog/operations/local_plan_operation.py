#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import os
from typing import Any

from otterdog import organization as org
from otterdog.config import OrganizationConfig
from .plan_operation import PlanOperation
from otterdog.providers.github import Github


class LocalPlanOperation(PlanOperation):
    def __init__(self, suffix: str):
        super().__init__()

        self.suffix = suffix
        self.other_org = None

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        other_org_file_name = self.jsonnet_config.get_org_config_file(github_id) + self.suffix

        if not os.path.exists(other_org_file_name):
            self.printer.print_warn(f"configuration file '{other_org_file_name}' does not exist")
            return 1

        try:
            self.other_org = org.load_from_file(github_id, other_org_file_name, self.config, False)
        except RuntimeError as e:
            self.printer.print_error(f"failed to load configuration\n{str(e)}")
            return 1

        return super().execute(org_config)

    def setup_github_client(self, org_config: OrganizationConfig) -> int:
        self.gh_client = Github(None)
        return 0

    def get_current_org_settings(self, github_id: str, settings_keys: set[str]) -> dict[str, Any]:
        return self.other_org.get_settings()

    def get_current_webhooks(self, github_id: str) -> list[tuple[str, dict[str, Any]]]:
        return [("0", hook) for hook in self.other_org.get_webhooks()]

    def get_current_repos(self, github_id: str) -> list[(str, dict[str, Any], list[(str, dict[str, Any])])]:
        repos = self.other_org.get_repos()
        result = []
        for repo in repos:
            rules = repo.pop("branch_protection_rules")
            result.append(("0", repo, [("0", rule) for rule in rules]))
        return result
