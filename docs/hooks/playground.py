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

As script, it generates the catalog of the examples of the configuration guides that the playground lists, and the
catalog of the objects of the reference that the playground uses to complete and describe properties, see
`make playground-examples`.
"""

import base64
import dataclasses
import json
import posixpath
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

_FENCE = re.compile(r"^(?P<indent> *)(?P<fence>`{3,}) *(?P<lang>[\w-]*)")
_HEADING = re.compile(r"^(?P<level>#{1,6}) +(?P<text>\S.*)$")
_TAB = re.compile(r'^(?P<indent> *)===[+!]? +"(?P<label>[^"]*)"')
# placeholders like '<github-id>' that have to be replaced before an example can be evaluated
_PLACEHOLDER = re.compile(r"<[A-Za-z][\w .-]*>")
# markers of code annotations, e.g. '// (1)!', that are only meaningful in the documentation
_ANNOTATION_MARKER = re.compile(r"// \(\d+\)!")
_LINK_TEXT = ":material-play-circle-outline: Open in the Playground"

_ROOT_DIR = Path(__file__).resolve().parents[2]
EXAMPLES_CATALOG = _ROOT_DIR / "otterdog" / "webapp" / "home" / "playground-examples.json"
REFERENCE_CATALOG = _ROOT_DIR / "otterdog" / "webapp" / "home" / "playground-reference.json"

# a call of a function of the default configuration in a 'Jsonnet Function' section of the reference
_FUNCTION = re.compile(r"orgs\.(?P<name>\w+)\(")
# a property annotated in a jsonnet block, e.g. 'settings+: { ... }, // (1)!', and the matching annotation
_ANNOTATED_PROPERTY = re.compile(r"^\s*(?P<key>\w+)\+?:+(?P<value>[^/:][^/]*)//\s*\((?P<number>\d+)\)!")
_ANNOTATION_LINK = re.compile(r"^\s*(?P<number>\d+)\.\s+see \[(?P<title>[^\]]+)\]\((?P<link>[^)]+)\)")
_LINK = re.compile(r"\]\((?P<path>[^)#]*)(?:#(?P<anchor>[\w-]+))?\)")
# a markdown link, replaced by its text in the plain text of a heading or a cell of a table
_LINK_WITH_TEXT = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# an entry of the navigation of mkdocs.yml, e.g. '- Repository Webhook: reference/organization/repository/webhook.md'
_NAV_ENTRY = re.compile(r"^\s*- (?P<entry>.*)$")
_LINE_BREAK = re.compile(r"<br\s*/?>")


def playground_url(base_url: str, code: str) -> str:
    encoded = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{base_url.rstrip('/')}/playground?template=example#code={encoded}"


def is_complete_example(code: str) -> bool:
    return "orgs.newOrg(" in code and "..." not in code and _PLACEHOLDER.search(code) is None


def strip_annotation_markers(code: str) -> str:
    return "".join(_strip_annotation_marker(line) for line in code.splitlines(keepends=True))


def _strip_annotation_marker(line: str) -> str:
    marker = _ANNOTATION_MARKER.search(line)
    return line if marker is None else line[: marker.start()].rstrip(" \t") + line[marker.end() :]


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
    position = _PagePosition()
    examples: list[dict[str, str | None]] = []

    index = 0
    while index < len(lines):
        position.leave_tab(lines[index])
        fence = _FENCE.match(lines[index])
        if fence is None:
            position.follow(lines[index])
            index += 1
            continue

        end = _closing_fence(lines, index + 1, fence.group("indent"), fence.group("fence"))
        if end is None:
            break
        indent = len(fence.group("indent"))
        code = "".join(code_line[indent:] for code_line in lines[index + 1 : end])
        if fence.group("lang") == "jsonnet" and is_complete_example(code):
            examples.append(
                {"section": position.section, "variant": position.tab, "code": strip_annotation_markers(code)}
            )
        index = end + 1

    return position.title, examples


@dataclasses.dataclass
class _PagePosition:
    """The title of a page, and the heading of the section and the content tab of its current line."""

    title: str | None = None
    section: str | None = None
    tab: str | None = None
    tab_indent: int = 0

    def leave_tab(self, line: str) -> None:
        # the content of a tab is indented, the next line indented as the tab ends it, unless it starts another tab
        indent = len(line) - len(line.lstrip(" "))
        if self.tab is not None and line.strip() and indent <= self.tab_indent and _TAB.match(line) is None:
            self.tab = None

    def follow(self, line: str) -> None:
        if (heading := _HEADING.match(line)) is not None:
            text = _plain_text(heading.group("text"))
            if len(heading.group("level")) == 1:
                self.title = text
            else:
                self.section = text
            self.tab = None
        elif (tab := _TAB.match(line)) is not None:
            self.tab = tab.group("label")
            self.tab_indent = len(tab.group("indent"))


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


def extract_reference(docs_dir: Path) -> dict[str, Any]:
    """
    Returns the objects documented by the reference of the organization, for the completion of the playground: the
    properties of each object, a page or a section of a page, and the functions of the default configuration that
    create them, as named by the 'Jsonnet Function' sections.
    """

    reference_dir = docs_dir / "reference" / "organization"
    titles = _navigation_titles(docs_dir.parent / "mkdocs.yml", "reference/organization/")
    objects: dict[str, dict[str, Any]] = {}
    functions: dict[str, str] = {}
    for page in sorted(reference_dir.rglob("*.md")):
        page_id = page.relative_to(reference_dir).as_posix()
        objects[page_id] = {"title": titles.get(page_id, page_id), "url": "", "properties": {}}
        _ReferencePage(page_id, objects, functions).read(page.read_text())

    # only objects with properties are kept, e.g. not the format of secret values
    documented = {object_id: entry for object_id, entry in objects.items() if entry["properties"]}
    for entry in documented.values():
        for prop in entry["properties"].values():
            if prop.get("object") not in documented:
                prop.pop("object", None)
    return {
        "objects": documented,
        "functions": {name: target for name, target in functions.items() if target in documented},
    }


def render_reference_catalog(docs_dir: Path) -> str:
    return json.dumps(extract_reference(docs_dir), indent=2, ensure_ascii=False) + "\n"


class _ReferencePage:
    """
    Reads the objects documented by a page of the reference: the page and its sections, with the properties of their
    tables or of the annotations of their example, and the functions named by its 'Jsonnet Function' sections.
    """

    def __init__(self, page_id: str, objects: dict, functions: dict[str, str]) -> None:
        self.page_id = page_id
        # the url of the page of a directory is the one of the directory
        path = page_id.removesuffix("index.md")
        if path == page_id:
            path = page_id.removesuffix(".md") + "/"
        self.url = f"reference/organization/{path}"
        self.objects = objects
        self.functions = functions
        self.current = page_id
        # the object whose function is named by the current 'Jsonnet Function' section
        self.function_target: str | None = None
        self.annotated: dict[str, tuple[str, str]] = {}
        self.annotations: dict[str, dict[str, Any]] = {}

    def read(self, markdown: str) -> None:
        self.objects[self.page_id]["url"] = self.url
        for line in markdown.splitlines():
            self._read_line(line)

        # an object described by the annotations of its example instead of a table, e.g. the organization
        if not self.objects[self.page_id]["properties"]:
            self.objects[self.page_id]["properties"] = self.annotations

    def _read_line(self, line: str) -> None:
        if (heading := _HEADING.match(line)) is not None:
            self._read_heading(len(heading.group("level")), _plain_text(heading.group("text")))
        elif self.function_target is not None and (call := _FUNCTION.search(line)) is not None:
            self.functions.setdefault(call.group("name"), self.function_target)
        elif (row := _property_row(self.page_id, line)) is not None:
            self.objects[self.current]["properties"][row[0]] = row[1]
        elif (prop := _ANNOTATED_PROPERTY.match(line)) is not None:
            self.annotated[prop.group("number")] = (prop.group("key"), prop.group("value").strip())
        elif (link := _ANNOTATION_LINK.match(line)) is not None and link.group("number") in self.annotated:
            key, value = self.annotated[link.group("number")]
            self.annotations[key] = {
                "type": "list" if value.startswith("[") else "object",
                "description": link.group("title"),
                "object": _linked_object(self.page_id, link.group(0)),
            }

    def _read_heading(self, level: int, text: str) -> None:
        self.function_target = None
        if text == "Jsonnet Function":
            self.function_target = self.page_id if level <= 2 else self.current
        elif level == 1:
            self.objects[self.page_id]["title"] = text
        else:
            self.current = f"{self.page_id}#{_slugify(text)}"
            self.objects.setdefault(
                self.current, {"title": text, "url": f"{self.url}#{_slugify(text)}", "properties": {}}
            )


def _navigation_titles(mkdocs_file: Path, prefix: str) -> dict[str, str]:
    """
    Returns the titles of the pages under a prefix in the navigation of the documentation, the page of a section
    without title getting the title of the section, e.g. 'Environment'.
    """

    titles: dict[str, str] = {}
    section: str | None = None
    for line in mkdocs_file.read_text().splitlines():
        entry = _NAV_ENTRY.match(line)
        title, page = _navigation_entry(entry.group("entry")) if entry is not None else (None, None)
        name = title or section
        if page is not None and page.startswith(prefix) and page.endswith(".md") and name is not None:
            titles[page.removeprefix(prefix)] = name
        # a section has a title without page
        section = title if page == "" else None
    return titles


def _navigation_entry(entry: str) -> tuple[str | None, str]:
    """
    Returns the title and the page of an entry of the navigation, e.g. ('Webhook', 'webhook.md') for
    'Webhook: webhook.md', (None, 'webhook.md') for 'webhook.md', and ('Section', '') for 'Section:'.
    """

    title, separator, page = entry.partition(":")
    return (title.strip(), page.strip()) if separator else (None, title.strip())


def _property_row(page_id: str, line: str) -> tuple[str, dict[str, Any]] | None:
    cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
    key = re.fullmatch(r"_([\w-]+)_", cells[0]) if len(cells) >= 3 else None
    if key is None:
        return None

    prop: dict[str, Any] = {"type": _cell_text(cells[1]), "description": _cell_text(cells[2])}
    if len(cells) > 3 and cells[3]:
        prop["notes"] = _cell_text(cells[3])
    if (linked := _linked_object(page_id, cells[1])) is not None:
        prop["object"] = linked
    return key.group(1), prop


def _linked_object(page_id: str, markdown: str) -> str | None:
    link = _LINK.search(markdown)
    if link is None:
        return None
    path = (
        page_id
        if not link.group("path")
        else posixpath.normpath(posixpath.join(posixpath.dirname(page_id), link.group("path")))
    )
    return path if link.group("anchor") is None else f"{path}#{link.group('anchor')}"


def _cell_text(markdown: str) -> str:
    text = _LINK_WITH_TEXT.sub(r"\1", markdown)
    text = text.replace("\\[", "[").replace("\\]", "]").replace("\\|", "|")
    return " ".join(_LINE_BREAK.sub(" ", text).split())


def _plain_text(markdown: str) -> str:
    text = _LINK_WITH_TEXT.sub(r"\1", markdown)
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
    REFERENCE_CATALOG.write_text(render_reference_catalog(_ROOT_DIR / "docs"))
