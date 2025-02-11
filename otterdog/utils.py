#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, Literal, TextIO, TypeGuard, TypeVar
from urllib.parse import urlparse

from rich.console import Console

from otterdog.logging import _print_message, get_logger, is_info_enabled

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Callable, Mapping, Sequence

T = TypeVar("T")

_logger = get_logger(__name__)


class _Unset:
    """
    A marker class to indicate that a value is unset and thus should
    not be considered. This is different to None.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
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


def is_set_and_present(value: T | None) -> TypeGuard[T]:
    return is_set_and_valid(value)


def unwrap(value: T | None, error_message: str = "unexpected None when unwrapping value") -> T:
    """
    Will unwrap the given value or raise a ValueError if it is None

    :param value: the optional value to unwrap
    :param error_message: the error message when failing to unwrap
    :return: the value or a ValueError if it is None
    """
    if value is None:
        raise ValueError(error_message)
    else:
        return value


def expect_type(value: Any, expected_type: type[T]) -> T:
    if isinstance(value, expected_type):
        return value
    else:
        raise ValueError(f"unexpected value of type '{type(value)}' while '{expected_type}' was expected")


@dataclass
class Change(Generic[T]):
    from_value: T | None
    to_value: T | None


def is_different_ignoring_order(value: Any, other_value: Any) -> bool:
    """
    Checks whether two values are considered to be equal.
    Note: two lists are considered to be equal if they contain the same elements,
    regardless or the order.
    """
    if isinstance(value, list) and isinstance(other_value, list):
        return sorted(value) != sorted(other_value)
    elif isinstance(value, dict) and isinstance(other_value, dict):
        for key, item_value in value.items():
            other_item_value = other_value.get(key, None)
            if isinstance(item_value, list):
                if sorted(item_value) != sorted(other_item_value):
                    return True
            else:
                if item_value != other_item_value:
                    return True

        return False

    return value != other_value


def patch_to_other(value: Any, other_value: Any) -> tuple[bool, Any]:
    if isinstance(value, dict):
        if len(other_value) == 0:
            if len(value) > 0:
                return True, value
            else:
                return False, None
        else:
            diff = dict(value)

            for k, v in other_value.items():
                if diff.get(k) == v:
                    diff.pop(k)

            if len(diff) == 0:
                return False, None
            else:
                return True, diff
    elif isinstance(value, list):
        sorted_value_list = sorted(value)

        if other_value is None:
            return True, sorted_value_list

        sorted_other_list = sorted(other_value)

        if sorted_value_list != sorted_other_list:
            diff = _diff_list(sorted_value_list, sorted_other_list)  # type: ignore
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
            _logger.warning("key '%s' defined in default configuration not present in config, skipping", key)
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
        elif isinstance(value, dict):
            printer.println(f"{key}+: {{")
            printer.level_up()
            num_items = len(value)
            for index, (k, v) in enumerate(value.items()):
                if index < num_items - 1:
                    printer.println(f"{k}: {json.dumps(v, ensure_ascii=False)},")
                else:
                    printer.println(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            printer.level_down()
            printer.println("},")
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
        self,
        output: TextIO | Console,
        initial_offset: int = 0,
        spaces_per_level: int = 2,
        log_level: LogLevel = LogLevel.GLOBAL,
        output_for_github: bool = False,
    ):
        if isinstance(output, Console):
            self._console = output
            self._writer = self._console.file
        else:
            no_color = output_for_github
            width = (
                110 if output_for_github else 9999
            )  # set a ridiculous high width for the normal case, otherwise rich will try to wrap lines
            self._console = Console(file=output, no_color=no_color, width=width)
            self._writer = output

        self._initial_offset = " " * initial_offset
        self._level = 0
        self._spaces_per_level = spaces_per_level
        self._indented_line = False
        self._log_level = log_level
        self._output_for_github = output_for_github

    @property
    def spaces_per_level(self) -> int:
        return self._spaces_per_level

    @property
    def console(self) -> Console:
        return self._console

    @property
    def writer(self) -> TextIO:
        return self._writer  # type: ignore

    @property
    def current_indentation(self) -> str:
        return self._initial_offset + " " * (self._level * self._spaces_per_level)

    def print(self, text: str = "", highlight: bool = False) -> None:
        lines = text.splitlines(keepends=True)
        if len(lines) > 0:
            for line in lines:
                self._print_indentation()

                if line.endswith("\n"):
                    self._console.print(line[:-1], end="", highlight=highlight)
                    self.print_line_break()
                else:
                    self._console.print(line, end="", highlight=highlight)

    def println(self, text: str = "", highlight: bool = False) -> None:
        self.print(text, highlight=highlight)
        self.print_line_break()

    def print_line_break(self) -> None:
        self._console.print("")
        self._indented_line = False

    def _print_indentation(self) -> None:
        if not self._indented_line:
            self._console.print(self.current_indentation, end="")
            self._indented_line = True

    def _is_logging_enabled(self, level: int, global_fn: Callable[[], bool]) -> bool:
        match self._log_level:
            case LogLevel.GLOBAL:
                return global_fn()

            case _:
                return self._log_level.value <= level

    def print_info(self, msg: str) -> None:
        if self._is_logging_enabled(1, is_info_enabled):
            _print_message(msg, "green", "Info", self._console, "+" if self._output_for_github else None)

    def is_info_enabled(self) -> bool:
        return self._is_logging_enabled(1, is_info_enabled)

    def print_warn(self, msg: str) -> None:
        if self._is_logging_enabled(2, lambda: True):
            _print_message(msg, "yellow", "Warning", self._console, "!" if self._output_for_github else None)

    def print_error(self, msg: str) -> None:
        if self._is_logging_enabled(3, lambda: True):
            _print_message(msg, "red", "Error", self._console, "-" if self._output_for_github else None)

    def level_up(self) -> None:
        self._level += 1

    def level_down(self) -> None:
        if self._level == 0:
            raise RuntimeError("tried to call level_down on level 0")

        self._level -= 1


async def run_command(cmd: str, *args: str, **kwargs) -> tuple[int, str, str]:
    import asyncio

    process = await asyncio.create_subprocess_exec(
        cmd, *args, **kwargs, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")  # type: ignore


def jsonnet_evaluate_file(file: str) -> dict[str, Any]:
    import rjsonnet

    _logger.trace("evaluating jsonnet file '%s'", file)

    try:
        return json.loads(rjsonnet.evaluate_file(file))
    except Exception as ex:
        raise RuntimeError(f"failed to evaluate jsonnet file: {ex!s}") from ex


def jsonnet_evaluate_snippet(snippet: str) -> dict[str, Any]:
    import rjsonnet

    _logger.trace("evaluating jsonnet snippet '%s'", snippet)

    try:
        return json.loads(rjsonnet.evaluate_snippet("", snippet))
    except Exception as ex:
        raise RuntimeError(f"failed to evaluate snippet: {ex!s}") from ex


def get_or_default(namespace: Namespace, key: str, default: T) -> T:
    if namespace.__contains__(key):
        return namespace.__getattribute__(key)
    else:
        return default


def snake_to_camel_case(string: str) -> str:
    result = re.sub(r"[_\-]+", " ", string).title().replace(" ", "")
    return result[0].lower() + result[1:]


def snake_to_normal_case(string: str) -> str:
    result = re.sub(r"[_\-]+", " ", string).title()
    return result[0] + result[1:]


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


def parse_github_url(url: str) -> tuple[str, str]:
    pattern = re.compile(r"https://github.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)")
    m = pattern.match(url)
    if m is None:
        raise ValueError(f"unexpected GitHub url '{url}'")
    else:
        return m.group(1), m.group(2)


def is_ghsa_repo(repo_name: str) -> bool:
    """
    Returns True if the given repo_name is considered to be a repo created for a GitHub security advisory.

    Pattern: <regular repo name>-ghsa-xxxx-xxxx-xxxx
    """
    return re.match(".*-ghsa(-[23456789cfghjmpqrvwx]{4}){3}", repo_name) is not None


def strip_trailing_commas(lines: list[str]) -> list[str]:
    return [line.rstrip(",") for line in lines]


def sort_jsonnet(lines: list[str]) -> list[str]:
    ast: list[tuple[str, Any]] = []
    object_stack = [ast]

    for line in lines:
        trimmed_line = line.rstrip().rstrip(",")
        if trimmed_line.endswith(("{", "[")):
            current_node: list[tuple[str, Any]] = []
            object_stack[-1].append((line, current_node))
            object_stack.append(current_node)
        elif (trimmed_line.endswith("}") and "{" not in trimmed_line) or (
            trimmed_line.endswith("]") and "[" not in trimmed_line
        ):
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


class PrettyFormatter:
    def __init__(self, spaces_per_level: int = 2, key_align: int = -1):
        self.types: dict[str, Any] = {}
        self.htchar = " " * spaces_per_level
        self.lfchar = "\n"
        self.key_align = key_align
        self.indent = 0
        self.set_formatter(object, self.__class__._format_object)
        self.set_formatter(dict, self.__class__._format_dict)
        self.set_formatter(list, self.__class__._format_list)
        self.set_formatter(tuple, self.__class__._format_tuple)

    def set_formatter(self, obj, callback):
        self.types[obj] = callback

    def format(self, value, **args):
        for key in args:
            setattr(self, key, args[key])
        formatter = self.types[type(value) if type(value) in self.types else object]
        return formatter(self, value, self.indent)

    def _format_object(self, value, indent):
        if isinstance(value, str):
            if "\n" in value:
                return '"""\n' + value + '"""'

        return json.dumps(value, ensure_ascii=False)

    def _format_dict(self, value, indent):
        if len(value) == 0:
            return "{}"

        key_align = max(len(repr(x)) for x in value) + 1 if self.key_align == -1 else self.key_align

        items = [
            self.lfchar
            + self.htchar * (indent + 1)
            + repr(key).ljust(key_align)
            + ": "
            + (self.types[type(value[key]) if type(value[key]) in self.types else object])(self, value[key], indent + 1)
            for key in sorted(value)
        ]
        return "{%s}" % (",".join(items) + self.lfchar + self.htchar * indent)

    def _format_list(self, value, indent):
        items = [
            self.lfchar
            + self.htchar * (indent + 1)
            + (self.types[type(item) if type(item) in self.types else object])(self, item, indent + 1)
            for item in value
        ]
        if len(items) == 0:
            return "[]"
        else:
            return "[%s]" % (",".join(items) + self.lfchar + self.htchar * indent)

    def _format_tuple(self, value, indent):
        items = [
            self.lfchar
            + self.htchar * (indent + 1)
            + (self.types[type(item) if type(item) in self.types else object])(self, item, indent + 1)
            for item in value
        ]
        return "(%s)" % (",".join(items) + self.lfchar + self.htchar * indent)


def query_json(expr: str, data: Mapping[str, Any]) -> Any:
    """
    Evaluates a jsonata expression on the given dictionary.
    """
    from jsonata import Jsonata  # type: ignore

    return Jsonata.jsonata(expr).evaluate(data)


def deep_merge_dict(source: dict[str, Any], destination: dict[str, Any]):
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            deep_merge_dict(value, node)
        else:
            destination[key] = value

    return destination


def format_date_for_csv(iso_date_str: str) -> str:
    if iso_date_str is None:
        return ""
    date_obj = datetime.fromisoformat(iso_date_str)
    return date_obj.strftime("%d/%m/%Y %H:%M:%S")


def debug_times(category: str):
    import asyncio
    import functools

    def decorator_timed(func):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper_timed(*args, **kwargs):
                start = datetime.now()
                _logger.debug(f"{category}: starting ...")
                value = await func(*args, **kwargs)
                end = datetime.now()
                _logger.debug(f"{category}: complete after {(end - start).total_seconds()}s")
                return value

            return wrapper_timed
        else:

            @functools.wraps(func)
            def wrapper_timed(*args, **kwargs):
                start = datetime.now()
                _logger.debug(f"{category}: starting ...")
                value = func(*args, **kwargs)
                end = datetime.now()
                _logger.debug(f"{category}: complete after {(end - start).total_seconds()}s")
                return value

            return wrapper_timed

    return decorator_timed


def render_chevron(content: str, context: dict[str, Any]) -> str:
    import chevron

    # need to escape ${{ sequences as used at GitHub
    escaped_content = content.replace("${{", "$\\{\\{")
    output = chevron.render(escaped_content, context)
    return output.replace("$\\{\\{", "${{")
