#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import logging
from typing import cast

from rich.box import Box
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

TRACE = logging.DEBUG - 5

# verbose levels
# 0: warning
# 1: info
# 2: debug
# 3: trace
_verbose_level = 0

CONSOLE_STDOUT = Console(
    theme=Theme(
        {
            "logging.level.error": "red",
            "logging.level.warning": "yellow",
            "logging.level.info": "green",
            "logging.level.debug": "cyan",
            "logging.level.trace": "magenta",
        }
    ),
    highlight=False,
)
CONSOLE_STDERR = Console(stderr=True)


class CustomLogger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)

        logging.addLevelName(TRACE, "TRACE")

    def trace(self, msg, *args, **kwargs):
        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)


logging.setLoggerClass(CustomLogger)


def init_logging(verbose: int, setup_python_logger: bool = True) -> None:
    global _verbose_level
    _verbose_level = verbose

    if verbose < 0:
        raise RuntimeError(f"negative verbose level not valid: {verbose}")

    show_time = False

    match verbose:
        case 0:
            level = logging.WARNING
        case 1:
            level = logging.INFO
        case 2:
            level = logging.DEBUG
        case 3:
            level = TRACE
        case _:
            level = TRACE
            show_time = True

    if setup_python_logger is True:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(message)s",
            datefmt="%X.%f",
            handlers=[
                RichHandler(
                    rich_tracebacks=True,
                    tracebacks_show_locals=True,
                    show_time=show_time,
                    omit_repeated_times=False,
                    console=CONSOLE_STDOUT,
                )
            ],
        )

    import otterdog

    logging.getLogger(otterdog.__name__).setLevel(level)


def get_logger(name: str) -> CustomLogger:
    return cast(CustomLogger, logging.getLogger(name))


def is_info_enabled() -> bool:
    return _verbose_level >= 1


def is_debug_enabled() -> bool:
    return _verbose_level >= 2


def is_trace_enabled() -> bool:
    return _verbose_level >= 3


def print_exception(exc: Exception) -> None:
    if is_debug_enabled():
        import asyncio

        from rich.traceback import Traceback

        def get_rich_tb(exception: Exception) -> Traceback:
            return Traceback.from_exception(
                type(exception),
                exception,
                exception.__traceback__,
                show_locals=is_trace_enabled(),
                suppress=[asyncio],
                width=None,
            )

        if isinstance(exc, ExceptionGroup):
            CONSOLE_STDERR.print(get_rich_tb(exc))
            for nested_exception in exc.exceptions:
                CONSOLE_STDERR.print(get_rich_tb(nested_exception))
        else:
            CONSOLE_STDERR.print(get_rich_tb(exc))
    else:
        if isinstance(exc, ExceptionGroup):
            for nested_exception in exc.exceptions:
                print_error(str(nested_exception))
        else:
            print_error(str(exc))


def print_info(msg: str, console: Console = CONSOLE_STDOUT) -> None:
    if is_info_enabled():
        _print_message(msg, "green", "Info", console)


def print_warn(msg: str, console: Console = CONSOLE_STDOUT) -> None:
    _print_message(msg, "yellow", "Warning", console)


def print_error(msg: str, console: Console = CONSOLE_STDOUT) -> None:
    _print_message(msg, "red", "Error", console)


# fmt: off
_DEFAULT_BOX: Box = Box(
    "╷   \n"
    "│   \n"
    "│   \n"
    "│   \n"
    "│   \n"
    "│   \n"
    "│   \n"
    "╵   \n",
    ascii=False,
)
# fmt: on


def _print_message(msg: str, color: str, level: str, console: Console, custom_prefix: str | None = None) -> None:
    from rich.table import Table

    if custom_prefix is not None:
        # fmt: off
        custom_box: Box = Box(
            f"{custom_prefix}   \n"
            f"{custom_prefix}   \n"
            f"{custom_prefix}   \n"
            f"{custom_prefix}   \n"
            f"{custom_prefix}   \n"
            f"{custom_prefix}   \n"
            f"{custom_prefix}   \n"
            f"{custom_prefix}   \n",
            ascii=True,
        )
        box = custom_box
    else:
        box = _DEFAULT_BOX

    table = Table(show_header=False, show_footer=False, show_lines=False, box=box, border_style=color)
    table.add_column("severity", justify="left", style=color)
    table.add_column("message", justify="left", no_wrap=False)
    table.add_row(level + ":", msg)
    console.print(table)
