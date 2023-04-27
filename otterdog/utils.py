# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Any, Callable
from argparse import Namespace

from colorama import init as colorama_init, Fore, Style

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


def get_diff_from_defaults(obj: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    result = {}

    for key, default_value in sorted(defaults.items()):
        if key not in obj:
            continue

        current_value = obj[key]
        if current_value != default_value:
            if isinstance(current_value, dict):
                nested_result = get_diff_from_defaults(current_value, default_value)
                result[key] = nested_result
            elif isinstance(current_value, list):
                combined_list = current_value + default_value
                if len(combined_list) == 0:
                    result[key] = current_value
                elif isinstance(combined_list[0], str):
                    diff = diff_list(current_value, default_value)
                    result[key] = diff
                else:
                    result[key] = current_value
            else:
                result[key] = current_value

    return result


def diff_list(list1: list[Any], list2: list[Any]) -> list[Any]:
    s = set(list2)
    return [x for x in list1 if x not in s]


def dump_json_object(obj: Any, fp, offset=0, indent=2, embedded_object: bool = False,
                     predicate: Callable[[str], bool] = lambda x: False,
                     func: Callable[[str, Any, int], None] = lambda x, y: False):
    if not embedded_object:
        fp.write(" " * offset)
    fp.write("{\n")

    offset += indent
    for k, v in sorted(obj.items()):
        fp.write(" " * offset)
        if predicate(k):
            func(k, v, offset)
        else:
            if isinstance(v, dict):
                fp.write(f"{k}+: ")
                dump_json_object(v, fp, offset, indent, True)
            elif isinstance(v, list):
                fp.write(f"{k}+: [\n")
                offset += indent
                for item in v:
                    fp.write(" " * offset)
                    fp.write(f"{json.dumps(item)},\n")
                offset -= indent
                fp.write(" " * offset)
                fp.write("],\n")
            else:
                fp.write(f"{k}: {json.dumps(v)},\n")

    offset -= indent
    fp.write(" " * offset + "},\n")


def associate_by_key(input_list: list[dict[str, Any]], key_func: Callable[[Any], str]) -> dict[str, dict[str, Any]]:
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
