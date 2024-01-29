#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from abc import ABC, abstractmethod
from typing import Any, Optional

from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.utils import Change, IndentingPrinter, is_unset, style


class Operation(ABC):
    _DEFAULT_WIDTH: int = 33

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

    @printer.setter
    def printer(self, value: IndentingPrinter):
        self._printer = value

    @abstractmethod
    def pre_execute(self) -> None:
        ...

    @abstractmethod
    async def execute(self, org_config: OrganizationConfig) -> int:
        ...

    def post_execute(self) -> None:
        pass

    def print_dict(
        self,
        data: dict[str, Any],
        item_header: str,
        action: str,
        color: str,
        key_value_separator: str = "=",
        value_separator: str = "",
    ) -> None:
        prefix = f"{style(action, fg=color)} " if action else ""
        closing_prefix = prefix

        if item_header:
            self.printer.print(f"{prefix}{item_header} ")
        self._print_dict_internal(data, prefix, closing_prefix, False, key_value_separator, value_separator)

    def _print_internal(
        self,
        data: Any,
        prefix: str,
        closing_prefix: str,
        include_prefix: bool,
        key_value_separator: str,
        value_separator: str,
    ):
        if isinstance(data, dict):
            self._print_dict_internal(
                data, prefix, closing_prefix, include_prefix, key_value_separator, value_separator
            )
        elif isinstance(data, list):
            self._print_list_internal(data, prefix, closing_prefix, key_value_separator, value_separator)
        else:
            self.printer.println(f"{prefix if include_prefix else ''}{self._get_value(data)}{value_separator}")

    def _print_dict_internal(
        self,
        data: dict[str, Any],
        prefix: str,
        closing_prefix: str,
        include_prefix: bool,
        key_value_separator: str,
        value_separator: str,
    ):
        self.printer.println(f"{prefix if include_prefix else ''}{{")
        self.printer.level_up()
        for key, value in sorted(data.items()):
            self.printer.print(f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} {key_value_separator} ")
            self._print_internal(value, prefix, closing_prefix, False, key_value_separator, value_separator)

        self.printer.level_down()
        self.printer.println(f"{closing_prefix}}}{value_separator}")

    def _print_list_internal(
        self, data: list[Any], prefix: str, closing_prefix: str, key_value_separator: str, value_separator: str
    ):
        if len(data) > 0:
            self.printer.println("[")
            self.printer.level_up()
            for entry in data:
                self._print_internal(entry, prefix, closing_prefix, True, key_value_separator, value_separator)

            self.printer.level_down()
            self.printer.println(f"{closing_prefix}],")
        else:
            self.printer.println(f"[]{value_separator}")

    @staticmethod
    def _get_value(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return str(value).lower()
        else:
            return f'"{value}"'

    def print_modified_dict(
        self,
        data: dict[str, Change[Any]],
        item_header: str,
        redacted_keys: Optional[set[str]] = None,
        forced_update: bool = False,
    ) -> None:
        prefix = style("! ", fg="magenta") if forced_update else style("~ ", fg="yellow")
        closing_prefix = prefix
        color = "magenta" if forced_update else "yellow"

        self.printer.println(f"\n{prefix}{item_header} {{")
        self.printer.level_up()

        for key, change in sorted(data.items()):
            current_value = change.from_value
            expected_value = change.to_value

            if isinstance(expected_value, dict):
                self.printer.println(f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} = {{")
                self.printer.level_up()

                processed_keys = set()
                for k, v in sorted(expected_value.items()):
                    c_v = current_value.get(k) if current_value is not None else None

                    if v != c_v:
                        self.printer.println(
                            f"{prefix}{k.ljust(self._DEFAULT_WIDTH, ' ')} ="
                            f' {self._get_value(c_v)} {style("->", fg=color)} {self._get_value(v)}'
                        )

                    processed_keys.add(k)

                if current_value is not None:
                    for k, v in sorted(current_value.items()):
                        if k not in processed_keys:
                            self.printer.println(
                                f"{style('- ', fg='red')}{k.ljust(self._DEFAULT_WIDTH, ' ')} =" f" {self._get_value(v)}"
                            )

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

                self.printer.println(
                    f"{prefix}{key.ljust(self._DEFAULT_WIDTH, ' ')} ="
                    f' {self._get_value(c_v)} {style("->", fg=color)} {self._get_value(e_v)}'
                )

        self.printer.level_down()
        self.printer.println(f"{closing_prefix}}}")
