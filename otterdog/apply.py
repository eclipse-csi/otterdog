# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Any

from colorama import Style

from config import OtterdogConfig
from diff import DiffOperation


class ApplyOperation(DiffOperation):
    def __init__(self, config: OtterdogConfig):
        super().__init__(config)

    def handle_modified_settings(self, org_id: str, modified_settings: dict[str, (Any, Any)]) -> None:
        settings = {}
        for key, (expected_value, current_value) in modified_settings.items():
            settings[key] = expected_value
            self.printer.print(f"  updating value for key '{key}' to '{expected_value}'")

        self.gh_client.update_org_settings(org_id, settings)

    def handle_modified_webhook(self, org_id: str, webhook_id: str,
                                modified_webhook: dict[str, (Any, Any)]) -> None:
        config = {}
        for key, (expected_value, current_value) in modified_webhook.items():
            config[key] = expected_value
            msg = f"  updating value for webhook['{webhook_id}'].config.{key} to '{expected_value}'"
            self.printer.print(msg)

        self.gh_client.update_webhook_config(org_id, webhook_id, config)

    def handle_new_webhook(self, org_id: str, data: dict[str, Any]) -> None:
        self.printer.print(f"  creating new webhook with data:\n{json.dumps(data, indent=2)}")
        self.gh_client.add_webhook(org_id, data)

    def handle_modified_repo(self, org_id: str, repo_name: str, modified_repo: dict[str, (Any, Any)]) -> None:
        data = {}
        for key, (expected_value, current_value) in modified_repo.items():
            data[key] = expected_value
            msg = f"  updating value for repo['{repo_name}'].{key} to '{expected_value}'"
            self.printer.print(msg)

        self.gh_client.update_repo(org_id, repo_name, data)

    def handle_new_repo(self, org_id: str, data: dict[str, Any]) -> None:
        self.printer.print(f"  creating new repo with data:\n{json.dumps(data, indent=2)}")
        self.gh_client.add_repo(org_id, data)

    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Any]) -> None:
        data = {}
        for key, (expected_value, current_value) in modified_rule.items():
            data[key] = expected_value
            msg = f"  updating value for branch_protection_rule['{rule_pattern}'].{key} to '{expected_value}'"
            self.printer.print(msg)

        self.gh_client.update_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id, data)

    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        self.printer.print(f"  creating new branch_protection_rule for repo '{repo_name}'"
                           f"with data:\n{json.dumps(data, indent=2)}")
        self.gh_client.add_branch_protection_rule(org_id, repo_name, repo_id, data)

    def handle_finish(self, additions: int, differences: int) -> None:
        self.printer.print(f"\n{Style.BRIGHT}Executed plan:{Style.RESET_ALL} {additions} added, {differences} changed.")
