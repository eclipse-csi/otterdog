#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import unittest
from io import StringIO
from unittest.mock import patch

from parameterized import parameterized  # type: ignore

from otterdog.operations import Operation
from otterdog.utils import Change, IndentingPrinter, LogLevel


class OperationTest(unittest.TestCase):
    # fmt: off
    @parameterized.expand(
        [
            (
                {"A": Change("1", "2"),
                 "B": Change("Hello", "World")},
                '~  {'
                '  ~ A = "1" -> "2"'
                '  ~ B = "Hello" -> "World"'
                '~ }'),
            (
                {"A": Change([1, 2], [3]),
                 "B": Change(3, 4)},
                '~  {'
                '  ~ A = ['
                '    ~ 1 -> 3'
                '    - 2'
                '  ~ ]'
                '  ~ B = 3 -> 4'
                '~ }',
            ),
            (
                {"A": Change({"B": [1, 2]}, {"B": [3]})},
                '~  {'
                '  ~ A   = {'
                '    ~ B   = ['
                '      ~ 1 -> 3'
                '      - 2'
                '    ~ ]'
                '  ~ }'
                '~ }',
            ),
        ]
    )
    # fmt: on
    @patch.multiple(Operation, __abstractmethods__=set())
    def test_print_modified_dict(self, test_input, expected: str):
        operation = Operation()  # type: ignore

        output = StringIO()
        printer = IndentingPrinter(output, log_level=LogLevel.ERROR)
        operation.init(None, printer)  # type: ignore

        operation.print_modified_dict(test_input, "", False)

        assert _strip_string(output.getvalue()) == expected


def _strip_string(input_string: str) -> str:
    return _remove_lf(_remove_ansi_color_codes(input_string))


def _remove_ansi_color_codes(input_string: str) -> str:
    import re

    # 7-bit and 8-bit C1 ANSI sequences
    ansi_escape_8bit = re.compile(r"\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~]")
    return ansi_escape_8bit.sub("", input_string)


def _remove_lf(input_string: str) -> str:
    return input_string.replace("\n", "")
