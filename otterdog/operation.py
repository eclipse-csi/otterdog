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

from config import OtterdogConfig, OrganizationConfig
from utils import IndentingPrinter


class Operation(Protocol):
    _DEFAULT_WIDTH = 56

    @property
    @abstractmethod
    def printer(self) -> IndentingPrinter:
        pass

    @abstractmethod
    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None: raise NotImplementedError

    @abstractmethod
    def execute(self, org_config: OrganizationConfig) -> int: raise NotImplementedError

    def print_dict(self, data: dict[str, Any], item_header: str, action: str, color: str) -> None:
        prefix = f"{color}{action}{Style.RESET_ALL} " if action else ""
        closing_prefix = " " * len(action) + " " if action else ""

        self.printer.print(f"{prefix}{item_header} {{")
        self.printer.level_up()

        for key, value in data.items():
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

    def print_modified_dict(self, data: dict[str, Any], item_header: str) -> None:
        self.printer.print(f"\n{Fore.YELLOW}~ {Style.RESET_ALL}{item_header} {{")
        self.printer.level_up()

        for key, (expected_value, current_value) in data.items():
            self.printer.print(f"{Fore.YELLOW}~ {Style.RESET_ALL}{key.ljust(self._DEFAULT_WIDTH, ' ')} ="
                               f" \"{current_value}\" {Fore.YELLOW}->{Style.RESET_ALL} \"{expected_value}\"")

        self.printer.level_down()
        self.printer.print(f"  }}")
