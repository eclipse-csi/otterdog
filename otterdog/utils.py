#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import json
import re
import sys
from argparse import Namespace
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    TypeGuard,
    TypeVar,
    Union,
)
from urllib.parse import urlparse

import click
from colorama import Style

T = TypeVar("T")


# verbose levels
# 0: off
# 1: info
# 2: debug
# 3: trace
_verbose_level = 0


def init(verbose: int) -> None:
    global _verbose_level
    _verbose_level = verbose


def is_info_enabled() -> bool:
    return _verbose_level >= 1


def is_debug_enabled() -> bool:
    return _verbose_level >= 2


def is_trace_enabled() -> bool:
    return _verbose_level >= 3


def style(
    text: str,
    fg: Optional[Union[int, Tuple[int, int, int], str]] = None,
    bg: Optional[Union[int, Tuple[int, int, int], str]] = None,
    bold: Optional[bool] = None,
    bright: Optional[bool] = None,
    dim: Optional[bool] = None,
    underline: Optional[bool] = None,
    overline: Optional[bool] = None,
    italic: Optional[bool] = None,
    blink: Optional[bool] = None,
    reverse: Optional[bool] = None,
    strikethrough: Optional[bool] = None,
    reset: bool = True,
) -> str:
    if bright is True:
        text = f"{Style.BRIGHT}{text}"
    return click.style(text, fg, bg, bold, dim, underline, overline, italic, blink, reverse, strikethrough, reset)


def print_info(msg: str, printer: TextIO = sys.stdout) -> None:
    if is_info_enabled():
        _print_message(msg, "green", "Info", printer)


def print_debug(msg: str, printer: TextIO = sys.stdout) -> None:
    if is_debug_enabled():
        printer.write(f"{style('[DEBUG]', fg='cyan')} {msg}\n")


def print_trace(msg: str, printer: TextIO = sys.stdout) -> None:
    if is_trace_enabled():
        printer.write(f"{style('[TRACE]', fg='magenta')} {msg}\n")


def print_warn(msg: str, printer: TextIO = sys.stdout) -> None:
    _print_message(msg, "yellow", "Warning", printer)


def print_error(msg: str, printer: TextIO = sys.stdout) -> None:
    _print_message(msg, "red", "Error", printer)


def _print_message(msg: str, color: str, level: str, printer: TextIO) -> None:
    printer.write(style("╷\n", fg=color))

    lines = msg.splitlines()
    level_prefix = style(f"│ {level}:", fg=color)

    if len(lines) > 1:
        printer.write(f"{level_prefix} {lines[0]}\n")
        printer.write(style("│\n", fg=color))
        for line in lines[1:]:
            printer.write(f"{style('│', fg=color)}    {line}\n")
    else:
        printer.write(f"{level_prefix} {msg}\n")

    printer.write(style("╵\n", fg=color))


class _Unset:
    """
    A marker class to indicate that a value is unset and thus should
    not be considered. This is different to None.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(_Unset, cls).__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<UNSET>"

    def __bool__(self) -> Literal[False]:
        return False

    def __copy__(self):
        return UNSET

    def __deepcopy__(self, memo: dict[int, Any]):
        return UNSET


UNSET = _Unset()


def is_unset(value: Any) -> bool:
    """
    Returns whether the given value is an instance of Unset.
    """
    return value is UNSET


def is_set_and_valid(value: Any) -> bool:
    return not is_unset(value) and value is not None


def is_set_and_present(value: Optional[T]) -> TypeGuard[T]:
    return is_set_and_valid(value)


@dataclass
class Change(Generic[T]):
    from_value: Optional[T]
    to_value: Optional[T]


def is_different_ignoring_order(value: Any, other_value: Any) -> bool:
    """
    Checks whether two values are considered to be equal.
    Note: two lists are considered to be equal if they contain the same elements,
    regardless or the order.
    """
    if isinstance(value, list):
        return sorted(value) != sorted(other_value)

    return value != other_value


def patch_to_other(value: Any, other_value: Any) -> tuple[bool, Any]:
    if isinstance(value, dict):
        raise ValueError("dictionary values not supported")
    elif isinstance(value, list):
        sorted_value_list = sorted(value)
        sorted_other_list = sorted(other_value)

        if sorted_value_list != sorted_other_list:
            diff = _diff_list(sorted_value_list, sorted_other_list)
            if len(diff) > 0:
                return True, diff
            else:
                return False, diff
    else:
        if value != other_value:
            return True, value

    # values are not different, no patch generated
    return False, None


def _diff_list(list1: list[T], list2: list[T]) -> list[T]:
    s = set(list2)
    return [x for x in list1 if x not in s]


def write_patch_object_as_json(
    diff_object: dict[str, Any], printer: IndentingPrinter, close_object: bool = True
) -> None:
    if close_object is True and len(diff_object) == 0:
        printer.println(",")
        return

    printer.println(" {")
    printer.level_up()

    for key, value in sorted(diff_object.items()):
        if is_unset(value):
            print_warn(f"key '{key}' defined in default configuration not present in config, skipping")
            continue

        if isinstance(value, list):
            printer.println(f"{key}+: [")
            printer.level_up()
            num_items = len(value)
            for index, item in enumerate(value):
                if index < num_items - 1:
                    printer.println(f"{json.dumps(item, ensure_ascii=False)},")
                else:
                    printer.println(f"{json.dumps(item, ensure_ascii=False)}")
            printer.level_down()
            printer.println("],")
        else:
            printer.println(f"{key}: {json.dumps(value, ensure_ascii=False)},")

    if close_object is True:
        printer.level_down()
        printer.println("},")


def associate_by_key(input_list: Sequence[T], key_func: Callable[[T], str]) -> dict[str, T]:
    result = {}
    for item in input_list:
        key = key_func(item)

        if key in result:
            raise RuntimeError(f"duplicate item found with key '{key}'")

        result[key] = item

    return result


def multi_associate_by_key(input_list: Sequence[T], key_func: Callable[[T], list[str]]) -> dict[str, T]:
    result = {}
    for item in input_list:
        keys = key_func(item)

        for key in keys:
            if key in result:
                raise RuntimeError(f"duplicate item found with key '{key}'")

            result[key] = item

    return result


class LogLevel(Enum):
    GLOBAL = 0
    INFO = 1
    WARN = 2
    ERROR = 3


class IndentingPrinter:
    def __init__(
        self, writer: TextIO, initial_offset: int = 0, spaces_per_level: int = 2, log_level: LogLevel = LogLevel.GLOBAL
    ):
        self._writer = writer
        self._initial_offset = " " * initial_offset
        self._level = 0
        self._spaces_per_level = spaces_per_level
        self._indented_line = False
        self._log_level = log_level

    @property
    def writer(self) -> TextIO:
        return self._writer

    @property
    def _current_indentation(self) -> str:
        return self._initial_offset + " " * (self._level * self._spaces_per_level)

    def print(self, text: str = "") -> None:
        lines = text.splitlines(keepends=True)
        if len(lines) > 0:
            for line in lines:
                self._print_indentation()

                if line.endswith("\n"):
                    self._writer.write(line[:-1])
                    self.print_line_break()
                else:
                    self._writer.write(line)

    def println(self, text: str = "") -> None:
        self.print(text)
        self.print_line_break()

    def print_line_break(self) -> None:
        self._writer.write("\n")
        self._indented_line = False

    def _print_indentation(self) -> None:
        if not self._indented_line:
            self._writer.write(self._current_indentation)
            self._indented_line = True

    def _is_logging_enabled(self, level: int, global_fn: Callable[[], bool]) -> bool:
        match self._log_level:
            case LogLevel.GLOBAL:
                return global_fn()

            case _:
                return self._log_level.value <= level

    def print_info(self, msg: str) -> None:
        if self._is_logging_enabled(1, is_info_enabled):
            _print_message(msg, "green", "Info", self._writer)

    def is_info_enabled(self) -> bool:
        return self._is_logging_enabled(1, is_info_enabled)

    def print_warn(self, msg: str) -> None:
        if self._is_logging_enabled(2, lambda: True):
            _print_message(msg, "yellow", "Warning", self._writer)

    def print_error(self, msg: str) -> None:
        if self._is_logging_enabled(3, lambda: True):
            _print_message(msg, "red", "Error", self._writer)

    def level_up(self) -> None:
        self._level += 1

    def level_down(self) -> None:
        self._level -= 1
        assert self._level >= 0


def jsonnet_evaluate_file(file: str) -> dict[str, Any]:
    import _gojsonnet  # type: ignore

    print_trace(f"evaluating jsonnet file {file}")

    try:
        return json.loads(_gojsonnet.evaluate_file(file))
    except Exception as ex:
        raise RuntimeError(f"failed to evaluate jsonnet file: {str(ex)}")


def jsonnet_evaluate_snippet(snippet: str) -> dict[str, Any]:
    import _gojsonnet  # type: ignore

    print_trace(f"evaluating jsonnet snippet {snippet}")

    try:
        return json.loads(_gojsonnet.evaluate_snippet("", snippet))
    except Exception as ex:
        raise RuntimeError(f"failed to evaluate snippet: {str(ex)}")


def get_or_default(namespace: Namespace, key: str, default: T) -> T:
    if namespace.__contains__(key):
        return namespace.__getattribute__(key)
    else:
        return default


def snake_to_camel_case(string: str) -> str:
    result = re.sub(r"[_\-]+", " ", string).title().replace(" ", "")
    return result[0].lower() + result[1:]


def camel_to_snake_case(string: str) -> str:
    string = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", string)
    string = re.sub("__([A-Z])", r"_\1", string)
    string = re.sub("([a-z0-9])([A-Z])", r"\1_\2", string)
    return string.lower()


def parse_template_url(url: str) -> tuple[str, str, str]:
    parts = urlparse(url)

    if parts.netloc != "github.com":
        raise ValueError(f"only github.com is supported for template urls: {parts.netloc}")

    repo_url = f"{parts.scheme}://{parts.netloc}{parts.path}"

    matcher = re.match(r"([^@]+)(@(.*))?", parts.fragment)
    if matcher is None:
        raise ValueError(f"failed to parse file from template url: {url}")

    file = matcher.group(1)
    ref = matcher.group(3)

    if ref is None:
        raise ValueError(f"failed to parse ref from template url: {url}")

    return repo_url, file, ref


def is_ghsa_repo(repo_name: str) -> bool:
    """
    Returns True if the given repo_name is considered to be a repo created for a GitHub security advisory.

    Pattern: <regular repo name>-ghsa-xxxx-xxxx-xxxx
    """
    return re.match(".*-ghsa(-[23456789cfghjmpqrvwx]{4}){3}", repo_name) is not None


def strip_trailing_commas(lines: list[str]) -> list[str]:
    return list(map(lambda line: line.rstrip(","), lines))


def sort_jsonnet(lines: list[str]) -> list[str]:
    ast: list[tuple[str, Any]] = []
    object_stack = [ast]

    for line in lines:
        trimmed_line = line.rstrip().rstrip(",")
        if trimmed_line.endswith("{") or trimmed_line.endswith("["):
            current_node: list[tuple[str, Any]] = []
            object_stack[-1].append((line, current_node))
            object_stack.append(current_node)
        elif trimmed_line.endswith("}") and "{" not in trimmed_line:
            object_stack[-1].append((line, None))
            object_stack.pop()
        elif trimmed_line.endswith("]") and "[" not in trimmed_line:
            object_stack[-1].append((line, None))
            object_stack.pop()
        else:
            object_stack[-1].append((line, None))

    for node in ast:
        _sort_node(node)

    result: list[str] = []
    for node in ast:
        print_node(node, result)
    return result


def _sort_node(node):
    line, context = node

    if context is not None:
        last = context.pop()
        context.sort()
        context.append(last)
        for next_node in context:
            _sort_node(next_node)


def print_node(node, result):
    line, context = node

    result.append(line)
    if context is not None:
        for next_node in context:
            print_node(next_node, result)


def get_approval() -> bool:
    answer = input()
    if answer != "yes" and answer != "y":
        return False
    else:
        return True
