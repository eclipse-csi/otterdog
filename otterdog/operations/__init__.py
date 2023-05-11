# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from abc import abstractmethod
from typing import Protocol, Any

from colorama import Fore, Style

from otterdog.config import OtterdogConfig, OrganizationConfig
from otterdog.utils import IndentingPrinter, Change, is_unset


class Operation(Protocol):
    _DEFAULT_WIDTH = 56

    @property
    @abstractmethod
    def printer(self) -> IndentingPrinter:
        pass

    @abstractmethod
    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        raise NotImplementedError

    @abstractmethod
    def pre_execute(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(self, org_config: OrganizationConfig) -> int:
        raise NotImplementedError

    def print_dict(self, data: dict[str, Any], item_header: str, action: str, color: str) -> None:
        prefix = f"{color}{action}{Style.RESET_ALL} " if action else ""
        closing_prefix = " " * len(action) + " " if action else ""

        self.printer.print(f"{prefix}{item_header} {{")
        self.printer.level_up()

        for key, value in sorted(data.items()):
            if isinstance(value, dict):
                self.printer.print(f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {{")
                self.printer.level_up()
                for k, v in value.items():
                    self.printer.print(f"{prefix}{k.ljust(self._DEFAULT_WIDTH, ' ')} = \"{v}\"")
                self.printer.level_down()
                self.printer.print(f"{closing_prefix}}}")
            elif isinstance(value, list):
                self.printer.print(f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {value}")
            else:
                self.printer.print(f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} = \"{value}\"")

        self.printer.level_down()
        self.printer.print(f"{closing_prefix}}}")

    def print_modified_dict(self,
                            data: dict[str, Change[Any]],
                            item_header: str,
                            redacted_keys: set[str] = None,
                            forced_update: bool = False) -> None:
        action = f"{Fore.MAGENTA}!" if forced_update else f"{Fore.YELLOW}~"
        color = f"{Fore.MAGENTA}" if forced_update else f"{Fore.YELLOW}"

        self.printer.print(f"\n{action} {Style.RESET_ALL}{item_header} {{")
        self.printer.level_up()

        for key, change in sorted(data.items()):
            current_value = change.from_value
            expected_value = change.to_value

            if isinstance(expected_value, dict):
                self.printer.print(f"{action} {Style.RESET_ALL}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {{")
                self.printer.level_up()

                processed_keys = set()
                for k, v in sorted(expected_value.items()):
                    c_v = current_value.get(k)

                    if v != c_v:
                        self.printer.print(f"{action} {Style.RESET_ALL}"
                                           f"{k.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                           f" \"{c_v}\" {color}->{Style.RESET_ALL} \"{v}\"")

                    processed_keys.add(k)

                for k, v in sorted(current_value.items()):
                    if k not in processed_keys:
                        self.printer.print(f"{Fore.RED}- {Style.RESET_ALL}{k.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                           f" \"{v}\"")
                self.printer.level_down()
                self.printer.print("  }}")
            else:
                def should_redact(value: Any) -> bool:
                    if is_unset(value) or value is None:
                        return False

                    if redacted_keys is not None and key is not None and key in redacted_keys:
                        return True
                    else:
                        return False

                c_v = "<redacted>" if should_redact(current_value) else current_value
                e_v = "<redacted>" if should_redact(expected_value) else expected_value

                self.printer.print(f"{action} {Style.RESET_ALL}{key.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                   f" \"{c_v}\" {color}->{Style.RESET_ALL} \"{e_v}\"")

        self.printer.level_down()
        self.printer.print("  }}")
