# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Any, Optional

from colorama import Fore, Style

from otterdog.config import OtterdogConfig
from otterdog.models.branch_protection_rule import BranchProtectionRule
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.organization_webhook import OrganizationWebhook
from otterdog.models.repository import Repository
from otterdog.utils import IndentingPrinter, Change

from .diff_operation import DiffOperation, DiffStatus


class PlanOperation(DiffOperation):
    def __init__(self, no_web_ui: bool, update_webhooks: bool):
        super().__init__(no_web_ui, update_webhooks)

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None:
        self.printer.print(f"Planning execution for configuration at '{self.config.config_file}'")
        self.print_legend()

    def print_legend(self) -> None:
        self.printer.print("\nActions are indicated with the following symbols:")
        self.printer.print(f"  {Fore.GREEN}+{Style.RESET_ALL} create")
        self.printer.print(f"  {Fore.YELLOW}~{Style.RESET_ALL} modify")
        self.printer.print(f"  {Fore.MAGENTA}!{Style.RESET_ALL} forced update")
        self.printer.print(f"  {Fore.RED}-{Style.RESET_ALL} extra (missing in definition but available "
                           f"in other config)")

    def handle_modified_settings(self, org_id: str, modified_settings: dict[str, Change[Any]]) -> int:
        self.print_modified_dict(modified_settings, "settings")

        settings_to_change = 0
        for k, v in modified_settings.items():
            if OrganizationSettings.is_read_only_key(k):
                self.printer.print(f"\n{Fore.YELLOW}Note:{Style.RESET_ALL} setting '{k}' "
                                   f"is read-only, will be skipped.")
            else:
                settings_to_change += 1

        return settings_to_change

    def handle_modified_webhook(self,
                                org_id: str,
                                webhook_id: str,
                                webhook_url: str,
                                modified_webhook: dict[str, Change[Any]],
                                webhook: OrganizationWebhook,
                                forced_update: bool) -> None:
        self.printer.print()
        self.print_modified_dict(modified_webhook, f"webhook[url='{webhook_url}']", {"secret"}, forced_update)

        if "secret" in modified_webhook:
            new_secret = modified_webhook["secret"].to_value
            if not new_secret:
                self.printer.print(f"\n{Fore.RED}Warning:{Style.RESET_ALL} removing secret for webhook "
                                   f"with url '{webhook_url}'")

    def handle_extra_webhook(self, org_id: str, webhook: OrganizationWebhook) -> None:
        self.printer.print()
        self.print_dict(webhook.to_model_dict(), "extra webhook", "-", Fore.RED)

    def handle_new_webhook(self, org_id: str, webhook: OrganizationWebhook) -> None:
        self.printer.print()
        self.print_dict(webhook.to_model_dict(), "new webhook", "+", Fore.GREEN)

    def handle_modified_repo(self, org_id: str, repo_name: str, modified_repo: dict[str, Change[Any]]) -> int:
        self.print_modified_dict(modified_repo, f"repo[name=\"{repo_name}\"]")

        settings_to_change = 0
        for k, v in modified_repo.items():
            if Repository.is_read_only_key(k):
                self.printer.print(f"\n{Fore.YELLOW}Note:{Style.RESET_ALL} setting '{k}' "
                                   f"is read-only, will be skipped.")
            else:
                settings_to_change += 1

        return settings_to_change

    def handle_extra_repo(self, org_id: str, repo: Repository) -> None:
        self.printer.print()
        self.print_dict(repo.to_model_dict(), "extra repo", "-", Fore.RED)

    def handle_new_repo(self, org_id: str, repo: Repository) -> None:
        self.printer.print()
        self.print_dict(repo.to_model_dict(), "new repo", "+", Fore.GREEN)

    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Change[Any]]) -> None:

        self.printer.print()
        self.print_modified_dict(modified_rule,
                                 f"branch_protection_rule[repo=\"{repo_name}\", pattern=\"{rule_pattern}\"]")

    def handle_extra_rule(self, org_id: str, repo_name: str, repo_id: str, bpr: BranchProtectionRule) -> None:
        self.printer.print()
        self.print_dict(bpr.to_model_dict(), f"extra branch_protection_rule[repo=\"{repo_name}\"]", "-", Fore.RED)

    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: Optional[str], bpr: BranchProtectionRule) -> None:
        self.printer.print()
        self.print_dict(bpr.to_model_dict(), f"new branch_protection_rule[repo=\"{repo_name}\"]", "+", Fore.GREEN)

    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        self.printer.print()
        self.printer.print(f"\n{Style.BRIGHT}Plan:{Style.RESET_ALL} {diff_status.additions} to add, "
                           f"{diff_status.differences} to change, "
                           f"{diff_status.extras} are missing in definition.")
