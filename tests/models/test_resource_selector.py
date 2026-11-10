#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from pathlib import Path

import pytest

from otterdog.models import ResourceSelector, matches_delete_filter
from otterdog.models.github_organization import GitHubOrganization


@pytest.fixture
def org() -> GitHubOrganization:
    data = json.loads((Path(__file__).parent / "resources" / "otterdogtest.json").read_text(encoding="utf-8"))
    data["project_name"] = "test-project"
    data["variables"] = [{"name": "ORG_VARIABLE", "value": "org", "visibility": "public", "selected_repositories": []}]
    data["repositories"][0]["variables"] = [{"name": "REPO_VARIABLE", "value": "repo"}]
    return GitHubOrganization.from_model_data(data)


@pytest.mark.parametrize(
    ("selector", "model_object_name", "conditions"),
    [
        ("org_code_security_configuration", "org_code_security_configuration", ()),
        ("org_*", "org_*", ()),
        # as displayed by plan
        (
            'org_code_security_configuration[name="Legacy - private/internal repositories"]',
            "org_code_security_configuration",
            (("name", "Legacy - private/internal repositories"),),
        ),
        ("org_code_security_configuration[name=Legacy*]", "org_code_security_configuration", (("name", "Legacy*"),)),
        (
            'branch_protection_rule[pattern="master", repository=jiro]',
            "branch_protection_rule",
            (("pattern", "master"), ("repository", "jiro")),
        ),
        # a quoted value can contain commas and brackets
        ('org_variable[ name = "a, [b]" ]', "org_variable", (("name", "a, [b]"),)),
        ("  org_variable  ", "org_variable", ()),
        ('org_variable[name="a]"]', "org_variable", (("name", "a]"),)),
        ("org_variable[name=a=b]", "org_variable", (("name", "a=b"),)),
        ('org_variable[name="", repository = my-repo ]', "org_variable", (("name", ""), ("repository", "my-repo"))),
    ],
)
def test_parse(selector, model_object_name, conditions):
    parsed = ResourceSelector.parse(selector)

    assert parsed.model_object_name == model_object_name
    assert parsed.conditions == conditions
    assert str(parsed) == selector


@pytest.mark.parametrize(
    "selector",
    [
        "",
        "   ",
        "org variable",
        "org_variable]",
        "[name=a]",
        "org_variable[]",
        "org_variable[name]",
        "org_variable[=a]",
        "org_variable[name=a",
        "org_variable[name=a]x",
        "org_variable[name=a,]",
        'org_variable[name="a]',
        'org_variable[name="a" b]',
        'org_variable[name=a"b]',
    ],
)
def test_parse_rejects_invalid_selectors(selector):
    with pytest.raises(ValueError, match="invalid resource selector"):
        ResourceSelector.parse(selector)


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ("org_variable", True),
        ("org_*", True),
        ("org_variable[name=ORG_VARIABLE]", True),
        ('org_variable[name="ORG_*"]', True),
        ("org_variable[name=OTHER]", False),
        # the type and the values are matched as a whole, with their case
        ("org_var", False),
        ("org_variable[name=org_variable]", False),
        # not the key of the resource
        ("org_variable[value=org]", False),
        ("repo_variable", False),
    ],
)
def test_matches_a_resource(org, selector, expected):
    assert ResourceSelector.parse(selector).matches(org.variables[0]) is expected


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ("repo_variable[repository=.eclipsefdn-private]", True),
        ('repo_variable[name="REPO_VARIABLE", repository=".eclipsefdn-*"]', True),
        ("repo_variable[repository=other]", False),
        # the parent is named by its type
        ("repo_variable[name=.eclipsefdn-private]", False),
    ],
)
def test_matches_a_resource_by_the_key_of_its_parent(org, selector, expected):
    repository = org.repositories[0]

    assert ResourceSelector.parse(selector).matches(repository.variables[0], repository) is expected


def test_empty_delete_filter_matches_all_resources(org):
    assert matches_delete_filter(org.variables[0], None, ()) is True
    assert matches_delete_filter(org.variables[0], None, (ResourceSelector.parse("repo_*"),)) is False
    assert (
        matches_delete_filter(
            org.variables[0], None, (ResourceSelector.parse("repo_*"), ResourceSelector.parse("org_*"))
        )
        is True
    )
