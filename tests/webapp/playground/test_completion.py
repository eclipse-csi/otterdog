#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The completion and the description of the functions and properties of the default configuration."""

import json

HEAD = "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n\norgs.newOrg('my-project', 'my-org') {\n"
REPOSITORY = HEAD + "  _repositories+:: [\n    orgs.newRepo('my-repo') {\n"
HINTS = """[...document.querySelectorAll('.cm-tooltip-autocomplete li')].map((item) => {
  const detail = item.querySelector('.cm-completionDetail')?.textContent ?? '';
  return item.querySelector('.cm-completionLabel').textContent + (detail === '' || detail.startsWith('(') ? '' : ' ') + detail;
})"""
TOOLTIP = ".playground-tooltip"


def complete(playground, code: str, typed: str) -> list[str]:
    """Replace the editor contents, type at the end, and read the suggestion menu.

    Installing the prefix directly keeps each test focused on the final keystroke
    that opens completion. The real browser handles that keystroke and shows the
    menu; the returned labels include parameter hints such as 'newRepo(name)'.
    """
    page = playground.page
    view = playground.view()
    page.evaluate(
        f"(code) => {{ {view}.dispatch({{changes: {{from: 0, to: {view}.state.doc.length, insert: code}},"
        f" selection: {{anchor: code.length}}}}); {view}.focus(); }}",
        code,
    )
    page.keyboard.type(typed, delay=30)
    page.wait_for_selector(".cm-tooltip-autocomplete li", timeout=10000)
    page.wait_for_timeout(300)
    return page.evaluate(HINTS)


def description(playground) -> str:
    return " | ".join(playground.page.locator(TOOLTIP).inner_text().split("\n"))


def test_functions_of_the_default_configuration_are_completed(playground):
    playground.open("example.html")
    page = playground.page

    hints = complete(playground, HEAD + "  _repositories+:: [\n    orgs.newR", "e")
    assert "newRepo(name)" in hints
    assert "newRepoRuleset(name)" in hints
    assert all(hint.startswith("newRe") for hint in hints)
    info = description(playground)
    assert "orgs.newRepo(name)" in info
    assert "Returns a new object with the values of the default configuration" in info
    assert page.locator(f"{TOOLTIP} a").get_attribute("href").endswith("reference/organization/repository/")

    # the link opens the reference in a new tab
    page.context.route("**/reference/organization/**", lambda route: route.fulfill(body="reference"))
    with page.expect_popup() as popup:
        page.locator(f"{TOOLTIP} a").click()
    assert popup.value.url.endswith("reference/organization/repository/")
    popup.value.close()

    page.evaluate(f"{playground.view()}.focus()")
    page.keyboard.press("Control+Space")
    page.wait_for_selector(".cm-tooltip-autocomplete li", timeout=10000)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.keyboard.type("my-repo")
    assert playground.code().endswith("orgs.newRepo('my-repo')")


def test_properties_are_completed_with_their_default_value(playground):
    playground.open("example.html")
    page = playground.page

    assert complete(playground, REPOSITORY + "      has_", "w") == ["has_wiki true"]
    info = description(playground)
    for part in ["has_wiki", "boolean", "If the repo has a wiki", "Default value: true", "Reference: Repository"]:
        assert part in info
    page.keyboard.press("Enter")
    assert playground.code().endswith("has_wiki: ")
    page.keyboard.type("t")
    page.wait_for_timeout(400)
    assert page.locator(".cm-tooltip-autocomplete").count() == 0, "no completion in a value"


def test_properties_of_nested_objects_and_of_functions_of_the_configuration_are_completed(playground):
    playground.open("example.html")
    page = playground.page

    hints = complete(playground, REPOSITORY + "      workflows+: {\n        ena", "b")
    assert any(hint.startswith("enabled") for hint in hints)
    assert "Reference: Workflow Settings" in description(playground)
    page.keyboard.press("Escape")

    # objects created in a function of the configuration, whose arguments are not known
    function = "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n\n"
    function += "local customRuleset(name) =\n  orgs.newRepoRuleset(name) {\n    allows_"
    assert complete(playground, function, "u") == ["allows_updates true"]
    assert "Reference: Repository Ruleset" in description(playground)
    page.keyboard.press("Escape")

    complete(playground, HEAD + "  setting", "s")
    page.keyboard.press("Enter")
    assert playground.code().endswith("settings+: {}"), "objects are extended"


def test_hovering_a_property_describes_it(playground):
    playground.open("example.html")
    page = playground.page
    playground.type_code(REPOSITORY + "      has_wiki: false,\n    },\n  ],\n}")
    playground.wait_evaluated()

    coords = page.evaluate(f"{playground.view()}.coordsAtPos({playground.view()}.state.doc.line(6).from + 8)")
    page.mouse.move(coords["left"] + 2, (coords["top"] + coords["bottom"]) / 2)
    page.wait_for_timeout(1000)
    assert "If the repo has a wiki" in page.locator(f".cm-tooltip-hover {TOOLTIP}").inner_text()

    # the mouse can reach the description, e.g. to follow its link
    link = page.locator(f"{TOOLTIP} a").bounding_box()
    page.mouse.move(link["x"] + 5, link["y"] + link["height"] / 2, steps=8)
    page.wait_for_timeout(600)
    assert page.locator(".cm-tooltip-hover").count() == 1
    assert page.locator(f"{TOOLTIP} a").get_attribute("href").endswith("reference/organization/repository/")
    page.mouse.move(5, 5)
    page.wait_for_timeout(700)
    assert page.locator(".cm-tooltip-hover").count() == 0


def test_completion_uses_the_custom_local_constructor_without_an_argument(playground):
    """The custom template fixes the repository name in a local function.

    Its upstream library defines newRepo(name). The selected template instead
    defines local newRepo() = upstream.newRepo('custom-repo') and exports it.
    After typing orgs.newRe, the user should get newRepo(), without an argument
    to fill in. Selecting it must produce a repository named 'custom-repo'.
    """
    playground.open("custom-local.html")
    code = "local orgs = import 'vendor/custom/nested/otterdog-defaults.libsonnet';\norgs.newR"

    hints = complete(playground, code, "e")
    playground.page.keyboard.press("Enter")
    playground.wait_evaluated()
    playground.wait_status("ok")

    assert hints == ["newRepo()"]
    assert playground.code().endswith("orgs.newRepo()")
    assert json.loads(playground.output())["name"] == "custom-repo"


def test_completion_uses_the_custom_method_constructor_without_an_argument(playground):
    """The custom template fixes the repository name in an object method.

    The template defines { newRepo(): upstream.newRepo('custom-repo') }, while
    the upstream library still defines newRepo(name). The parameter-name lookup
    can find the upstream 'name', but the method used by the user needs no argument.
    Selecting its completion must insert newRepo() and evaluate successfully.
    """
    playground.open("custom-method.html")
    code = "local orgs = import 'vendor/custom/nested/otterdog-defaults.libsonnet';\norgs.newR"

    hints = complete(playground, code, "e")
    playground.page.keyboard.press("Enter")
    playground.wait_evaluated()
    playground.wait_status("ok")

    assert hints == ["newRepo()"]
    assert playground.code().endswith("orgs.newRepo()")
    assert json.loads(playground.output())["name"] == "custom-repo"


def test_completion_uses_a_function_expression_without_an_argument(playground):
    """The template exports a function value that supplies the repository name.

    It defines { newRepo: function() upstream.newRepo('custom-repo') }. This is
    another way to define a constructor with no required arguments. Typing
    orgs.newRe and selecting its suggestion must insert orgs.newRepo() and
    produce the repository named by that function.
    """
    playground.open("custom-function.html")
    code = "local orgs = import 'vendor/custom/nested/otterdog-defaults.libsonnet';\norgs.newR"

    hints = complete(playground, code, "e")
    playground.page.keyboard.press("Enter")
    playground.wait_evaluated()
    playground.wait_status("ok")

    assert hints == ["newRepo()"]
    assert playground.code().endswith("orgs.newRepo()")
    assert json.loads(playground.output())["name"] == "custom-repo"


def test_completion_allows_the_default_repository_name_to_be_used(playground):
    """The constructor accepts a name but supplies a default when it is omitted.

    The template defines newRepo(name='custom-repo'). The user can call it
    without entering a name. Selecting the completion should insert newRepo()
    so evaluation uses 'custom-repo', rather than replacing the default with ''.
    """
    playground.open("custom-optional.html")
    code = "local orgs = import 'vendor/custom/nested/otterdog-defaults.libsonnet';\norgs.newR"

    hints = complete(playground, code, "e")
    playground.page.keyboard.press("Enter")
    playground.wait_evaluated()
    playground.wait_status("ok")

    assert hints == ["newRepo()"]
    assert playground.code().endswith("orgs.newRepo()")
    assert json.loads(playground.output())["name"] == "custom-repo"
