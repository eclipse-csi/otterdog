# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Any

from colorama import Style

from config import OtterdogConfig
from diff import DiffStatus
from plan import PlanOperation
from utils import IndentingPrinter


class ApplyOperation(PlanOperation):
    def __init__(self):
        super().__init__()

        self._modified_settings = None
        self._modified_webhooks = {}
        self._new_webhooks = []
        self._modified_repos = {}
        self._new_repos = []
        self._modified_rules = []
        self._new_rules = []

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None:
        self.printer.print(f"Apply changes for configuration at '{self.config.config_file}'")

    def handle_modified_settings(self, org_id: str, modified_settings: dict[str, (Any, Any)]) -> None:
        super().handle_modified_settings(org_id, modified_settings)

        settings = {}
        for key, (expected_value, current_value) in modified_settings.items():
            settings[key] = expected_value

        self._modified_settings = settings

    def handle_modified_webhook(self,
                                org_id: str,
                                webhook_id: str,
                                webhook_url: str,
                                modified_webhook: dict[str, (Any, Any)],
                                webhook: dict[str, Any]) -> None:
        super().handle_modified_webhook(org_id, webhook_id, webhook_url, modified_webhook, webhook)

        config = {}
        for key, (expected_value, current_value) in modified_webhook.items():
            config[key] = expected_value

        self._modified_webhooks[webhook_id] = webhook

    def handle_extra_webhook(self, org_id: str, webhook: dict[str, Any]) -> None:
        super().handle_extra_webhook(org_id, webhook)

    def handle_new_webhook(self, org_id: str, data: dict[str, Any]) -> None:
        super().handle_new_webhook(org_id, data)
        self._new_webhooks.append(data)

    def handle_modified_repo(self, org_id: str, repo_name: str, modified_repo: dict[str, (Any, Any)]) -> None:
        super().handle_modified_repo(org_id, repo_name, modified_repo)
        
        data = {}
        for key, (expected_value, current_value) in modified_repo.items():
            data[key] = expected_value

        self._modified_repos[repo_name] = data

    def handle_extra_repo(self, org_id: str, repo: dict[str, Any]) -> None:
        super().handle_extra_repo(org_id, repo)

    def handle_new_repo(self, org_id: str, data: dict[str, Any]) -> None:
        super().handle_new_repo(org_id, data)
        self._new_repos.append(data)

    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Any]) -> None:
        data = {}
        for key, (expected_value, current_value) in modified_rule.items():
            data[key] = expected_value

        self._modified_rules.append((repo_name, rule_pattern, rule_id, data))

    def handle_extra_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        super().handle_extra_rule(org_id, repo_name, repo_id, data)

    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        super().handle_new_rule(org_id, repo_name, repo_id, data)
        self._new_rules.append((repo_name, repo_id, data))

    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        self.printer.print()

        if diff_status.differences == 0 and diff_status.additions == 0:
            self.printer.print(f"No changes required ({diff_status.extras} missing definitions ignored).")
            return

        self.printer.print(f"{Style.BRIGHT}Do you want to perform these actions?\n"
                           f"  Do you want to continue?\n"
                           f"  Only 'yes' will be accepted to approve.\n\n")

        self.printer.print(f"  {Style.BRIGHT}Enter a value:{Style.RESET_ALL} ", end='')
        answer = input()
        if answer != "yes":
            self.printer.print("\nApply cancelled.")
            return

        if self._modified_settings is not None:
            self.gh_client.update_org_settings(org_id, self._modified_settings)

        for webhook_id, webhook in self._modified_webhooks.items():
            self.gh_client.update_webhook(org_id, webhook_id, webhook)

        for webhook in self._new_webhooks:
            self.gh_client.add_webhook(org_id, webhook)

        for repo_name, repo in self._modified_repos.items():
            self.gh_client.update_repo(org_id, repo_name, repo)

        for repo in self._new_repos:
            self.gh_client.add_repo(org_id, repo)

        for (repo_name, rule_pattern, rule_id, rule) in self._modified_rules:
            self.gh_client.update_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id, rule)

        for (repo_name, repo_id, rule) in self._new_rules:
            self.gh_client.add_branch_protection_rule(org_id, repo_name, repo_id, rule)

        self.printer.print(f"{Style.BRIGHT}Executed plan:{Style.RESET_ALL} {diff_status.additions} added, "
                           f"{diff_status.differences} changed, "
                           f"{diff_status.extras} missing definitions ignored.")
