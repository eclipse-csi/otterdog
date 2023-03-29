#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from abc import abstractmethod
from typing import Protocol, Any

from colorama import Fore, Style

from .config import OtterdogConfig, OrganizationConfig
from .utils import IndentingPrinter


class Operation(Protocol):
    _DEFAULT_WIDTH = 56

    @property
    @abstractmethod
    def printer(self) -> IndentingPrinter:
        pass

    @abstractmethod
    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None: raise NotImplementedError

    @abstractmethod
    def pre_execute(self) -> None: raise NotImplementedError

    @abstractmethod
    def execute(self, org_config: OrganizationConfig) -> int: raise NotImplementedError

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

    def print_modified_dict(self, data: dict[str, Any], item_header: str, redacted_keys: set[str] = None) -> None:
        self.printer.print(f"\n{Fore.YELLOW}~ {Style.RESET_ALL}{item_header} {{")
        self.printer.level_up()

        for key, (expected_value, current_value) in sorted(data.items()):
            if isinstance(expected_value, dict):
                self.printer.print(f"{Fore.YELLOW}~ {Style.RESET_ALL}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {{")
                self.printer.level_up()

                processed_keys = set()
                for k, v in sorted(expected_value.items()):
                    c_v = current_value.get(k)

                    if v != c_v:
                        self.printer.print(f"{Fore.YELLOW}~ {Style.RESET_ALL}{k.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                           f" \"{c_v}\" {Fore.YELLOW}->{Style.RESET_ALL} \"{v}\"")

                    processed_keys.add(k)

                for k, v in sorted(current_value.items()):
                    if k not in processed_keys:
                        self.printer.print(f"{Fore.RED}- {Style.RESET_ALL}{k.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                           f" \"{v}\"")

                self.printer.level_down()
                self.printer.print(f"  }}")
            else:
                e_v = expected_value if not key or \
                                        redacted_keys is None or \
                                        key not in redacted_keys or \
                                        expected_value is None else "<redacted>"

                self.printer.print(f"{Fore.YELLOW}~ {Style.RESET_ALL}{key.ljust(self._DEFAULT_WIDTH, ' ')} ="
                                   f" \"{current_value}\" {Fore.YELLOW}->{Style.RESET_ALL} \"{e_v}\"")

        self.printer.level_down()
        self.printer.print(f"  }}")
