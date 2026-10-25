#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The explicit values identical to the values of the default configuration."""

CONFIGURATION = """local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';
local wiki = true;

orgs.newOrg('my-project', 'my-org') {
  settings+: {
    web_commit_signoff_required: true,
    description: "my org",
  },
  _repositories+:: [
    orgs.newRepo('my-repo') {
      has_wiki: wiki,
      allow_merge_commit: true,
      workflows+: {
        enabled: true,
      },
      rulesets: [
        orgs.newRepoRuleset('main') {
          required_pull_request+: {
            required_approving_review_count: 2,
          },
          required_status_checks: null,
        },
      ],
    },
  ],
}"""


def marked(playground) -> list[str]:
    return playground.marked("playground-default-value")


def test_values_of_the_default_configuration_are_highlighted(playground):
    playground.open("example.html")
    playground.type_code(CONFIGURATION)
    playground.wait_evaluated()
    page = playground.page
    page.wait_for_function("document.querySelectorAll('.playground-default-value').length > 0", timeout=10000)

    assert marked(playground) == [
        "web_commit_signoff_required: true",
        "enabled: true",
        "required_approving_review_count: 2",
    ]
    title = page.locator(".playground-default-value").first.get_attribute("title")
    assert "eclipse-csi/otterdog/examples/template/otterdog-defaults.libsonnet" in title
    assert "can be removed" in title

    note = page.locator(".playground-status-note[data-key=defaults] a")
    assert note.inner_text() == "3 values already set by the default configuration"
    assert "not taken into account" in note.get_attribute("title"), "the defaults of GitHub are not used"
    note.click()
    assert playground.cursor_line() == 6
    note.click()
    assert playground.cursor_line() == 14


def test_a_value_that_the_default_configuration_computes_otherwise_in_its_context_is_not_highlighted(playground):
    playground.open("example.html")
    # the default configuration computes the repositories from _repositories, an empty list being its value otherwise
    playground.type_code(CONFIGURATION.replace("  _repositories+:: [", "  repositories: [],\n  _repositories+:: ["))
    playground.wait_evaluated()
    playground.page.wait_for_function(
        "document.querySelectorAll('.playground-default-value').length > 0", timeout=10000
    )

    assert marked(playground) == [
        "web_commit_signoff_required: true",
        "enabled: true",
        "required_approving_review_count: 2",
    ]


def test_a_value_changed_to_the_default_is_highlighted(playground):
    playground.open("example.html")
    playground.type_code(CONFIGURATION.replace("allow_merge_commit: true", "allow_merge_commit: false"))
    playground.wait_evaluated()

    playground.page.wait_for_function(
        "document.querySelectorAll('.playground-default-value').length > 0", timeout=10000
    )
    assert "allow_merge_commit: false" in marked(playground)


def test_nothing_is_highlighted_while_the_configuration_has_an_error(playground):
    playground.open("example.html")
    playground.type_code(CONFIGURATION.replace("enabled: true,", "enabled: unknown,"))
    playground.wait_evaluated()

    assert marked(playground) == []
    assert playground.note("defaults") is None
