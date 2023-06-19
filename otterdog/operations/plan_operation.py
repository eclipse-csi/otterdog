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
from otterdog.models import ModelObject
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
        self.printer.println(f"Planning execution for configuration at '{self.config.config_file}'")
        self.print_legend()

    def print_legend(self) -> None:
        self.printer.println("\nActions are indicated with the following symbols:")
        self.printer.println(f"  {Fore.GREEN}+{Style.RESET_ALL} create")
        self.printer.println(f"  {Fore.YELLOW}~{Style.RESET_ALL} modify")
        self.printer.println(f"  {Fore.MAGENTA}!{Style.RESET_ALL} forced update")
        self.printer.println(f"  {Fore.RED}-{Style.RESET_ALL} delete")

    def handle_new_object(self,
                          org_id: str,
                          model_object: ModelObject,
                          parent_object: Optional[ModelObject] = None) -> None:
        self.printer.println()
        model_header = self.get_model_header(model_object, parent_object)
        self.print_dict(model_object.to_model_dict(for_diff=True), f"new {model_header}", "+", Fore.GREEN)

    def handle_delete_object(self,
                             org_id: str,
                             model_object: ModelObject,
                             parent_object: Optional[ModelObject] = None) -> None:
        self.printer.println()
        model_header = self.get_model_header(model_object, parent_object)
        self.print_dict(model_object.to_model_dict(for_diff=True), f"remove {model_header}", "-", Fore.RED)

    def handle_modified_settings(self, org_id: str, modified_settings: dict[str, Change[Any]]) -> int:
        self.print_modified_dict(modified_settings, "settings")

        settings_to_change = 0
        for k, v in modified_settings.items():
            if OrganizationSettings.is_read_only_key(k):
                self.printer.println(f"\n{Fore.YELLOW}Note:{Style.RESET_ALL} setting '{k}' "
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
        self.printer.println()
        self.print_modified_dict(modified_webhook, f"webhook[url='{webhook_url}']", {"secret"}, forced_update)

        if "secret" in modified_webhook:
            new_secret = modified_webhook["secret"].to_value
            if not new_secret:
                self.printer.println(f"\n{Fore.RED}Warning:{Style.RESET_ALL} removing secret for webhook "
                                     f"with url '{webhook_url}'")

    def handle_modified_repo(self, org_id: str, repo_name: str, modified_repo: dict[str, Change[Any]]) -> int:
        self.print_modified_dict(modified_repo, f"repo[name=\"{repo_name}\"]")

        settings_to_change = 0
        for k, v in modified_repo.items():
            if Repository.is_read_only_key(k):
                self.printer.println(f"\n{Fore.YELLOW}Note:{Style.RESET_ALL} setting '{k}' "
                                     f"is read-only, will be skipped.")
            else:
                settings_to_change += 1

        return settings_to_change

    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Change[Any]]) -> None:

        self.printer.println()
        self.print_modified_dict(modified_rule,
                                 f"branch_protection_rule[repo=\"{repo_name}\", pattern=\"{rule_pattern}\"]")

    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        self.printer.println()
        self.printer.println(f"\n{Style.BRIGHT}Plan:{Style.RESET_ALL} {diff_status.additions} to add, "
                             f"{diff_status.differences} to change, "
                             f"{diff_status.deletions} to delete.")
