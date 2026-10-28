#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest

from otterdog.utils import ExclusionPatterns


@pytest.mark.parametrize(
    "patterns,value,expected",
    [
        (["^external-.*", "^sync-.*"], "sync-team", True),
        (["^external-.*", "^sync-.*"], "staging", False),
        (["copilot"], "copilot-staging", True),
        (["^copilot$"], "copilot-staging", False),
        # a backreference refers to the group of its own pattern, not to one of a previous pattern
        (["^external-(dev|prod)$", r"^preview-(\d+)-\1$"], "preview-42-42", True),
        (["^external-(dev|prod)$", r"^preview-(\d+)-\1$"], "preview-42-43", False),
    ],
)
def test_patterns_are_matched_independently(patterns, value, expected):
    assert ExclusionPatterns(patterns).match(value) is expected


def test_pattern_lists_all_patterns():
    assert ExclusionPatterns(["a.*", "b.*"]).pattern == "a.*|b.*"
