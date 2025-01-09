#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING

from otterdog.config import CredentialResolver
from otterdog.utils import Change, IndentingPrinter, unwrap

if TYPE_CHECKING:
    from typing import Any

    from otterdog.config import OrganizationConfig, OtterdogConfig
    from otterdog.credentials import Credentials


class Operation(ABC):
    _DEFAULT_WIDTH: int = 33

    def __init__(self) -> None:
        self._config: OtterdogConfig | None = None
        self._printer: IndentingPrinter | None = None

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        self._config = config
        self._printer = printer

    @property
    def config(self) -> OtterdogConfig:
        return unwrap(self._config)

    @cached_property
    def credential_resolver(self) -> CredentialResolver:
        return CredentialResolver(self.config)

    def get_credentials(self, org_config: OrganizationConfig, only_token: bool = False) -> Credentials:
        return self.credential_resolver.get_credentials(org_config, only_token)

    @property
    def printer(self) -> IndentingPrinter:
        return unwrap(self._printer)

    @printer.setter
    def printer(self, value: IndentingPrinter):
        self._printer = value

    @abstractmethod
    def pre_execute(self) -> None: ...

    @abstractmethod
    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int: ...

    def post_execute(self) -> None:
        return

    async def check_config_file_exists(self, file_name: str) -> bool:
        from aiofiles import ospath

        if not await ospath.exists(file_name):
            self.printer.print_error(
                f"configuration file '{file_name}' does not exist, run 'fetch-config' or 'import' first."
            )
            return False
        else:
            return True

    async def check_config_file_overwrite_if_exists(self, file_name: str, force: bool) -> bool:
        from aiofiles import ospath

        from otterdog.utils import get_approval

        if await ospath.exists(file_name) and not force:
            self.printer.println()
            self.printer.println(f"[bold]Configuration already exists[/] at '{file_name}'.")
            self.printer.println("  Performing this action will overwrite its contents.")
            self.printer.println("  Do you want to continue? (Only 'yes' or 'y' will be accepted to approve)\n")

            self.printer.print("[bold]Enter a value:[/] ")
            if not get_approval():
                self.printer.println("\nOperation cancelled.")
                return False

        return True

    def _print_project_header(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> None:
        self.printer.println(
            f"\nProject [bold]{org_config.name}[/]\\[github_id={org_config.github_id}]"
            f"{self._format_progress(org_index, org_count)}"
        )

    @staticmethod
    def _format_progress(org_index: int | None, org_count: int | None) -> str:
        if org_index is None or org_count is None:
            return ""
        else:
            return f" ({org_index}/{org_count})"

    def print_dict(
        self,
        data: dict[str, Any],
        item_header: str,
        action: str,
        color: str,
        key_value_separator: str = "=",
        value_separator: str = "",
    ) -> None:
        prefix = f"[{color}]{action}[/] " if action else ""
        closing_prefix = prefix

        max_key_length = self._get_max_key_length_for_nested_dict(data)

        if item_header:
            self.printer.print(f"{prefix}{item_header} ")
        self._print_dict_internal(
            data, max_key_length, prefix, closing_prefix, False, key_value_separator, value_separator
        )

    def _print_internal(
        self,
        data: Any,
        max_key_length: int,
        prefix: str,
        closing_prefix: str,
        include_prefix: bool,
        key_value_separator: str,
        value_separator: str,
    ):
        if isinstance(data, dict):
            self._print_dict_internal(
                data,
                max_key_length,
                prefix,
                closing_prefix,
                include_prefix,
                key_value_separator,
                value_separator,
            )
        elif isinstance(data, list):
            self._print_list_internal(
                data,
                max_key_length,
                prefix,
                closing_prefix,
                key_value_separator,
                value_separator,
            )
        else:
            self.printer.println(
                f"{prefix if include_prefix else ''}{self._get_value(data)}{value_separator}", highlight=True
            )

    def _print_dict_internal(
        self,
        data: dict[str, Any],
        max_key_length: int,
        prefix: str,
        closing_prefix: str,
        include_prefix: bool,
        key_value_separator: str,
        value_separator: str,
    ):
        if len(data) > 0:
            self.printer.println(f"{prefix if include_prefix else ''}{{")
            self.printer.level_up()
            for key, value in sorted(data.items()):
                self.printer.print(f"{prefix}{key.ljust(max_key_length, ' ')} {key_value_separator} ")
                self._print_internal(
                    value, max_key_length, prefix, closing_prefix, False, key_value_separator, value_separator
                )

            self.printer.level_down()
            self.printer.println(f"{closing_prefix}}}{value_separator}")
        else:
            self.printer.println(f"{prefix if include_prefix else ''}{{}}{value_separator}")

    def _print_list_internal(
        self,
        data: list[Any],
        max_key_length: int,
        prefix: str,
        closing_prefix: str,
        key_value_separator: str,
        value_separator: str,
    ):
        if len(data) > 0:
            self.printer.println("[", highlight=True)
            self.printer.level_up()
            for entry in data:
                self._print_internal(
                    entry,
                    max_key_length,
                    prefix,
                    closing_prefix,
                    True,
                    key_value_separator,
                    value_separator,
                )

            self.printer.level_down()
            self.printer.println(f"{closing_prefix}],", highlight=True)
        else:
            self.printer.println(f"[]{value_separator}")

    @staticmethod
    def _get_value(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, int):
            return str(value)
        else:
            return f'"{value}"'

    def _get_max_key_length(self, data: dict[str, Change[Any]]) -> int:
        length = 0

        for key, change in sorted(data.items()):
            expected_value = change.to_value

            length = max(length, len(key))
            if isinstance(expected_value, dict):
                for k, _ in expected_value.items():
                    length = max(length, len(k) + self.printer.spaces_per_level)

        return length

    def _get_max_key_length_for_nested_dict(self, data: dict[str, Any]) -> int:
        length = 0

        for key, value in sorted(data.items()):
            length = max(length, len(key))
            if isinstance(value, dict):
                for k, _ in value.items():
                    length = max(length, len(k) + self.printer.spaces_per_level)

        return length

    def print_modified_dict(
        self,
        data: dict[str, Change[Any]],
        item_header: str,
        forced_update: bool = False,
    ) -> None:
        prefix = "[magenta]! [/]" if forced_update else "[yellow]~ [/]"
        closing_prefix = prefix
        color = "magenta" if forced_update else "yellow"

        self.printer.println(f"\n{prefix}{item_header} {{")
        self.printer.level_up()

        max_key_length = self._get_max_key_length(data)

        for key, change in sorted(data.items()):
            current_value = change.from_value
            expected_value = change.to_value
            self._print_modified_internal(
                key,
                max_key_length,
                current_value,
                expected_value,
                prefix,
                color,
                forced_update,
            )

        self.printer.level_down()
        self.printer.println(f"{closing_prefix}}}")

    def _print_modified_internal(
        self,
        key: str,
        max_key_length: int,
        current_value,
        expected_value,
        prefix: str,
        color: str,
        forced_update: bool,
    ):
        if isinstance(expected_value, dict):
            self.printer.println(f"{prefix}{key.ljust(max_key_length, ' ')} = {{")
            self.printer.level_up()
            self._print_modified_dict_internal(
                max_key_length,
                current_value,
                expected_value,
                prefix,
                color,
                forced_update,
            )
            self.printer.level_down()
            self.printer.println(f"{prefix}}}")
        elif isinstance(expected_value, list):
            self.printer.println(f"{prefix}{key.ljust(max_key_length, ' ')} = [")
            self.printer.level_up()
            self._print_modified_list_internal(current_value, expected_value, prefix, color, forced_update)
            self.printer.level_down()
            self.printer.println(f"{prefix}]")
        else:
            self.printer.println(
                f"{prefix}{key.ljust(max_key_length, ' ')} ="
                f' {self._get_value(current_value)} [{color}]->[/] {self._get_value(expected_value)}'
            )

    def _print_modified_dict_internal(
        self,
        max_key_length: int,
        current_value,
        expected_value,
        prefix: str,
        color: str,
        forced_update: bool,
    ) -> None:
        processed_keys = set()
        for k, v in sorted(expected_value.items()):
            c_v = current_value.get(k) if current_value is not None else None

            if v != c_v:
                if c_v is None:
                    self.printer.println(f"[green]+ [/]{k.ljust(max_key_length, ' ')} =" f" {self._get_value(v)}")
                elif v is None:
                    self.printer.println(f"[red]- [/]{k.ljust(max_key_length, ' ')} =" f" {self._get_value(c_v)}")
                else:
                    self._print_modified_internal(k, max_key_length, c_v, v, prefix, color, forced_update)
            elif forced_update is True:
                self._print_modified_internal(k, max_key_length, c_v, v, prefix, color, forced_update)

            processed_keys.add(k)

        if current_value is not None:
            for k, v in sorted(current_value.items()):
                if k not in processed_keys:
                    self.printer.println(f"[red]- [/]{k.ljust(max_key_length, ' ')} =" f" {self._get_value(v)}")

    def _print_modified_list_internal(
        self,
        current_value,
        expected_value,
        prefix: str,
        color: str,
        forced_update: bool,
    ) -> None:
        from difflib import SequenceMatcher

        a = sorted(current_value)
        b = sorted(expected_value)

        max_length_a = max((len(str(x)) for x in a), default=0)
        max_length_b = max((len(str(x)) for x in b), default=0)

        max_length = max(max_length_a, max_length_b)

        for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b).get_opcodes():
            match tag:
                case "equal":
                    if forced_update is True:
                        for i in range(i1, i2):
                            self.printer.println(f"{prefix}{self._get_value(a[i])}")
                case "replace":
                    diff_i = i2 - i1
                    diff_j = j2 - j1

                    i = i1
                    j = j1

                    for _ in range(i1, min(diff_i, diff_j)):
                        self.printer.println(
                            f"{prefix}{self._get_value(a[i]).ljust(max_length, ' ')} [{color}]->[/] "
                            f"{self._get_value(b[j])}"
                        )
                        j = j + 1
                        i = i + 1

                    while i < i2:
                        self.printer.println(f"[red]- [/]{self._get_value(a[i])}")
                        i = i + 1

                    while j < j2:
                        self.printer.println(f"[green]+ [/]{self._get_value(b[j])}")
                        j = j + 1

                case "delete":
                    for i in range(i1, i2):
                        self.printer.println(f"[red]- [/]{self._get_value(a[i])}")
                case "insert":
                    for j in range(j1, j2):
                        self.printer.println(f"[green]+ [/]{self._get_value(b[j])}")
