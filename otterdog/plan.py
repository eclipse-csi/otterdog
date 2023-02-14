# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Any

from colorama import Fore, Style

from config import OtterdogConfig
from diff import DiffOperation
from utils import IndentingPrinter


class PlanOperation(DiffOperation):
    def __init__(self):
        super().__init__()

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)
        self.printer.print(f"Planning execution for configuration at '{config.config_file}'")
        self.printer.print(f"\nActions are indicted with the following symbols:")
        self.printer.print(f"  {Fore.GREEN}+{Style.RESET_ALL} create")
        self.printer.print(f"  {Fore.YELLOW}~{Style.RESET_ALL} modify")
        self.printer.print(f"  {Fore.RED}-{Style.RESET_ALL} extra (missing in definition but available live)")

    def handle_modified_settings(self, org_id: str, modified_settings: dict[str, (Any, Any)]) -> None:
        self.printer.print(f"\n{Fore.YELLOW}~ {Style.RESET_ALL}settings {{")
        self.printer.level_up()

        for key, (expected_value, current_value) in modified_settings.items():
            self.printer.print(f"{Fore.YELLOW}~ {Style.RESET_ALL}{key.ljust(30, ' ')} ="
                               f" \"{current_value}\" {Fore.YELLOW}->{Style.RESET_ALL} \"{expected_value}\"")

        self.printer.level_down()
        self.printer.print(f"  }}")

    def handle_modified_webhook(self, org_id: str, webhook_id: str, modified_webhook: dict[str, (Any, Any)]) -> None:
        for key, (expected_value, current_value) in modified_webhook.items():
            msg = f"  webhook['{webhook_id}'].config.{key}: expected '{expected_value}' but was '{current_value}'"
            self.printer.print_info(msg)

    def handle_extra_webhook(self, org_id: str, webhook: dict[str, Any]) -> None:
        self.printer.print()
        print_dict(webhook, "extra webhook", "-", Fore.RED, self.printer)

    def handle_new_webhook(self, org_id: str, webhook: dict[str, Any]) -> None:
        self.printer.print()
        print_dict(webhook, "new webhook", "+", Fore.GREEN, self.printer)

    def handle_modified_repo(self, org_id: str, repo_name: str, modified_repo: dict[str, (Any, Any)]) -> None:
        print(f"  {Fore.YELLOW}~ {Style.RESET_ALL}repo[name=\"{repo_name}\"] {{")
        for key, (expected_value, current_value) in modified_repo.items():
            print(f"    {Fore.YELLOW}~ {Style.RESET_ALL}{key.ljust(30, ' ')} ="
                  f" \"{current_value}\" {Fore.YELLOW}->{Style.RESET_ALL} \"{expected_value}\"")
        print(f"    }}")

    def handle_new_repo(self,
                        org_id: str,
                        data: dict[str, Any]) -> None:
        print(f"  {Fore.GREEN}+{Style.RESET_ALL} new repo {{")
        for key, value in data.items():
            print(f"    {Fore.GREEN}+ {Style.RESET_ALL}{key.ljust(30, ' ')} = \"{value}\"")
        print(f"    }}")

    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Any]) -> None:
        for key, (expected_value, current_value) in modified_rule.items():
            msg = f"  branch_protection_rule['{rule_pattern}'].{key}: " \
                  f"expected '{expected_value}' but was '{current_value}'"
            self.printer.print_info(msg)

    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        self.printer.print_info(f"new branch_protection_rule for repo '{repo_name}'"
                                f"with data:\n{json.dumps(data, indent=2)}")

    def handle_finish(self, additions: int, differences: int, extras: int) -> None:
        self.printer.print(f"\n{Style.BRIGHT}Plan:{Style.RESET_ALL} {additions} to add, {differences} to change, "
                           f"{extras} are missing in definition.")


def print_dict(data: dict[str, Any], item_header: str, action: str, color: str, printer: IndentingPrinter) -> None:
    printer.print(f"{color}{action}{Style.RESET_ALL} {item_header} {{")
    printer.level_up()

    for key, value in data.items():
        if isinstance(value, dict):
            printer.print(f"{color}{action} {Style.RESET_ALL}{key.ljust(30, ' ')} = {{")
            printer.level_up()
            for k, v in value.items():
                printer.print(f"{color}{action} {Style.RESET_ALL}{k.ljust(30, ' ')} = \"{v}\"")
            printer.level_down()
            printer.print(f"  }}")
        elif isinstance(value, list):
            printer.print(f"{color}{action} {Style.RESET_ALL}{key.ljust(30, ' ')} = {value}")
        else:
            printer.print(f"{color}{action} {Style.RESET_ALL}{key.ljust(30, ' ')} = \"{value}\"")

    printer.level_down()
    printer.print(f"  }}")
