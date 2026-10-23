#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Connects the jsonnet examples of the documentation with the playground of the otterdog dashboard.

As MkDocs hook, it adds a link to the playground below every complete jsonnet example. An example is complete if
it defines an organization with `orgs.newOrg`, does not omit content with `...` and does not contain placeholders
like `<github-id>`. The snippet is passed to the playground base64url encoded in the fragment of the url, the
playground evaluates it with the example template of otterdog, which the examples are validated with. The base
url of the dashboard is configured with `extra.otterdog_url` in `mkdocs.yml`, no link is added if it is empty.

As script, it generates the catalog of the examples of the configuration guides that the playground lists, see
`make playground-examples`.
"""

import base64
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

_FENCE = re.compile(r"^(?P<indent> *)(?P<fence>`{3,}) *(?P<lang>[\w-]*)")
_HEADING = re.compile(r"^(?P<level>#{1,6}) +(?P<text>.+?) *$")
_TAB = re.compile(r'^(?P<indent> *)===[+!]? +"(?P<label>[^"]*)"')
# placeholders like '<github-id>' that have to be replaced before an example can be evaluated
_PLACEHOLDER = re.compile(r"<[A-Za-z][\w .-]*>")
# markers of code annotations, e.g. '// (1)!', that are only meaningful in the documentation
_ANNOTATION_MARKER = re.compile(r"[ \t]*// \(\d+\)!")
_LINK_TEXT = ":material-play-circle-outline: Open in the Playground"

_ROOT_DIR = Path(__file__).resolve().parents[2]
EXAMPLES_CATALOG = _ROOT_DIR / "otterdog" / "webapp" / "home" / "playground-examples.json"


def playground_url(base_url: str, code: str) -> str:
    encoded = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{base_url.rstrip('/')}/playground?template=example#code={encoded}"


def is_complete_example(code: str) -> bool:
    return "orgs.newOrg(" in code and "..." not in code and _PLACEHOLDER.search(code) is None


def strip_annotation_markers(code: str) -> str:
    return _ANNOTATION_MARKER.sub("", code)


def add_playground_links(markdown: str, base_url: str) -> str:
    lines = markdown.splitlines(keepends=True)
    result: list[str] = []

    index = 0
    while index < len(lines):
        match = _FENCE.match(lines[index])
        if match is None:
            result.append(lines[index])
            index += 1
            continue

        indent, fence = match.group("indent"), match.group("fence")
        end = _closing_fence(lines, index + 1, indent, fence)
        if end is None:
            result.extend(lines[index:])
            break

        code = "".join(line[len(indent) :] for line in lines[index + 1 : end])
        result.extend(lines[index : end + 1])
        index = end + 1

        if match.group("lang") != "jsonnet" or not is_complete_example(code):
            continue

        # code annotations must directly follow their code block, add the link after them
        annotations_end = _end_of_annotations(lines, index, indent)
        result.extend(lines[index:annotations_end])
        index = annotations_end

        url = playground_url(base_url, strip_annotation_markers(code))
        result.append("\n")
        result.append(f'{indent}[{_LINK_TEXT}]({url}){{ target="_blank" rel="noopener" }}\n')
        if index < len(lines) and lines[index].strip():
            result.append("\n")

    return "".join(result)


def extract_examples(markdown: str) -> tuple[str | None, list[dict[str, str | None]]]:
    """
    Returns the title of a page and its complete jsonnet examples, each with the heading of its section and the
    label of its content tab, if any.
    """

    lines = markdown.splitlines(keepends=True)
    title: str | None = None
    section: str | None = None
    tab: str | None = None
    tab_indent = 0
    examples: list[dict[str, str | None]] = []

    index = 0
    while index < len(lines):
        line = lines[index]
        indent = len(line) - len(line.lstrip(" "))

        if tab is not None and line.strip() and indent <= tab_indent and _TAB.match(line) is None:
            tab = None

        fence = _FENCE.match(line)
        if fence is not None:
            end = _closing_fence(lines, index + 1, fence.group("indent"), fence.group("fence"))
            if end is None:
                break

            code = "".join(code_line[indent:] for code_line in lines[index + 1 : end])
            if fence.group("lang") == "jsonnet" and is_complete_example(code):
                examples.append({"section": section, "variant": tab, "code": strip_annotation_markers(code)})

            index = end + 1
            continue

        if (heading := _HEADING.match(line)) is not None:
            text = _plain_text(heading.group("text"))
            if len(heading.group("level")) == 1:
                title = text
            else:
                section = text
            tab = None
        elif (tab_match := _TAB.match(line)) is not None:
            tab = tab_match.group("label")
            tab_indent = len(tab_match.group("indent"))

        index += 1

    return title, examples


def render_examples_catalog(docs_dir: Path) -> str:
    """
    Renders the catalog of the examples of the configuration guides, in the order of the guides index, followed
    by the examples of the page about organization-wide policies.
    """

    guides_dir = docs_dir / "userguide" / "guides"
    names = dict.fromkeys(re.findall(r"\]\(([\w-]+)\.md(?:#[\w-]*)?\)", (guides_dir / "index.md").read_text()))
    pages = [guides_dir / f"{name}.md" for name in names]
    pages.append(docs_dir / "operating_otterdog" / "organization-policies.md")

    catalog = []
    for page in pages:
        title, examples = extract_examples(page.read_text())
        if len(examples) == 0:
            continue

        # examples of the same section without content tab are numbered
        untabbed = Counter(example["section"] for example in examples if example["variant"] is None)
        numbers: Counter[str | None] = Counter()
        entries: list[dict[str, str | None]] = []
        for example in examples:
            section = example["section"] or title or page.stem
            entry_title = section
            if example["variant"] is None and untabbed[example["section"]] > 1:
                numbers[example["section"]] += 1
                entry_title = f"{section} ({numbers[example['section']]})"

            entries.append(
                {
                    "title": entry_title,
                    "variant": example["variant"],
                    "anchor": _slugify(section),
                    "code": example["code"],
                }
            )

        catalog.append(
            {
                "title": title or page.stem,
                "path": page.relative_to(docs_dir).with_suffix("").as_posix() + "/",
                "examples": entries,
            }
        )

    return json.dumps({"pages": catalog}, indent=2, ensure_ascii=False) + "\n"


def _plain_text(markdown: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", markdown)
    return text.replace("`", "").replace("**", "").strip()


def _slugify(text: str) -> str:
    # same algorithm as the default slugify function of the 'toc' markdown extension
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def _closing_fence(lines: list[str], start: int, indent: str, fence: str) -> int | None:
    closing = re.compile(rf"^{re.escape(indent)}{re.escape(fence)}[ ]*$")
    for index in range(start, len(lines)):
        if closing.match(lines[index].rstrip("\n")):
            return index
    return None


def _end_of_annotations(lines: list[str], start: int, indent: str) -> int:
    item = re.compile(rf"^{re.escape(indent)}\d+\. ")
    continuation = f"{indent}   "

    index = start
    while index < len(lines) and not lines[index].strip():
        index += 1

    if index == len(lines) or item.match(lines[index]) is None:
        return start

    end = index
    while index < len(lines):
        line = lines[index]
        if item.match(line) or (line.startswith(continuation) and line.strip()):
            index += 1
            end = index
        elif not line.strip():
            index += 1
        else:
            break

    return end


def on_page_markdown(markdown: str, *, config: Any, **_: Any) -> str:
    base_url = config.extra.get("otterdog_url")
    if not base_url:
        return markdown

    return add_playground_links(markdown, base_url)


if __name__ == "__main__":
    EXAMPLES_CATALOG.write_text(render_examples_catalog(_ROOT_DIR / "docs"))
