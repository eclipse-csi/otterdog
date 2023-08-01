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
from otterdog.models.secret import Secret
from otterdog.models.webhook import Webhook
from otterdog.utils import IndentingPrinter, Change

from .diff_operation import DiffOperation, DiffStatus


class PlanOperation(DiffOperation):
    def __init__(self, no_web_ui: bool, update_webhooks: bool, update_secrets: bool, update_filter: str):
        super().__init__(no_web_ui, update_webhooks, update_secrets, update_filter)

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

    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        self.printer.println()
        model_header = model_object.get_model_header(parent_object)
        self.print_dict(
            model_object.to_model_dict(for_diff=True),
            f"add {model_header}",
            "+",
            Fore.GREEN,
        )

    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        self.printer.println()
        model_header = model_object.get_model_header(parent_object)
        self.print_dict(
            model_object.to_model_dict(for_diff=True),
            f"remove {model_header}",
            "-",
            Fore.RED,
        )

    def handle_modified_object(
        self,
        org_id: str,
        modified_object: dict[str, Change[Any]],
        forced_update: bool,
        current_object: ModelObject,
        expected_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> int:
        self.printer.println()
        model_header = current_object.get_model_header(parent_object)

        # FIXME: this code should be moved to the model class.
        if isinstance(expected_object, Secret):
            redacted_keys = {"value"} if self.resolve_secrets() is True else set()
        elif isinstance(expected_object, Webhook):
            redacted_keys = {"secret"} if self.resolve_secrets() is True else set()
        else:
            redacted_keys = set()

        self.print_modified_dict(modified_object, model_header, redacted_keys, forced_update)

        # FIXME: this code should be moved to the Webhook model class.
        if isinstance(current_object, Webhook):
            if "secret" in modified_object:
                new_secret = modified_object["secret"].to_value
                if not new_secret:
                    self.printer.println(
                        f"\n{Fore.RED}Warning:{Style.RESET_ALL} removing secret for webhook "
                        f"with url '{current_object.url}'"
                    )

        settings_to_change = 0
        for k, v in modified_object.items():
            if current_object.is_read_only_key(k):
                self.printer.println(
                    f"\n{Fore.YELLOW}Note:{Style.RESET_ALL} setting '{k}' " f"is read-only, will be skipped."
                )
            else:
                settings_to_change += 1

        return settings_to_change

    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        self.printer.println(
            f"\n{Style.BRIGHT}Plan:{Style.RESET_ALL} {diff_status.additions} to add, "
            f"{diff_status.differences} to change, "
            f"{diff_status.deletions} to delete."
        )
