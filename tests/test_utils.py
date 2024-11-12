#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest

from otterdog.utils import (
    UNSET,
    camel_to_snake_case,
    deep_merge_dict,
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
