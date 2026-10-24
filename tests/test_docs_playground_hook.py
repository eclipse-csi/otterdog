#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import base64
import importlib.util
import re
from pathlib import Path

import pretend
import pytest

_ROOT_DIR = Path(__file__).parent.parent
_BASE_URL = "https://otterdog.example.org"

_LINK = re.compile(
    r"^(?P<indent>[ ]*)\[[^\]]*Open in the Playground\]\("
    + re.escape(_BASE_URL)
    + r"/playground\?template=example#code=(?P<code>[\w-]+)\)",
    re.MULTILINE,
)


@pytest.fixture(scope="module")
def hook():
    spec = importlib.util.spec_from_file_location("playground_hook", _ROOT_DIR / "docs" / "hooks" / "playground.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decode(code: str) -> str:
    return base64.urlsafe_b64decode(code + "=" * (-len(code) % 4)).decode("utf-8")


def _links(markdown: str) -> list[tuple[str, str]]:
    return [(m.group("indent"), _decode(m.group("code"))) for m in _LINK.finditer(markdown)]


def test_playground_url(hook):
    url = hook.playground_url(_BASE_URL + "/", "orgs.newOrg('my-org') { name: 'é' }\n")

    assert url.startswith(f"{_BASE_URL}/playground?template=example#code=")
    assert _decode(url.split("#code=")[1]) == "orgs.newOrg('my-org') { name: 'é' }\n"


def test_link_added_below_complete_example(hook):
    markdown = "Text\n\n``` jsonnet\norgs.newOrg('my-org') {\n}\n```\n\nMore text\n"

    result = hook.add_playground_links(markdown, _BASE_URL)

    assert _links(result) == [("", "orgs.newOrg('my-org') {\n}\n")]
    assert result.startswith(markdown.split("\n\nMore text")[0])
    assert result.endswith("\n\nMore text\n")


@pytest.mark.parametrize(
    "block",
    [
        "``` jsonnet\norgs.newOrg('my-org') {\n  ...\n}\n```\n",
        "``` jsonnet\norgs.newOrg('<project-name>', '<github-id>') {\n}\n```\n",
        "``` jsonnet\norgs.newRepo('my-repo')\n```\n",
        '``` json\n{ "text": "orgs.newOrg(\'my-org\')" }\n```\n',
    ],
)
def test_no_link_for_other_blocks(hook, block):
    assert hook.add_playground_links(block, _BASE_URL) == block


def test_link_added_after_code_annotations(hook):
    markdown = (
        '=== "Ruleset"\n'
        "\n"
        "    ``` jsonnet\n"
        "    orgs.newOrg('my-org') { // (1)!\n"
        "    }\n"
        "    ```\n"
        "\n"
        "    1. First annotation\n"
        "       continued.\n"
        "    2. Second annotation\n"
        "\n"
        "Text\n"
    )

    result = hook.add_playground_links(markdown, _BASE_URL)

    assert _links(result) == [("    ", "orgs.newOrg('my-org') {\n}\n")]
    annotations_end = result.index("    2. Second annotation\n") + len("    2. Second annotation\n")
    assert result.index("Open in the Playground") > annotations_end
    assert result.endswith("\n\nText\n")


def test_no_link_without_otterdog_url(hook):
    markdown = "``` jsonnet\norgs.newOrg('my-org')\n```\n"
    config = pretend.stub(extra={"otterdog_url": ""})

    assert hook.on_page_markdown(markdown, page=None, config=config, files=None) == markdown


def test_every_guide_example_has_a_link(hook):
    pages = [
        *sorted((_ROOT_DIR / "docs" / "userguide" / "guides").glob("*.md")),
        _ROOT_DIR / "docs" / "operating_otterdog" / "organization-policies.md",
    ]

    for page in pages:
        markdown = page.read_text()
        blocks = len(re.findall(r"^[ ]*`{3,}[ ]*jsonnet", markdown, re.MULTILINE))
        assert len(_links(hook.add_playground_links(markdown, _BASE_URL))) == blocks, page.name


def test_extract_examples(hook):
    markdown = (
        "# Page title\n"
        "\n"
        "## Section with `code`\n"
        "\n"
        '=== "First"\n'
        "\n"
        "    ``` jsonnet\n"
        "    orgs.newOrg('my-org') { // (1)!\n"
        "    }\n"
        "    ```\n"
        "\n"
        "    1. Annotation\n"
        "\n"
        "Paragraph after the tabs.\n"
        "\n"
        "``` jsonnet\n"
        "orgs.newOrg('other-org')\n"
        "```\n"
        "\n"
        "``` jsonnet\n"
        "orgs.newOrg('my-org') {\n"
        "  ...\n"
        "}\n"
        "```\n"
    )

    title, examples = hook.extract_examples(markdown)

    assert title == "Page title"
    assert examples == [
        {"section": "Section with code", "variant": "First", "code": "orgs.newOrg('my-org') {\n}\n"},
        {"section": "Section with code", "variant": None, "code": "orgs.newOrg('other-org')\n"},
    ]


def test_playground_examples_catalog_is_up_to_date(hook):
    expected = hook.render_examples_catalog(_ROOT_DIR / "docs")

    assert hook.EXAMPLES_CATALOG.read_text() == expected, "run 'make playground-examples' to update the catalog"


def test_extract_reference(hook):
    reference = hook.extract_reference(_ROOT_DIR / "docs")

    # the functions of the default configuration, named by the 'Jsonnet Function' sections
    assert reference["functions"]["newRepo"] == "repository/index.md"
    assert reference["functions"]["newPullRequest"] == "repository/ruleset.md#pull-request-settings"
    assert reference["functions"]["extendRepo"] == "repository/index.md"

    repository = reference["objects"]["repository/index.md"]
    assert repository["title"] == "Repository"
    assert repository["url"] == "reference/organization/repository/"
    assert repository["properties"]["has_wiki"] == {"type": "boolean", "description": "If the repo has a wiki"}
    # embedded models are linked by the properties containing them
    assert repository["properties"]["workflows"]["object"] == "repository/index.md#workflow-settings"
    assert "enabled" in reference["objects"]["repository/index.md#workflow-settings"]["properties"]

    # pages without title get the one of the navigation, or of their section in the navigation
    assert reference["objects"]["repository/webhook.md"]["title"] == "Repository Webhook"
    assert reference["objects"]["repository/environment/index.md"]["title"] == "Environment"

    # the organization is described by the annotations of its example
    assert reference["objects"]["index.md"]["properties"]["settings"] == {
        "type": "object",
        "description": "Organization Settings",
        "object": "settings.md",
    }


def test_playground_reference_catalog_is_up_to_date(hook):
    expected = hook.render_reference_catalog(_ROOT_DIR / "docs")

    assert hook.REFERENCE_CATALOG.read_text() == expected, "run 'make playground-examples' to update the catalog"
