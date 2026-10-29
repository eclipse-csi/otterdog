#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The documents of the global playground, its files of the default configuration, its output and its controls."""

from otterdog.webapp.home import routes

from .helpers import EDITOR, decode

CATALOG = routes._playground_examples()
FUNCTIONS = "otterdog-functions.libsonnet"
IMPORT = "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n\n"
TWO_REPOSITORIES = (
    IMPORT + "orgs.newOrg('p', 'o') {\n  _repositories+:: [\n"
    "    orgs.newRepo('alpha') { has_wiki: false },\n    orgs.newRepo('beta'),\n  ],\n}"
)


def example(playground, page: int, index: int):
    return playground.page.locator(f'.playground-example[data-page="{page}"][data-example="{index}"]')


def test_the_snippet_is_evaluated(playground):
    playground.open("index.html")

    assert playground.tabs() == [
        {"label": "playground.jsonnet", "active": True, "preview": False, "modified": False, "closable": False}
    ]
    assert playground.page.locator("#playground-propose").count() == 0
    assert '"myrepo"' in playground.output()
    assert playground.examples().count() == sum(len(page["examples"]) for page in CATALOG)


def test_the_files_of_the_default_configuration_are_shown(playground):
    playground.open("example.html")
    page = playground.page

    page.locator("#playground-files-toggle").click()
    items = [" ".join(item.split()) for item in page.locator(".playground-file-item").all_inner_texts()]
    assert items == [
        "otterdog-defaults.libsonnet imported by the playground",
        f"{FUNCTIONS} imported by otterdog-defaults.libsonnet",
    ]
    page.keyboard.press("Escape")

    playground.open_file(FUNCTIONS)
    pane = playground.file_editor(FUNCTIONS)
    assert playground.shown_file().endswith(FUNCTIONS)
    assert page.locator("#playground-files-label").inner_text() == FUNCTIONS
    assert not any(tab["active"] for tab in playground.tabs())
    assert page.evaluate(f"{playground.view(pane)}.state.readOnly")
    assert page.evaluate(f"{playground.view(pane)}.scrollDOM.clientHeight") > 300
    info = " ".join(page.locator(".tab-pane.active .border-bottom").first.inner_text().split())
    assert "read-only" in info
    assert "imported by otterdog-defaults.libsonnet" in info
    assert page.locator(f".tab-pane.active a[href$='/{FUNCTIONS}']").count() == 1

    playground.tab("playground.jsonnet").locator(".nav-link").click()
    assert playground.shown_file() == "playground.jsonnet"
    assert playground.tabs()[0]["active"]
    assert page.locator("#playground-files-label").inner_text() == "Default configuration"


def test_changes_are_evaluated_once_typing_pauses(playground):
    playground.open("index.html")
    page = playground.page
    page.wait_for_timeout(300)
    evaluations = playground.evaluations

    page.locator(f"{EDITOR} .cm-content").click()
    page.keyboard.press("Control+End")
    page.keyboard.type("\n// a comment typed quickly", delay=20)
    assert playground.evaluations == evaluations
    playground.wait_evaluated()

    assert playground.evaluations == evaluations + 1
    assert playground.tabs()[0]["modified"]
    assert page.locator("#playground-reset").is_enabled()


def test_errors_are_located_in_the_files(playground):
    playground.open("index.html")
    page = playground.page

    playground.type_code(IMPORT + "orgs.newOrg('p', 'o') {\n  settings+: {\n    name: unknown,\n  },\n}")
    playground.wait_evaluated()
    assert playground.status == "Error at line 5"
    assert playground.line_at(f"{EDITOR} .cm-lintRange-error") == 5
    assert page.locator(f"{EDITOR} .cm-lint-marker-error").count() == 1
    assert page.locator("#playground-files-toggle .playground-files-error").is_hidden()

    # an error in a file of the default configuration, e.g. a missing argument
    playground.type_code(IMPORT + "orgs.newOrg('p', 'o') {\n  _repositories+:: [\n    orgs.newRepo(),\n  ],\n}")
    playground.wait_evaluated()
    assert page.locator("#playground-files-toggle .playground-files-error").is_visible()
    link = page.locator("#playground-error a", has_text=".libsonnet:").first
    filename, line = link.inner_text().split(":")[:2]
    link.click()
    page.wait_for_timeout(200)
    assert playground.shown_file().endswith(filename.split("/")[-1])
    assert playground.cursor_line(playground.file_editor(filename.split("/")[-1])) == int(line)
    assert page.locator(".tab-pane.active .cm-lintRange-error").count() >= 1

    playground.tab("playground.jsonnet").locator(".nav-link").click()
    playground.type_code(TWO_REPOSITORIES)
    playground.wait_evaluated()
    playground.open_file(filename.split("/")[-1])
    assert (
        page.locator(".tab-pane[data-file] .cm-lintRange-error, .tab-pane[data-file] .cm-lint-marker-error").count()
        == 0
    )
    assert page.locator("#playground-files-toggle .playground-files-error").is_hidden()


def test_the_output_shows_a_section_or_a_repository_and_finds_a_text(playground):
    playground.open("index.html")
    page = playground.page
    playground.type_code(TWO_REPOSITORIES)
    playground.wait_evaluated()

    page.select_option("#playground-output-view", "repository:alpha")
    assert '"name": "alpha"' in playground.output()
    assert '"beta"' not in playground.output()
    page.fill("#playground-output-find", "has_")
    assert page.locator("#playground-output-find-count").inner_text().startswith("1/")
    assert page.locator("#playground-output .playground-find-current").count() == 1


def test_examples_are_opened_as_documents(playground):
    playground.open("index.html")
    page = playground.page
    playground.type_code(TWO_REPOSITORIES)
    playground.wait_evaluated()
    page.select_option("#playground-output-view", "repository:alpha")
    snippet = playground.code()

    first = example(playground, 0, 0)
    first.click()
    playground.wait_evaluated()
    tabs = playground.tabs()
    assert len(tabs) == 2
    assert tabs[1]["active"]
    assert tabs[1]["preview"]
    assert tabs[1]["closable"]
    gaps = page.evaluate(
        """() => [...document.querySelectorAll('.playground-document-closable')].map((item) =>
          item.querySelector('.playground-document-close').getBoundingClientRect().left
          - item.querySelector('.playground-document-label').getBoundingClientRect().right)"""
    )
    assert all(gap >= 0 for gap in gaps), "the close button is next to the label, not over it"
    assert not page.locator("#playground-overwrite-modal").is_visible()
    assert CATALOG[0]["examples"][0]["code"].strip() in playground.code()
    assert first.get_attribute("aria-current") == "true"
    assert page.locator("#playground-output-view").input_value() == ""

    # the preview is replaced by the next example, unless it is modified
    second = example(playground, 0, 1)
    second.click()
    playground.wait_evaluated()
    assert len(playground.tabs()) == 2
    assert playground.tabs()[1]["label"] == second.inner_text().strip()
    page.locator(f"{EDITOR} .cm-content").click()
    page.keyboard.press("Control+End")
    page.keyboard.type("\n// adapted")
    page.wait_for_timeout(100)
    assert not playground.tabs()[1]["preview"]
    assert playground.tabs()[1]["modified"]
    modified = playground.code()
    example(playground, 1, 0).click()
    playground.wait_evaluated()
    assert len(playground.tabs()) == 3

    # each document keeps its content, history, evaluation and view of the output
    evaluations = playground.evaluations
    playground.tab("playground.jsonnet").locator(".nav-link").click()
    playground.wait_evaluated()
    assert playground.code() == snippet
    assert playground.evaluations == evaluations
    assert page.locator("#playground-output-view").input_value() == "repository:alpha"
    second.click()
    playground.wait_evaluated()
    assert playground.code() == modified
    page.evaluate(f"{playground.view()}.focus()")
    page.keyboard.press("Control+z")
    assert "// adapted" not in playground.code()


def test_examples_are_closed_and_documents_reset(playground):
    playground.open("index.html")
    page = playground.page
    example(playground, 0, 0).click()
    playground.wait_evaluated()
    page.locator(f"{EDITOR} .cm-content").click()
    page.keyboard.press("Control+End")
    page.keyboard.type("\n// adapted")
    example(playground, 1, 0).click()
    playground.wait_evaluated()

    page.locator("#playground-documents .playground-document").nth(2).locator(".playground-document-close").click()
    page.wait_for_timeout(200)
    assert len(playground.tabs()) == 2
    assert not page.locator("#playground-overwrite-modal").is_visible()

    page.locator("#playground-documents .playground-document").nth(1).locator(".playground-document-close").click()
    page.wait_for_selector("#playground-overwrite-modal.show")
    assert "discards your changes" in page.locator("#playground-overwrite-message").inner_text()
    page.locator("#playground-overwrite-confirm").click()
    page.wait_for_timeout(500)
    assert len(playground.tabs()) == 1
    assert playground.tabs()[0]["active"]

    playground.type_code(TWO_REPOSITORIES)
    playground.wait_evaluated()
    page.locator("#playground-reset").click()
    page.wait_for_selector("#playground-overwrite-modal.show")
    page.locator("#playground-overwrite-confirm").click()
    playground.wait_evaluated()
    assert "orgs.newRepo('myrepo')" in playground.code()
    assert not playground.tabs()[0]["modified"]


def test_a_link_to_the_shown_document_is_copied(playground):
    playground.open("index.html")
    example(playground, 0, 1).click()
    playground.wait_evaluated()

    playground.page.locator("#playground-copy-link").click()
    playground.page.wait_for_timeout(200)

    assert decode(playground.copied.split("#code=")[1]) == playground.code()


def test_the_examples_collapse_to_leave_the_space_to_the_editors(playground):
    playground.open("index.html")
    page = playground.page
    width = page.locator(".playground-editor").bounding_box()["width"]

    page.locator("#playground-examples-toggle").click()
    page.wait_for_timeout(300)
    assert page.locator(".playground-examples").bounding_box()["width"] < 60
    assert page.locator(".playground-editor").bounding_box()["width"] > width + 200
    bar, panes = page.locator(".playground-examples").bounding_box(), page.locator(".playground-panes").bounding_box()
    assert abs((bar["y"] + bar["height"]) - (panes["y"] + panes["height"])) <= 2, "the bar is as high as the editors"
    assert page.locator("#playground-examples-toggle").get_attribute("aria-expanded") == "false"
    assert page.evaluate(f"{playground.view()}.scrollDOM.clientWidth") > 600

    page.reload()
    playground.wait_status("ok")
    assert page.evaluate(
        "document.querySelector('.playground-layout').classList.contains('playground-examples-collapsed')"
    )
    bar = page.locator(".playground-examples").bounding_box()
    page.mouse.click(bar["x"] + bar["width"] / 2, bar["y"] + bar["height"] - 20)
    page.wait_for_timeout(300)
    assert page.locator(".playground-examples").bounding_box()["width"] > 250


def test_changing_the_default_configuration_keeps_the_shown_document(playground):
    playground.open("index.html")
    page = playground.page
    example(playground, 0, 1).click()
    playground.wait_evaluated()
    content = playground.code()

    page.select_option("#playground-template", "example")
    page.wait_for_load_state()
    page.wait_for_timeout(300)

    assert "?template=example#code=" in page.url
    assert decode(page.url.split("#code=")[1]) == content


def test_custom_helper_error_opens_and_marks_that_helper_instead_of_the_upstream_helper(playground):
    """Two libraries have the same helper filename, but only the custom one fails.

    The selected template is vendor/custom/nested/otterdog-defaults.libsonnet.
    It imports its sibling otterdog-functions.libsonnet, containing
    error 'custom helper failed'. A different helper with the same filename
    lives under nested/upstream/.

    This page triggers the error in the real WASM evaluator. Clicking its source
    link must open line 1 of the custom helper and show an error mark there.
    The unrelated upstream helper must have no error mark.
    """
    page = playground.page
    custom_helper = "vendor/custom/nested/otterdog-functions.libsonnet"
    custom_editor = '.tab-pane[data-file="vendor/custom/nested/otterdog-functions.libsonnet"]'
    upstream_editor = '.tab-pane[data-file="vendor/custom/nested/upstream/otterdog-functions.libsonnet"]'

    # playground.open() waits for successful evaluation; this page must fail.
    page.goto(f"{playground.base_url}/custom-helper-error.html")
    playground.wait_status("error")
    error_text = page.locator("#playground-error").inner_text()
    error_source_link = page.locator("#playground-error a", has_text="otterdog-functions.libsonnet:1:")
    error_source_link.click()
    page.wait_for_timeout(200)

    assert "custom helper failed" in error_text
    assert playground.shown_file() == custom_helper
    assert playground.cursor_line(custom_editor) == 1
    assert page.locator(f"{custom_editor} .cm-lintRange-error").count() == 1
    assert page.locator(f"{upstream_editor} .cm-lintRange-error").count() == 0
