#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The validation of the evaluated configurations with the schemas of otterdog, and by otterdog on the server."""

from pathlib import Path

import pytest

from .helpers import EDITOR, validated_by_otterdog

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


ORGANIZATION = """local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('website'),
    orgs.newRepo('api') {
      rulesets: [
        orgs.newRepoRuleset('main') {
          include_refs+: ['1.2.x'],
        },
      ],
    },
  ],
}"""
INCLUDE_REFS_ERROR = "has an invalid 'include_refs' pattern '1.2.x'"


def validate_button(playground):
    return playground.page.locator("#playground-validate")


def test_the_configuration_of_an_organization_is_validated_by_otterdog(playground):
    playground.open("example.html")
    page = playground.page
    urls = validated_by_otterdog(page)
    playground.type_code(ORGANIZATION)
    playground.wait_evaluated()

    # no schema problem, only otterdog knows the patterns allowed for the branches of a ruleset
    assert playground.note("problems") is None
    assert errors(playground) == []
    validate_button(playground).click()
    page.wait_for_function("document.querySelector('.playground-status-note[data-key=validation] a') !== null")

    assert urls == [playground.base_url + "/playground/validate?template=example"]
    assert "1 validation error" in playground.note("validation")
    # located at the invalid value of the property the problem is about
    assert errors(playground) == ["'1.2.x'"]
    page.click(".playground-status-note[data-key=validation] a")
    page.wait_for_selector(".cm-panel-lint li")
    (problem,) = page.locator(".cm-panel-lint li").all_inner_texts()
    assert 'repo_ruleset[name="main", repository=api] ' + INCLUDE_REFS_ERROR in problem


def test_the_limitations_of_the_validation_by_otterdog_are_shown(playground):
    playground.open("example.html")
    page = playground.page
    validated_by_otterdog(page)
    playground.type_code(ORGANIZATION.replace("'1.2.x'", "'refs/heads/1.2.x'"))
    playground.wait_evaluated()

    assert "Not checked: the members of the teams" in validate_button(playground).get_attribute("title")
    validate_button(playground).click()
    page.wait_for_function("document.querySelector('.playground-status-note[data-key=validation] .text-success')")

    # not "valid", as the pull request may still be rejected
    assert "no problem found by otterdog" in playground.note("validation")
    link = page.locator(".playground-status-note[data-key=validation] .playground-validation-limitations")
    assert "Not checked: the members of the teams" in link.get_attribute("title")
    assert link.get_attribute("target") == "_blank"
    url, section = link.get_attribute("href").split("#")
    assert url.endswith("/userguide/guides/troubleshooting/")
    # the section of the documentation detailing them
    troubleshooting = Path(__file__).parents[3] / "docs" / "userguide" / "guides" / "troubleshooting.md"
    assert section == "validation-in-the-playground"
    assert "\n## Validation in the Playground\n" in troubleshooting.read_text()


def test_the_unknown_properties_ignored_by_otterdog_are_reported(playground):
    playground.open("example.html")
    page = playground.page
    validated_by_otterdog(page)
    unknown = ORGANIZATION.replace("'1.2.x'", "'refs/heads/1.2.x'").replace(
        "orgs.newRepo('website')", "orgs.newRepo('website') { test: 'test' }"
    )
    playground.type_code(unknown)
    playground.wait_evaluated()
    assert "1 schema warning" in playground.note("problems")

    validate_button(playground).click()
    page.wait_for_function("document.querySelector('.playground-status-note[data-key=validation] a') !== null")

    assert "1 validation warning" in playground.note("validation")
    page.click(".playground-status-note[data-key=validation] a")
    page.wait_for_selector(".cm-panel-lint li")
    problems = page.locator(".cm-panel-lint li").all_inner_texts()
    assert any(
        "repositories[name=\"website\"] has the unknown property 'test', which otterdog ignores" in problem
        for problem in problems
    )
    assert warnings(playground) == ["test: 'test'"]


def test_the_validation_by_otterdog_only_applies_to_the_validated_content(playground):
    playground.open("example.html")
    page = playground.page
    validated_by_otterdog(page)
    playground.type_code(ORGANIZATION)
    playground.wait_evaluated()
    validate_button(playground).click()
    page.wait_for_function("document.querySelector('.playground-status-note[data-key=validation] a') !== null")

    playground.replace("'1.2.x'", "'refs/heads/1.2.x'")
    assert validate_button(playground).is_disabled()
    playground.wait_evaluated()

    assert playground.note("validation") is None
    assert errors(playground) == []
    validate_button(playground).click()
    page.wait_for_function("document.querySelector('.playground-status-note[data-key=validation] .text-success')")
    assert "no problem found by otterdog" in playground.note("validation")


@pytest.mark.parametrize(
    "code,reason",
    [
        (
            ORGANIZATION.replace("orgs.newRepo('website')", "orgs.newRepo('website') { has_wiki: 'yes' }"),
            "schema errors",
        ),
        (ORGANIZATION.replace("'1.2.x'", "'1.2.x' +"), "evaluated without error"),
    ],
    ids=["schema_errors", "evaluation_error"],
)
def test_a_configuration_is_not_validated_by_otterdog(playground, code, reason):
    playground.open("example.html")
    playground.type_code(code)
    playground.wait_evaluated()

    button = validate_button(playground)
    assert button.is_visible()
    assert button.is_disabled()
    assert reason in button.get_attribute("title")


def test_an_earlier_validation_by_otterdog_does_not_replace_a_later_one(playground):
    playground.open("example.html")
    page = playground.page
    # the requests are answered by the test, in another order
    requests = []
    page.route("**/playground/validate**", lambda route: requests.append(route))

    def wait_requests(count):
        while len(requests) < count:
            page.wait_for_timeout(50)

    playground.type_code(ORGANIZATION)
    playground.wait_evaluated()
    validate_button(playground).click()
    wait_requests(1)
    playground.replace("'1.2.x'", "'refs/heads/1.2.x'")
    playground.wait_evaluated()
    validate_button(playground).click()
    wait_requests(2)

    # the validation of the earlier content answers while the later one is pending
    requests[0].fulfill(json={"problems": [{"severity": "error", "message": "an earlier problem"}]})
    page.wait_for_timeout(300)
    assert "validating" in playground.note("validation")
    assert validate_button(playground).is_disabled()

    requests[1].fulfill(json={"problems": []})
    page.wait_for_function("document.querySelector('.playground-status-note[data-key=validation] .text-success')")
    assert "no problem found by otterdog" in playground.note("validation")
    assert errors(playground) == []
    assert not validate_button(playground).is_disabled()


def test_the_validation_by_otterdog_is_only_offered_for_an_organization(playground):
    # the snippet of the global playground is the configuration of an organization
    playground.open("example.html")
    playground.wait_evaluated()
    assert validate_button(playground).is_visible()
    assert not validate_button(playground).is_disabled()

    # a snippet creating a repository
    playground.type_code(VALID)
    playground.wait_evaluated()
    assert not validate_button(playground).is_visible()

    playground.type_code(ORGANIZATION)
    playground.wait_evaluated()
    assert validate_button(playground).is_visible()


def test_a_failed_validation_by_otterdog_is_reported(playground):
    playground.open("example.html")
    page = playground.page
    page.route("**/playground/validate**", lambda route: route.fulfill(status=500, body="Internal Server Error"))
    playground.type_code(ORGANIZATION)
    playground.wait_evaluated()

    validate_button(playground).click()
    page.wait_for_function("document.querySelector('.playground-status-note[data-key=validation] .text-danger')")

    assert "validation failed: the server answered with the status 500" in playground.note("validation")
    assert not validate_button(playground).is_disabled()
