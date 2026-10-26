#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The impact of an edited default configuration on the projects of the instance, a page of the administration."""

import pytest

DEFAULTS = "otterdog-defaults.libsonnet"
FUNCTIONS = "otterdog-functions.libsonnet"


def open_page(playground) -> None:
    playground.page.goto(f"{playground.base_url}/template-impact.html")
    playground.page.wait_for_selector(".tab-pane.active .cm-content")


def edit(playground, old: str, new: str, name: str = DEFAULTS) -> None:
    playground.page.locator(".nav-link", has_text=name).click()
    playground.replace(old, new, playground.file_editor(name))


def restore(playground, name: str = DEFAULTS) -> None:
    playground.page.locator(".nav-link", has_text=name).click()
    playground.page.locator(f"{playground.file_editor(name)} .playground-file-restore").click()


def evaluate_projects(playground) -> str:
    page = playground.page
    page.locator("#playground-impact-run").click()
    page.wait_for_function(
        "!document.getElementById('playground-impact-run').disabled"
        " && document.querySelector('#playground-impact .fw-semibold') !== null",
        timeout=60000,
    )
    return " ".join(page.locator("#playground-impact").inner_text().split())


def listed_projects(playground) -> list[str]:
    summaries = playground.page.locator("#playground-impact > details > summary").all_inner_texts()
    return [" ".join(text.split()) for text in summaries]


@pytest.mark.parametrize("name", ["index.html", "example.html", "org.html"])
def test_the_playground_does_not_evaluate_the_impact_of_the_template(playground, name):
    playground.open(name)
    page = playground.page

    assert page.locator("#playground-impact-tab").count() == 0
    playground.open_file(DEFAULTS)
    assert page.evaluate(f"{playground.view(playground.file_editor(DEFAULTS))}.state.readOnly")
    # a page of the administration
    assert page.locator('.sidebar-menu a[href="/admin/template-impact"]').count() == 1


def test_the_files_of_the_default_configuration_are_edited(playground):
    open_page(playground)
    page = playground.page

    tabs = [" ".join(text.split()) for text in page.locator(".nav-tabs .nav-link").all_inner_texts()]
    assert tabs == [DEFAULTS, FUNCTIONS]
    assert page.locator('.sidebar-menu a[href="/admin/template-impact"].active').count() == 1
    assert not page.evaluate(f"{playground.view(playground.file_editor(DEFAULTS))}.state.readOnly")

    edit(playground, "has_wiki: true,", "has_wiki: false,")
    tab = page.locator(".nav-link", has_text=DEFAULTS)
    assert tab.locator(".playground-document-modified").is_visible()
    assert page.locator(f"{playground.file_editor(DEFAULTS)} .playground-file-restore").is_visible()
    assert page.locator(".nav-link", has_text=FUNCTIONS).locator(".playground-document-modified").is_hidden()

    restore(playground)
    assert tab.locator(".playground-document-modified").is_hidden()
    assert "has_wiki: true," in playground.code(playground.file_editor(DEFAULTS))


def test_the_projects_are_evaluated_once_the_default_configuration_is_edited(playground):
    open_page(playground)
    page = playground.page
    run = page.locator("#playground-impact-run")
    assert run.is_disabled(), "the projects do not change with the published default configuration"
    # hovering the disabled button tells why it is disabled
    page.locator("#playground-impact-hint").hover()
    page.wait_for_selector(".tooltip.show", timeout=5000)
    assert "Edit a file of the default configuration" in page.locator(".tooltip.show").inner_text()

    edit(playground, "has_wiki: true,", "has_wiki: false,")
    assert run.is_enabled()
    run.hover()
    page.wait_for_timeout(500)
    assert page.locator(".tooltip.show").count() == 0
    evaluate_projects(playground)
    assert page.locator("#playground-impact-count").inner_text() == "1"

    # once the changes are discarded, the projects do not change anymore
    restore(playground)
    assert run.is_disabled()
    assert page.locator("#playground-impact").inner_text() == ""
    assert page.locator("#playground-impact-count").is_hidden()


def test_projects_changing_or_failing_with_the_edited_default_configuration_are_listed(playground):
    open_page(playground)
    page = playground.page
    edit(playground, "has_wiki: true,", "has_wiki: false,")
    edit(playground, 'content_type: "form",', 'content_type: error "edited webhook",')

    summary = evaluate_projects(playground)

    assert (
        "1 of 4 projects changes with the edited default configuration, 1 fails to evaluate, 1 is unchanged" in summary
    )
    assert "Failing with the published default configuration too: broken." in summary
    assert "1 project is not evaluated" in summary
    # the failing projects first, then the projects that change
    assert listed_projects(playground) == ["gamma error playground", "alpha 1 playground"]
    assert page.locator("#playground-impact-count").inner_text() == "2"

    # the changes grouped by property and values across the projects
    groups = page.evaluate(
        """() => [...document.querySelectorAll('.playground-impact-changes')].map((grid) =>
          [...grid.children].map((cell) => cell.textContent).join(' | '))"""
    )
    assert groups == ["~ | repositories[*].has_wiki | true → false | 1 in 1 project"]

    page.locator(".playground-impact-changes a").first.click()
    assert page.locator("#playground-impact > details", has_text="alpha").is_visible()
    assert page.locator("#playground-impact > details", has_text="gamma").is_hidden()
    filter_note = page.locator("#playground-impact > p", has_text="Projects with the change of")
    assert "repositories[*].has_wiki" in filter_note.inner_text()
    filter_note.locator("a", has_text="Show all the projects").click()
    assert page.locator("#playground-impact > details", has_text="gamma").is_visible()
    assert filter_note.is_hidden()

    page.locator("#playground-impact > details > summary", has_text="alpha").click()
    rows = page.locator("#playground-impact .playground-change-rows").first.inner_text()
    assert "has_wiki" in rows
    assert "true" in rows
    assert "false" in rows
    page.locator("#playground-impact > details > summary", has_text="gamma").click()
    assert "edited webhook" in page.locator("#playground-impact pre").inner_text()
    link = page.locator("#playground-impact > details > summary a", has_text="playground").first
    assert link.get_attribute("href") == "/projects/gamma/playground"


def test_the_impact_is_outdated_once_the_default_configuration_is_edited_again(playground):
    open_page(playground)
    page = playground.page
    edit(playground, "has_wiki: true,", "has_wiki: false,")
    evaluate_projects(playground)
    assert page.locator(".playground-impact-outdated").is_hidden()

    edit(playground, 'content_type: "form",', 'content_type: error "edited webhook",')
    assert page.locator(".playground-impact-outdated").is_visible()

    evaluate_projects(playground)
    assert page.locator(".playground-impact-outdated").is_hidden()
    assert listed_projects(playground) == ["gamma error playground", "alpha 1 playground"]
