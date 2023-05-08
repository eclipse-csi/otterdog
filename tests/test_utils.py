# ****************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from otterdog.utils import *


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
