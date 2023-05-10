# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Any

from colorama import Fore, Style

from otterdog.config import OtterdogConfig
from otterdog.models.branch_protection_rule import BranchProtectionRule
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.organization_webhook import OrganizationWebhook
from otterdog.models.repository import Repository
from otterdog.utils import IndentingPrinter, Change

from .diff_operation import DiffStatus
from .plan_operation import PlanOperation


class ApplyOperation(PlanOperation):
    def __init__(self, force_processing: bool, no_web_ui: bool, update_webhooks: bool):
        super().__init__(no_web_ui, update_webhooks)

        self.force_processing = force_processing

        self._org_settings_to_update: dict[str, Change[Any]] = {}
        self._modified_webhooks: dict[str, OrganizationWebhook] = {}
        self._new_webhooks: list[OrganizationWebhook] = []
        self._modified_repos: dict[str, dict[str, Change[Any]]] = {}
        self._new_repos: list[Repository] = []
        self._modified_rules: list[tuple[str, str, str, dict[str, Change[Any]]]] = []
        self._new_rules: list[tuple[str, str, BranchProtectionRule]] = []

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None:
        self.printer.print(f"Apply changes for configuration at '{self.config.config_file}'")
        self.print_legend()

    def handle_modified_settings(self,
                                 org_id: str,
                                 modified_settings: dict[str, Change[Any]],
                                 full_settings: OrganizationSettings) -> int:
        super().handle_modified_settings(org_id, modified_settings, full_settings)
        self._org_settings_to_update = modified_settings
        return len(modified_settings)

    def handle_modified_webhook(self,
                                org_id: str,
                                webhook_id: str,
                                webhook_url: str,
                                modified_webhook: dict[str, Change[Any]],
                                webhook: OrganizationWebhook,
                                forced_update: bool) -> None:
        super().handle_modified_webhook(org_id, webhook_id, webhook_url, modified_webhook, webhook, forced_update)
        self._modified_webhooks[webhook_id] = webhook

    def handle_extra_webhook(self, org_id: str, webhook: OrganizationWebhook) -> None:
        super().handle_extra_webhook(org_id, webhook)

    def handle_new_webhook(self, org_id: str, webhook: OrganizationWebhook) -> None:
        super().handle_new_webhook(org_id, webhook)
        self._new_webhooks.append(webhook)

    def handle_modified_repo(self, org_id: str, repo_name: str, modified_repo: dict[str, Change[Any]]) -> None:
        super().handle_modified_repo(org_id, repo_name, modified_repo)
        self._modified_repos[repo_name] = modified_repo

    def handle_extra_repo(self, org_id: str, repo: Repository) -> None:
        super().handle_extra_repo(org_id, repo)

    def handle_new_repo(self, org_id: str, repo: Repository) -> None:
        super().handle_new_repo(org_id, repo)
        self._new_repos.append(repo)

    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Change[Any]]) -> None:
        super().handle_modified_rule(org_id, repo_name, rule_pattern, rule_id, modified_rule)
        self._modified_rules.append((repo_name, rule_pattern, rule_id, modified_rule))

    def handle_extra_rule(self, org_id: str, repo_name: str, repo_id: str, bpr: BranchProtectionRule) -> None:
        super().handle_extra_rule(org_id, repo_name, repo_id, bpr)

    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, bpr: BranchProtectionRule) -> None:
        super().handle_new_rule(org_id, repo_name, repo_id, bpr)
        self._new_rules.append((repo_name, repo_id, bpr))

    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        self.printer.print()

        if diff_status.differences == 0 and diff_status.additions == 0:
            self.printer.print(f"No changes required ({diff_status.extras} missing definitions ignored).")
            return

        if not self.force_processing:
            self.printer.print(f"{Style.BRIGHT}Do you want to perform these actions?\n"
                               f"  Only 'yes' will be accepted to approve.\n\n")

            self.printer.print(f"  {Style.BRIGHT}Enter a value:{Style.RESET_ALL} ", end='')
            answer = input()
            if answer != "yes":
                self.printer.print("\nApply cancelled.")
                return

        if self._org_settings_to_update is not None:
            github_settings = OrganizationSettings.changes_to_provider(self._org_settings_to_update)
            self.gh_client.update_org_settings(org_id, github_settings)

        for webhook_id, webhook in self._modified_webhooks.items():
            self.gh_client.update_webhook(org_id, webhook_id, webhook.to_provider())

        for webhook in self._new_webhooks:
            self.gh_client.add_webhook(org_id, webhook.to_provider())

        for repo_name, repo in self._modified_repos.items():
            github_repo = Repository.changes_to_provider(repo)
            self.gh_client.update_repo(org_id, repo_name, github_repo)

        for repo in self._new_repos:
            self.gh_client.add_repo(org_id, repo.to_provider(), self.config.auto_init_repo)

        for repo_name, rule_pattern, rule_id, modified_rule in self._modified_rules:
            github_rule = BranchProtectionRule.changes_to_provider(modified_rule, self.gh_client)
            self.gh_client.update_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id, github_rule)

        for repo_name, repo_id, rule in self._new_rules:
            self.gh_client.add_branch_protection_rule(org_id, repo_name, repo_id, rule.to_provider(self.gh_client))

        self.printer.print(f"{Style.BRIGHT}Executed plan:{Style.RESET_ALL} {diff_status.additions} added, "
                           f"{diff_status.differences} changed, "
                           f"{diff_status.extras} missing definitions ignored.")
