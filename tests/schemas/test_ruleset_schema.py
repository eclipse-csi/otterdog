#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Test the pull_request definition of ruleset.json."""

import json
from importlib.resources import files

import pytest
from jsonschema import Draft202012Validator

from otterdog import resources


class TestPullRequestSchema:
    @pytest.fixture
    def validator(self):
        schema = json.loads(files(resources).joinpath("schemas/ruleset.json").read_text())
        return Draft202012Validator(schema["$defs"]["pull_request"])

    @pytest.mark.parametrize(
        "allowed_merge_methods,valid",
        [
            (["merge"], True),
            (["merge", "squash", "rebase"], True),
            ([], False),
            (["merge", "merge"], False),
            (["fast-forward"], False),
        ],
        ids=["single_method", "all_methods", "empty_list", "duplicate_method", "unknown_method"],
    )
    def test_allowed_merge_methods(self, validator, allowed_merge_methods, valid):
        data = {"required_approving_review_count": 0, "allowed_merge_methods": allowed_merge_methods}

        assert validator.is_valid(data) is valid
