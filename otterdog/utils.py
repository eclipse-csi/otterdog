# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
import sys
from typing import Any, Callable

from colorama import init as colorama_init, Fore, Style

# verbose levels
# 0: off
# 1: info
# 2: debug
# 3: trace
_verbose_level = 0


def init(verbose: int) -> None:
    global _verbose_level
    _verbose_level = verbose
    colorama_init()


def is_debug_enabled() -> bool:
    return _verbose_level >= 2


def print_info(msg: str) -> None:
    if _verbose_level >= 1:
        print(f"{Fore.GREEN}[INFO]{Style.RESET_ALL} " + msg)


def print_debug(msg: str) -> None:
    if _verbose_level >= 2:
        print(f"{Fore.CYAN}[DEBUG]{Style.RESET_ALL} " + msg)


def print_trace(msg: str) -> None:
    if _verbose_level >= 3:
        print(f"{Fore.MAGENTA}[TRACE]{Style.RESET_ALL} " + msg)


def print_warn(msg: str) -> None:
    print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} " + msg)


def print_err(msg: str) -> None:
    print(f"{Fore.RED}[ERR]{Style.RESET_ALL} " + msg)


def exit_with_message(msg: str, code: int) -> None:
    print_err(msg)
    sys.exit(code)


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
            else:
                result[key] = current_value

    return result


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
                fp.write(f"{k}: [\n")
                offset += indent
                for item in v:
                    fp.write(" " * offset)
                    fp.write(f"{json.dumps(item)},\n")
                offset -= indent
                fp.write(" " * offset)
                fp.write("]\n")
            else:
                fp.write(f"{k}: {json.dumps(v)},\n")

    offset -= indent
    fp.write(" " * offset + "},\n")


def associate_by_key(input_list: list[dict[str, Any]], key_func: Callable[[Any], str]) -> dict[str, dict[str, Any]]:
    result = {}
    for item in input_list:
        value = key_func(item)

        if value in result:
            exit_with_message(f"duplicate item found with key '{value}'", 1)

        result[value] = item

    return result
