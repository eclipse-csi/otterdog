# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from abc import ABC, abstractmethod
from typing import Any, Optional

from colorama import Fore, Style

from otterdog.config import OtterdogConfig, OrganizationConfig
from otterdog.utils import IndentingPrinter, Change, is_unset


class Operation(ABC):
    _DEFAULT_WIDTH: int = 56

    def __init__(self) -> None:
        self._config: Optional[OtterdogConfig] = None
        self._printer: Optional[IndentingPrinter] = None

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        self._config = config
        self._printer = printer

    @property
    def config(self) -> OtterdogConfig:
        assert self._config is not None
        return self._config

    @property
    def printer(self) -> IndentingPrinter:
        assert self._printer is not None
        return self._printer

    @abstractmethod
    def pre_execute(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(self, org_config: OrganizationConfig) -> int:
        raise NotImplementedError

    def print_dict(self, data: dict[str, Any], item_header: str, action: str, color: str) -> None:
        prefix = f"{color}{action}{Style.RESET_ALL} " if action else ""
        closing_prefix = " " * len(action) + " " if action else ""

        self.printer.println(f"{prefix}{item_header} {{")
        self.printer.level_up()

        for key, value in sorted(data.items()):
            if isinstance(value, dict):
                self.printer.println(f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {{")
                self.printer.level_up()
                for k, v in value.items():
                    self.printer.println(f"{prefix}{k.ljust(self._DEFAULT_WIDTH, ' ')} = {self._get_value(v)}")
                self.printer.level_down()
                self.printer.println(f"{closing_prefix}}}")
            elif isinstance(value, list):
                self.printer.println(f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {value}")
            else:
                self.printer.println(f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {self._get_value(value)}")

        self.printer.level_down()
        self.printer.println(f"{closing_prefix}}}")

    @staticmethod
    def _get_value(value: Any) -> str:
        if value is None:
            return str(value)
        if isinstance(value, bool):
            return str(value)
        else:
            return f"\"{value}\""

    def print_modified_dict(self,
                            data: dict[str, Change[Any]],
                            item_header: str,
                            redacted_keys: Optional[set[str]] = None,
                            forced_update: bool = False) -> None:
        action = f"{Fore.MAGENTA}!" if forced_update else f"{Fore.YELLOW}~"
        color = f"{Fore.MAGENTA}" if forced_update else f"{Fore.YELLOW}"

        self.printer.println(f"\n{action} {Style.RESET_ALL}{item_header} {{")
        self.printer.level_up()

        for key, change in sorted(data.items()):
            current_value = change.from_value
            expected_value = change.to_value

            if isinstance(expected_value, dict):
                self.printer.println(f"{action} {Style.RESET_ALL}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {{")
                self.printer.level_up()

                processed_keys = set()
                for k, v in sorted(expected_value.items()):
                    c_v = current_value.get(k) if current_value is not None else None

                    if v != c_v:
                        self.printer.println(f"{action} {Style.RESET_ALL}"
                                             f"{k.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                             f" \"{c_v}\" {color}->{Style.RESET_ALL} \"{v}\"")

                    processed_keys.add(k)

                if current_value is not None:
                    for k, v in sorted(current_value.items()):
                        if k not in processed_keys:
                            self.printer.println(f"{Fore.RED}- {Style.RESET_ALL}{k.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                                 f" \"{v}\"")

                self.printer.println("}")
                self.printer.level_down()
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

                self.printer.println(f"{action} {Style.RESET_ALL}{key.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                     f" \"{c_v}\" {color}->{Style.RESET_ALL} \"{e_v}\"")

        self.printer.println("}")
        self.printer.level_down()
