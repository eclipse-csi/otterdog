#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Test the schemas of the actions policies of organizations and repositories."""

import json
from importlib.resources import as_file, files
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from otterdog import resources
from otterdog.utils import jsonnet_evaluate_snippet

_DEFAULTS = files("otterdog").joinpath("resources", "defaults", "otterdog-defaults.libsonnet")


def _validator(schema_name: str) -> Draft202012Validator:
    schemas = files(resources).joinpath("schemas")
    with as_file(schemas) as schema_dir:
        registry: Registry = Registry().with_resources(
            (path.name, Resource.from_contents(json.loads(path.read_text())))
            for path in schema_dir.iterdir()
            if path.name.endswith(".json")
        )
        return Draft202012Validator(json.loads((schema_dir / schema_name).read_text()), registry=registry)


def _policy(function: str, **overrides: Any) -> dict[str, Any]:
    data = jsonnet_evaluate_snippet(f"(import '{_DEFAULTS}').{function}('policy')")
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "schema,function",
    [("org-actions-policy.json", "newOrgActionsPolicy"), ("repo-actions-policy.json", "newRepoActionsPolicy")],
)
@pytest.mark.parametrize(
    "overrides,valid",
    [
        ({}, True),
        ({"allowed_actors": ["@alice", "#Write"], "allowed_events": ["push"]}, True),
        ({"allowed_actors": "@alice"}, False),
        ({"allowed_events": [1]}, False),
        ({"enforcement": "enforced"}, False),
        ({"include_workflows": None}, False),
        ({"unknown": True}, False),
    ],
    ids=[
        "defaults",
        "rules",
        "actors_not_a_list",
        "event_not_a_string",
        "unknown_enforcement",
        "null_workflows",
        "unknown",
    ],
)
def test_policy(schema: str, function: str, overrides: dict[str, Any], valid: bool):
    assert _validator(schema).is_valid(_policy(function, **overrides)) is valid


def test_repository_targets_are_only_supported_by_organization_policies():
    data = _policy("newRepoActionsPolicy", include_repo_names=["~ALL"])

    assert _validator("repo-actions-policy.json").is_valid(data) is False
    assert _validator("org-actions-policy.json").is_valid(data) is True
