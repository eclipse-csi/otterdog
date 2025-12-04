#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from io import StringIO

import pytest

from otterdog.utils import (
    UNSET,
    IndentingPrinter,
    camel_to_snake_case,
    deep_merge_dict,
    format_date_for_csv,
    is_different_ignoring_order,
    is_ghsa_repo,
    parse_template_url,
    patch_to_other,
    snake_to_camel_case,
    snake_to_normal_case,
)


def test_is_different_ignoring_order():
    assert is_different_ignoring_order(1, 2) is True
    assert is_different_ignoring_order(None, None) is False
    assert is_different_ignoring_order(1, None) is True
    assert is_different_ignoring_order(None, 1) is True

    assert is_different_ignoring_order([], []) is False
    assert is_different_ignoring_order([1], [1]) is False
    assert is_different_ignoring_order([1, 2], [2, 1]) is False
    assert is_different_ignoring_order(["Hello"], ["World"]) is True
    assert is_different_ignoring_order(["Hello", "World"], ["World", "Hello"]) is False

    assert is_different_ignoring_order({"a": 1}, {"a": 1}) is False
    assert is_different_ignoring_order({"a": 1}, {"b": 1}) is True
    assert is_different_ignoring_order({"a": 1, "b": 2}, {"b": 2, "a": 1}) is False

    assert is_different_ignoring_order({"a"}, {"a"}) is False
    assert is_different_ignoring_order({"a", "b"}, {"b", "a"}) is False

    assert is_different_ignoring_order(UNSET, UNSET) is False
    assert is_different_ignoring_order(1, UNSET) is True


def test_patch_to_other():
    assert patch_to_other(1, 1) == (False, None)
    assert patch_to_other(1, 2) == (True, 1)

    assert patch_to_other([1], [1]) == (False, None)
    assert patch_to_other([1, 2], [1]) == (True, [2])
    assert patch_to_other([1, 2], [2, 1]) == (False, None)


def test_snake_to_camel_case():
    assert snake_to_camel_case("name") == "name"
    assert snake_to_camel_case("required_status_checks") == "requiredStatusChecks"
    assert snake_to_camel_case("required__status_checks") == "requiredStatusChecks"


def test_snake_to_normal_case():
    assert snake_to_normal_case("name") == "Name"
    assert snake_to_normal_case("required_status_checks") == "Required Status Checks"
    assert snake_to_normal_case("required__status_checks") == "Required Status Checks"


def test_camel_to_snake_case():
    assert camel_to_snake_case("name") == "name"
    assert camel_to_snake_case("requiredStatusChecks") == "required_status_checks"
    assert camel_to_snake_case("RequiredStatusChecks") == "required_status_checks"
    assert camel_to_snake_case("someXYZ") == "some_xyz"


def test_parse_template_url():
    assert parse_template_url("https://github.com/EclipseFdn/otterdog-defaults#otterdog-defaults.libsonnet@main") == (
        "https://github.com/EclipseFdn/otterdog-defaults",
        "otterdog-defaults.libsonnet",
        "main",
    )

    with pytest.raises(ValueError):
        assert parse_template_url("https://github.com/EclipseFdn/otterdog-defaults#otterdog-defaults.libsonnet")

    with pytest.raises(ValueError):
        parse_template_url("https://github.com/EclipseFdn/otterdog-defaults")


def test_is_ghsa_repo():
    assert is_ghsa_repo("name") is False
    assert is_ghsa_repo("name-wqjm-x66q-r2c6") is False
    assert is_ghsa_repo("jiro-ghsa-wqjm-x66q-r2c6") is True


def test_deep_merge_dict():
    src = {
        "first": {"Matt": 10, "Arnie": 2},
        "second": {"Peter": 2},
    }
    dst = {
        "first": {"Matt": 1},
        "third": {"Maria": 3},
    }

    assert deep_merge_dict(src, dst) == {
        "first": {"Matt": 10, "Arnie": 2},
        "second": {"Peter": 2},
        "third": {"Maria": 3},
    }


def test_format_date_for_csv():
    # Expected inputs are None or valid ISO 8601 Zulu timestamps
    assert format_date_for_csv(None) == ""

    assert format_date_for_csv("2024-03-15T14:30:45Z") == "2024-03-15 14:30:45"
    assert format_date_for_csv("2023-01-01T00:00:00Z") == "2023-01-01 00:00:00"
    assert format_date_for_csv("2023-12-31T23:59:59Z") == "2023-12-31 23:59:59"


_long_string = "Too long to fit console width"


@pytest.mark.parametrize(
    "method,long_string,soft_wrap,expected_newlines",
    [
        ("print", _long_string, False, 1),
        ("print", _long_string, True, 0),
        ("print", _long_string + "\n", False, 2),
        ("print", _long_string + "\n", True, 1),
        ("println", _long_string, False, 2),
        ("println", _long_string, True, 1),
        ("print", _long_string, None, 1),
        ("println", _long_string, None, 2),
    ],
)
def test_print_with_soft_wrap(method, long_string, soft_wrap, expected_newlines):
    # Create printer with console width that is narrower than the input string
    captured_output = StringIO()
    printer = IndentingPrinter(captured_output)
    printer._console.width = 20

    # Call `print` or `println` with default or passed soft_wrap
    print_method = getattr(printer, method)
    if soft_wrap is None:
        print_method(long_string)
    else:
        print_method(long_string, soft_wrap=soft_wrap)

    # Assert newline count in captured output
    assert captured_output.getvalue().count("\n") == expected_newlines
