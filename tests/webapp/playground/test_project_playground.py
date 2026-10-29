#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The playground of a project, starting with the current configuration of its organization."""

import json
import time

from .conftest import ORGANIZATION
from .helpers import EDITOR, encode, validated_by_otterdog


def changes(playground) -> str:
    return playground.page.locator("#playground-changes").inner_text()


def test_the_configuration_of_the_organization_is_shown(playground):
    playground.open("org.html")
    page = playground.page

    tabs = playground.tabs()
    assert len(tabs) == 1
    assert tabs[0]["label"] == "my-project"
    assert tabs[0]["active"]
    assert not tabs[0]["closable"]
    assert page.locator("#playground-propose").is_disabled(), "nothing to propose without changes"
    assert page.locator(".playground-example[data-organization]").get_attribute("aria-current") == "true"
    page.locator("#playground-changes-tab").click()
    assert "No change" in changes(playground)


def test_changes_are_proposed_on_github(playground):
    playground.open("org.html")
    page = playground.page
    playground.replace("has_wiki: true", "has_wiki: false")
    playground.wait_evaluated()
    content = playground.code()
    assert page.locator("#playground-changes-count").inner_text() == "1"

    propose = page.locator("#playground-propose")
    assert propose.is_enabled()
    urls = validated_by_otterdog(page)
    propose.click()
    page.wait_for_selector("#playground-propose-modal.show")
    # validated by otterdog first, without error
    assert urls == [playground.base_url + "/projects/my-project/playground/validate"]
    assert playground.copied == content + "\n", "copied with the final new line of the file"
    link = page.locator("#playground-propose-open")
    assert link.get_attribute("href") == "https://github.com/my-org/.otterdog/edit/main/otterdog/my-org.jsonnet"
    assert link.get_attribute("target") == "_blank"
    page.locator("#playground-propose-modal .btn-secondary").click()
    page.wait_for_timeout(400)

    playground.replace("has_wiki: false", "has_wiki: nope")
    playground.wait_evaluated()
    assert propose.is_disabled(), "no proposal of a configuration failing to evaluate"


def test_a_configuration_with_errors_is_only_proposed_once_confirmed(playground):
    playground.open("org.html")
    page = playground.page
    urls = validated_by_otterdog(page)
    playground.replace("allows_updates: false", "allows_updates: false, include_refs+: ['1.2.x']")
    playground.wait_evaluated()

    page.locator("#playground-propose").click()
    page.wait_for_selector("#playground-overwrite-modal.show")
    assert page.locator("#playground-overwrite-title").inner_text() == "Propose a configuration with errors?"
    assert page.locator("#playground-overwrite-message").inner_text() == (
        "Otterdog found 1 error in the configuration of my-project, underlined in it: "
        "the validation of its pull request will fail."
    )
    assert playground.marked("cm-lintRange-error") == ["'1.2.x'"]
    page.locator("#playground-overwrite-modal .btn-secondary").click()
    page.wait_for_timeout(400)
    assert playground.copied is None
    assert page.locator("#playground-propose-modal.show").count() == 0

    # the validation of the same content is not repeated
    page.locator("#playground-propose").click()
    page.wait_for_selector("#playground-overwrite-modal.show")
    page.locator("#playground-overwrite-confirm").click()
    page.wait_for_selector("#playground-propose-modal.show")
    assert playground.copied == playground.code() + "\n"
    assert len(urls) == 1


def test_a_configuration_not_validated_is_only_proposed_once_confirmed(playground):
    playground.open("org.html")
    page = playground.page
    page.route("**/playground/validate**", lambda route: route.fulfill(status=500, body="Internal Server Error"))
    playground.replace("has_wiki: true", "has_wiki: false")
    playground.wait_evaluated()

    page.locator("#playground-propose").click()
    page.wait_for_selector("#playground-overwrite-modal.show")

    assert page.locator("#playground-overwrite-message").inner_text() == (
        "The configuration of my-project has not been validated by otterdog. Its validation failed: "
        "the server answered with the status 500. The validation of its pull request may fail."
    )
    assert page.locator("#playground-overwrite-confirm").inner_text() == "Propose anyway"


def test_the_changes_of_the_configuration_are_shown_with_another_document(playground):
    playground.open("org.html")
    page = playground.page
    playground.replace("has_wiki: true", "has_wiki: false")
    playground.wait_evaluated()
    content = playground.code()

    page.locator(".playground-example").nth(6).click()
    playground.wait_evaluated()
    assert len(playground.tabs()) == 2
    assert playground.tabs()[0]["modified"]
    page.locator("#playground-changes-tab").click()
    assert "not to the shown document" in changes(playground)
    assert "has_wiki" in changes(playground)

    page.locator("#playground-changes a", has_text="Show the configuration").click()
    page.wait_for_timeout(300)
    assert playground.tabs()[0]["active"]
    assert playground.code() == content
    assert "not to the shown document" not in changes(playground)

    page.locator("#playground-output-tab").click()
    page.locator(".playground-example").nth(6).click()
    page.wait_for_timeout(300)
    page.locator(".playground-example[data-organization]").click()
    page.wait_for_timeout(300)
    assert playground.tabs()[0]["active"]


def test_changes_are_grouped_by_section_and_element(playground):
    playground.open("org.html")
    page = playground.page
    playground.type_code(
        ORGANIZATION.rstrip()
        .replace("settings+: { name: 'Org from the configuration' }", "settings+: { name: 'Org renamed' }")
        .replace("has_wiki: true,", "has_wiki: false,")
        .replace(
            "allows_updates: false }] },\n    orgs.newRepo('api')",
            "allows_updates: true, required_status_checks+: { status_checks: ['license-check'] } }] },\n"
            "    orgs.newRepo('api')",
        )
    )
    playground.wait_evaluated()
    page.locator("#playground-changes-tab").click()
    page.wait_for_timeout(200)

    sections = [" ".join(text.split()) for text in page.locator(".playground-changes-section-header").all_inner_texts()]
    assert sections == ["SETTINGS 1", "REPOSITORIES 3"]
    groups = [" ".join(text.split()) for text in page.locator(".playground-change-group > summary").all_inner_texts()]
    assert groups == ["~ website 3", "~ rulesets tags-protection 2"]
    rows = page.evaluate(
        """() => [...document.querySelectorAll('.playground-change-rows')].map((grid) =>
          [...grid.children].map((cell) => cell.textContent).join(' | '))"""
    )
    assert rows[0] == '~ | name | "Org from the configuration" → "Org renamed"'
    assert "~ | allows_updates | false → true" in rows[-1]
    assert "required_status_checks" in rows[-1]
    summary = " ".join(page.locator("#playground-changes > div").first.inner_text().split())
    assert "+ 1 added ~ 3 changed Expand all · Collapse all" in summary

    page.locator("#playground-changes a", has_text="Collapse all").click()
    assert page.evaluate("[...document.querySelectorAll('.playground-change-group')].every((group) => !group.open)")
    page.locator("#playground-changes a", has_text="Expand all").click()
    assert page.evaluate("[...document.querySelectorAll('.playground-change-group')].every((group) => group.open)")

    page.locator(".playground-change-group > summary", has_text="website").locator(".playground-change-show").click()
    page.wait_for_timeout(300)
    assert page.locator("#playground-output-tab").get_attribute("aria-selected") == "true"
    assert page.locator("#playground-output-view").input_value() == "repository:website"

    page.locator("#playground-reset").click()
    page.wait_for_selector("#playground-overwrite-modal.show")
    assert "current configuration of my-project" in page.locator("#playground-overwrite-message").inner_text()
    page.locator("#playground-overwrite-confirm").click()
    playground.wait_evaluated()
    assert page.locator("#playground-changes-count").is_hidden()


def test_a_snippet_of_a_link_is_shown_next_to_the_configuration(playground):
    snippet = "orgs.newOrg('my-project', 'my-org') {\n  settings+: { name: 'Shared' },\n}\n"
    playground.open("org.html", "#code=" + encode(snippet))

    tabs = playground.tabs()
    assert [tab["label"] for tab in tabs] == ["my-project", "playground.jsonnet"]
    assert tabs[1]["active"]
    assert '"Shared"' in playground.output()


def test_a_large_configuration_stays_responsive(playground):
    playground.open("large.html", timeout=60000)
    page = playground.page

    page.select_option("#playground-output-view", "section:settings")
    page.locator(".playground-example").nth(5).click()
    playground.wait_evaluated()
    evaluations = playground.evaluations
    page.locator(".playground-example[data-organization]").click()
    playground.wait_evaluated()
    assert playground.evaluations == evaluations, "shown again without evaluation"
    assert page.locator("#playground-output-view").input_value() == "section:settings"

    page.locator(f"{EDITOR} .cm-content").click()
    page.keyboard.press("Control+End")
    page.keyboard.type("\n// x")
    playground.wait_status("evaluating", timeout=5000)
    start = time.time()
    page.keyboard.type("y")
    assert time.time() - start < 0.5, "typing while evaluating"
    playground.wait_evaluated(timeout=60000)


def test_a_configuration_extending_the_default_configuration_is_completed(playground):
    playground.open("large.html", timeout=60000)
    page = playground.page
    # its values identical to the default configuration are highlighted
    page.wait_for_function(
        "document.querySelector('.playground-status-note[data-key=defaults]') !== null", timeout=15000
    )

    end = playground.code().index("orgs.newRepo('website') {") + len("orgs.newRepo('website') {")
    view = playground.view()
    page.evaluate(
        f"{view}.dispatch({{changes: {{from: {end}, insert: '\\n      has_'}}, selection: {{anchor: {end + 11}}}}}); {view}.focus()"
    )
    page.keyboard.type("w", delay=50)
    page.wait_for_selector(".cm-tooltip-autocomplete li", timeout=15000)

    labels = page.evaluate(
        "[...document.querySelectorAll('.cm-tooltip-autocomplete li .cm-completionLabel')].map((item) => item.textContent)"
    )
    assert labels == ["has_wiki"]


def test_the_examples_collapse_on_narrow_screens(playground):
    playground.open("org.html")
    page = playground.page
    page.set_viewport_size({"width": 900, "height": 1000})
    page.wait_for_timeout(300)

    page.locator("#playground-examples-toggle").click()
    page.wait_for_timeout(300)

    assert page.locator("#playground-examples-body").is_hidden()


def test_the_playground_of_a_project_is_opened_at_a_repository(playground):
    playground.open("org.html", "?repository=api")
    page = playground.page

    # the output shows the repository, the cursor is at the call creating it
    assert page.locator("#playground-output-view").input_value() == "repository:api"
    assert '"name": "api"' in playground.output()
    assert '"website"' not in playground.output()
    view = playground.view()
    selection = page.evaluate(
        f"{view}.state.sliceDoc({view}.state.selection.main.from, {view}.state.selection.main.to)"
    )
    assert selection == "orgs.newRepo('api')"
    assert playground.code().split("\n")[playground.cursor_line() - 1].strip().startswith("orgs.newRepo('api')")


def test_an_unknown_repository_opens_the_whole_configuration(playground):
    playground.open("org.html", "?repository=unknown")

    assert playground.page.locator("#playground-output-view").input_value() == ""
    assert playground.tabs()[0]["active"]


def test_playground_keeps_the_selected_custom_template_when_library_filenames_match(playground):
    """Opening the project must use its custom template and helper.

    The fixture's project imports vendor/custom/nested/otterdog-defaults.libsonnet.
    Another otterdog-defaults.libsonnet exists under nested/upstream/. The custom
    template sets the organization name from its own helper: 'Custom helper'.
    Seeing that value in the output confirms that the selected template was used.
    """
    playground.open("custom-local.html")

    assert "import 'vendor/custom/nested/otterdog-defaults.libsonnet'" in playground.code()
    assert json.loads(playground.output())["settings"]["name"] == "Custom helper"


def test_a_shared_snippet_uses_the_selected_custom_template_instead_of_its_upstream_library(playground):
    """A user opens a shared snippet whose template import belongs to another project.

    The URL's snippet imports vendor/documentation/otterdog-defaults.libsonnet,
    which is unavailable in this playground. The playground must adapt that
    import to the selected custom template, not its equally named upstream file.
    The resulting organization name 'Custom helper' comes from the custom helper.
    """
    shared_code = """local orgs = import 'vendor/documentation/otterdog-defaults.libsonnet';
orgs.newOrg('custom', 'custom')
"""
    shared_fragment = "#code=" + encode(shared_code)

    playground.open("custom-local.html", shared_fragment)

    assert "import 'vendor/custom/nested/otterdog-defaults.libsonnet'" in playground.code()
    assert json.loads(playground.output())["settings"]["name"] == "Custom helper"


def test_a_shared_snippet_from_a_nested_template_uses_the_selected_custom_template(playground):
    """A shared snippet imports a nested template from another project's repository.

    The unavailable import contains an extra 'templates/' directory. That source
    directory must not prevent adapting the import to this playground's selected
    template. The output name proves that the custom template and helper ran.
    """
    shared_code = """local orgs = import 'vendor/documentation/templates/otterdog-defaults.libsonnet';
orgs.newOrg('custom', 'custom')
"""
    shared_fragment = "#code=" + encode(shared_code)

    playground.open("custom-local.html", shared_fragment)

    assert "import 'vendor/custom/nested/otterdog-defaults.libsonnet'" in playground.code()
    assert json.loads(playground.output())["settings"]["name"] == "Custom helper"
