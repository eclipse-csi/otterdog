# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from argparse import Namespace
from io import TextIOBase
from typing import Any, Callable, Literal, TypeVar

from colorama import init as colorama_init, Fore, Style


T = TypeVar("T")


# verbose levels
# 0: off
# 1: debug
# 2: trace
_verbose_level = 0


def init(verbose: int) -> None:
    global _verbose_level
    _verbose_level = verbose
    colorama_init()


def is_debug_enabled() -> bool:
    return _verbose_level >= 1


def print_debug(msg: str) -> None:
    if _verbose_level >= 1:
        print(f"{Fore.CYAN}[DEBUG]{Style.RESET_ALL} " + msg)


def print_trace(msg: str) -> None:
    if _verbose_level >= 2:
        print(f"{Fore.MAGENTA}[TRACE]{Style.RESET_ALL} " + msg)


def print_warn(msg: str) -> None:
    _print_message(msg, Fore.YELLOW, "Warning")


def print_error(msg: str) -> None:
    _print_message(msg, Fore.RED, "Error")


def _print_message(msg: str, color: str, level: str) -> None:
    print(f"{color}╷")

    lines = msg.splitlines()

    if len(lines) > 1:
        print(f"│ {level}:{Style.RESET_ALL} {Style.BRIGHT}{lines[0]}{Style.RESET_ALL}")
        print(f"{color}│{Style.RESET_ALL}")
        for line in lines[1:]:
            print(f"{color}│{Style.RESET_ALL}    {line}")
    else:
        print(f"│ {level}:{Style.RESET_ALL} {msg}")

    print(f"{color}╵{Style.RESET_ALL}")


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
    if type(value) != type(other_value):
        raise ValueError(f"'value types do not match: {type(value)}' != '{type(other_value)}'")

    if isinstance(value, dict):
        raise ValueError(f"dictionary values not supported")
    elif isinstance(value, list):
        sorted_value_list = sorted(value)
        sorted_other_list = sorted(other_value)

        if sorted_value_list != sorted_other_list:
            diff = _diff_list(sorted_value_list, sorted_other_list)
            return True, diff
    else:
        if value != other_value:
            return True, value

    # values are not different, no patch generated
    return False, None


def _diff_list(list1: list[T], list2: list[T]) -> list[T]:
    s = set(list2)
    return [x for x in list1 if x not in s]


def dump_patch_object_as_json(diff_object: dict[str, Any],
                              fp: TextIOBase,
                              offset=0,
                              indent=2,
                              close_object: bool = True) -> int:
    if close_object is True and len(diff_object) == 0:
        fp.write(",\n")
        return offset

    fp.write(" {\n")
    offset += indent

    for key, value in sorted(diff_object.items()):
        if is_unset(value):
            print_warn(f"key '{key}' defined in default configuration not present in config, skipping")
            continue

        fp.write(" " * offset)
        if isinstance(value, list):
            fp.write(f"{key}+: [\n")
            offset += indent
            for item in value:
                fp.write(" " * offset)
                fp.write(f"{json.dumps(item)},\n")
            offset -= indent
            fp.write(" " * offset)
            fp.write("],\n")
        else:
            fp.write(f"{key}: {json.dumps(value)},\n")

    if close_object is True:
        offset -= indent
        fp.write(" " * offset + "},\n")
        return offset
    else:
        return offset


def associate_by_key(input_list: list[T], key_func: Callable[[T], str]) -> dict[str, T]:
    result = {}
    for item in input_list:
        key = key_func(item)

        if key in result:
            raise RuntimeError(f"duplicate item found with key '{key}'")

        result[key] = item

    return result


class IndentingPrinter:
    def __init__(self, spaces_per_level: int = 2):
        self._level = 0
        self._spaces_per_level = spaces_per_level

    def print(self, text: str = '', end: str = '\n') -> None:
        lines = text.splitlines()
        if len(lines) > 0:
            for line in lines:
                print(" " * (self._level * self._spaces_per_level) + line, end=end)
        else:
            print(end=end)

    def print_warn(self, text: str) -> None:
        print_warn(text)

    def print_error(self, text: str) -> None:
        print_error(text)

    def level_up(self) -> None:
        self._level += 1

    def level_down(self) -> None:
        self._level -= 1
        assert self._level >= 0


def jsonnet_evaluate_file(file: str) -> dict[str, Any]:
    import _gojsonnet

    print_trace(f"evaluating jsonnet file {file}")

    try:
        return json.loads(_gojsonnet.evaluate_file(file))
    except Exception as ex:
        raise RuntimeError(f"failed to evaluate jsonnet file: {str(ex)}")


def jsonnet_evaluate_snippet(snippet: str) -> dict[str, Any]:
    import _gojsonnet

    print_trace(f"evaluating jsonnet snippet {snippet}")

    try:
        return json.loads(_gojsonnet.evaluate_snippet("", snippet))
    except Exception as ex:
        raise RuntimeError(f"failed to evaluate snippet: {str(ex)}")


def get_or_default(namespace: Namespace, key: str, default: Any) -> Any:
    if namespace.__contains__(key):
        return namespace.__getattribute__(key)
    else:
        return default
