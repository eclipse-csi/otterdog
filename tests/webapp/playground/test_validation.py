#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The validation of the evaluated configurations with the schemas of otterdog."""

import pytest

from .helpers import EDITOR

RULESET = """local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newRepo('myrepo') {
  has_issues: false,
  rulesets: [
    orgs.newRepoRuleset('main') {
      required_pull_request+: {
        required_approving_review_count: "0",
      },
    },
  ],
}"""
VALID = RULESET.replace('"0"', "0")


def errors(playground) -> list[str]:
    return playground.marked("cm-lintRange-error")


def warnings(playground) -> list[str]:
    return playground.marked("cm-lintRange-warning")


def listed_problems(playground) -> list[str]:
    page = playground.page
    page.click(".playground-status-note[data-key=problems] a")
    page.wait_for_selector(".cm-panel-lint li")
    return page.locator(".cm-panel-lint li").all_inner_texts()


def test_a_value_of_a_wrong_type_is_reported(playground):
    playground.open("example.html")
    page = playground.page
    assert playground.note("problems") is None

    playground.type_code(RULESET)
    playground.wait_evaluated()

    assert errors(playground) == ['required_approving_review_count: "0"']
    assert page.locator(f"{EDITOR} .cm-lint-marker-error").count() == 1
    assert "1 schema error" in playground.note("problems")
    problems = listed_problems(playground)
    assert len(problems) == 1
    assert 'required_approving_review_count: "0" is not of type integer' in problems[0]
    page.locator(".cm-panel-lint li").first.click()
    page.keyboard.press("Enter")
    page.wait_for_timeout(200)
    assert playground.cursor_line() == 8
    page.keyboard.press("Escape")

    box = page.locator(f"{EDITOR} .cm-lintRange-error").first.bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + box["height"] / 2)
    page.wait_for_selector(".cm-tooltip-lint", timeout=5000)
    assert "is not of type integer" in page.locator(".cm-tooltip-lint").inner_text()


@pytest.mark.parametrize(
    "code,error,warning,note",
    [
        (
            VALID.replace("has_issues: false,", "has_issues: false,\n  has_wikki: true,"),
            [],
            ["has_wikki: true"],
            "1 schema warning",
        ),
        (
            VALID.replace(
                "has_issues: false,", "has_issues: false,\n  code_scanning_default_languages: ['python', 'truc'],"
            ),
            ["code_scanning_default_languages: ['python', 'truc']"],
            [],
            "1 schema error",
        ),
        # a missing property is reported at the call creating the object
        (
            (
                "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n\n"
                "orgs.newRepo('myrepo') {\n  name:: 'myrepo',\n}"
            ),
            ["orgs.newRepo"],
            [],
            "1 schema error",
        ),
    ],
    ids=["unknown_property", "value_not_allowed", "missing_property"],
)
def test_problems_are_reported(playground, code, error, warning, note):
    playground.open("example.html")
    playground.type_code(code)
    playground.wait_evaluated()

    assert errors(playground) == error
    assert warnings(playground) == warning
    assert note in playground.note("problems")


@pytest.mark.parametrize(
    "code",
    [
        VALID,
        RULESET.replace('"0"', '"0" +'),
        "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n\n{ a: orgs.newRepo('x') { has_wiki: 1 } }",
    ],
    ids=["valid", "evaluation_error", "not_a_call_of_the_default_configuration"],
)
def test_no_problem_is_reported(playground, code):
    playground.open("example.html")
    playground.type_code(RULESET)
    playground.wait_evaluated()

    playground.type_code(code)
    playground.wait_evaluated()

    assert playground.note("problems") is None
    assert warnings(playground) == []


def test_the_examples_are_valid(playground):
    playground.open("example.html")
    invalid = []
    for button in playground.examples().all():
        button.click()
        playground.wait_evaluated()
        if playground.note("problems") is not None:
            invalid.append((button.inner_text().strip(), playground.note("problems")))

    assert invalid == []


def test_a_problem_is_located_at_its_value_in_a_large_configuration(playground):
    playground.open("large.html", timeout=60000)
    assert playground.note("problems") is None

    playground.replace("    web_commit_signoff_required: false,", '    web_commit_signoff_required: "yes",')
    playground.wait_evaluated(timeout=60000)

    assert "1 schema error" in playground.note("problems")
    problems = listed_problems(playground)
    assert len(problems) == 1
    assert 'settings.web_commit_signoff_required: "yes" is not of type boolean' in problems[0]
    playground.page.locator(".cm-panel-lint li").first.click()
    playground.page.keyboard.press("Enter")
    playground.page.wait_for_timeout(200)
    # at the property of the settings, not at the property of the same name of a repository
    lines = playground.code().split("\n")
    assert lines[playground.cursor_line() - 1] == '    web_commit_signoff_required: "yes",'
