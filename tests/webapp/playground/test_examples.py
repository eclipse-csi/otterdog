#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The list of examples, filtered by their title and content."""

import pytest

VISIBLE = """[...document.querySelectorAll('.playground-example')]
  .filter((button) => !button.hidden && !button.closest('.playground-examples-group').hidden).length"""
EMPTY = "!document.getElementById('playground-examples-empty').classList.contains('d-none')"


@pytest.mark.parametrize("name", ["example.html", "org.html"])
def test_examples_are_filtered(playground, name):
    playground.open(name)
    page = playground.page
    total = page.evaluate(VISIBLE)

    page.fill("#playground-examples-filter", "zzzz-no-such-example")
    assert page.evaluate(VISIBLE) == 0
    assert page.evaluate(EMPTY)

    group = page.locator(".playground-examples-group").nth(1)
    page.fill("#playground-examples-filter", group.get_attribute("data-title").lower())
    assert page.evaluate(VISIBLE) >= group.locator(".playground-example").count()
    assert not page.evaluate(EMPTY)

    page.fill("#playground-examples-filter", "required_approving_review_count")
    assert 0 < page.evaluate(VISIBLE) < total, "matched by their content"

    page.fill("#playground-examples-filter", "")
    assert page.evaluate(VISIBLE) == total


def test_the_current_configuration_is_listed_with_the_examples(playground):
    playground.open("org.html")
    page = playground.page

    page.fill("#playground-examples-filter", "current configuration")
    assert page.locator(".playground-example[data-organization]").is_visible()
    page.fill("#playground-examples-filter", "")

    page.locator('.playground-example[data-page="0"][data-example="0"]').click()
    playground.wait_evaluated()
    assert ":" in page.locator(".playground-document .nav-link.active").get_attribute("title"), "titled with its page"
    page.locator(".playground-example[data-organization]").click()
    assert "my-project" in page.locator(".playground-document .nav-link.active").inner_text()
