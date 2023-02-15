# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Any

from colorama import Fore, Style

from config import OtterdogConfig
from diff import DiffOperation, DiffStatus
from utils import IndentingPrinter


class PlanOperation(DiffOperation):
    def __init__(self):
        super().__init__()

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None:
        self.printer.print(f"Planning execution for configuration at '{self.config.config_file}'")
        self.printer.print(f"\nActions are indicted with the following symbols:")
        self.printer.print(f"  {Fore.GREEN}+{Style.RESET_ALL} create")
        self.printer.print(f"  {Fore.YELLOW}~{Style.RESET_ALL} modify")
        self.printer.print(f"  {Fore.RED}-{Style.RESET_ALL} extra (missing in definition but available live)")

    def handle_modified_settings(self, org_id: str, modified_settings: dict[str, (Any, Any)]) -> None:
        self.print_modified_dict(modified_settings, "settings")

    def handle_modified_webhook(self,
                                org_id: str,
                                webhook_id: str,
                                webhook_url: str,
                                modified_webhook: dict[str, (Any, Any)],
                                webhook: dict[str, Any]) -> None:
        self.printer.print()
        self.print_modified_dict(modified_webhook, f"webhook[url='{webhook_url}']")

    def handle_extra_webhook(self, org_id: str, webhook: dict[str, Any]) -> None:
        self.printer.print()
        self.print_dict(webhook, "extra webhook", "-", Fore.RED)

    def handle_new_webhook(self, org_id: str, webhook: dict[str, Any]) -> None:
        self.printer.print()
        self.print_dict(webhook, "new webhook", "+", Fore.GREEN)

    def handle_modified_repo(self, org_id: str, repo_name: str, modified_repo: dict[str, (Any, Any)]) -> None:
        self.print_modified_dict(modified_repo, f"repo[name=\"{repo_name}\"]")

    def handle_extra_repo(self, org_id: str, repo: dict[str, Any]) -> None:
        self.printer.print()
        self.print_dict(repo, "extra repo", "-", Fore.RED)

    def handle_new_repo(self, org_id: str, data: dict[str, Any]) -> None:
        self.printer.print()
        self.print_dict(data, "new repo", "+", Fore.GREEN)

    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Any]) -> None:

        self.printer.print()
        self.print_modified_dict(modified_rule,
                                 f"branch_protection_rule[repo=\"{repo_name}\", pattern=\"{rule_pattern}\"]")

    def handle_extra_rule(self, org_id: str, repo_name: str, repo_id: str, rule_data: dict[str, Any]) -> None:
        self.printer.print()
        self.print_dict(rule_data, f"extra branch_protection_rule[repo=\"{repo_name}\"]", "-", Fore.RED)

    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, rule_data: dict[str, Any]) -> None:
        self.printer.print()
        self.print_dict(rule_data, f"new branch_protection_rule[repo=\"{repo_name}\"]", "+", Fore.GREEN)

    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        self.printer.print()
        self.printer.print(f"\n{Style.BRIGHT}Plan:{Style.RESET_ALL} {diff_status.additions} to add, "
                           f"{diff_status.differences} to change, "
                           f"{diff_status.extras} are missing in definition.")
