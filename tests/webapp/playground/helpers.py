#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Drives a page of the playground: its editors, documents, output and status."""

import base64
from typing import Any

# Counts the evaluations sent to the worker, captures the copied texts, and finds the CodeMirror view of an element.
_INIT_SCRIPT = """
window.__evaluations = 0;
const postMessage = Worker.prototype.postMessage;
Worker.prototype.postMessage = function (message, ...rest) {
  // the comparisons with the default configuration are not counted
  if (!message.files['playground.jsonnet'].includes('defaultsSame(')) {
    window.__evaluations++;
  }
  return postMessage.call(this, message, ...rest);
};
window.__copied = null;
Object.defineProperty(navigator, 'clipboard', {value: {writeText: async (text) => { window.__copied = text; }}});
window.__view = (selector) => document.querySelector(selector + ' .cm-content').cmTile.root.view;
// the texts of the marks of a class, the adjacent elements of a mark being merged
window.__marked = (selector, className) => {
  const view = __view(selector);
  const ranges = [];
  for (const element of document.querySelectorAll(selector + ' .' + className)) {
    const from = view.posAtDOM(element, 0);
    const to = from + element.textContent.length;
    const last = ranges[ranges.length - 1];
    if (last !== undefined && last.to === from) last.to = to; else ranges.push({from, to});
  }
  return ranges.map(({from, to}) => view.state.sliceDoc(from, to));
};
"""

EDITOR = "#playground-input-0"
OUTPUT = "#playground-output"

# changes are evaluated once typing paused for this delay, in milliseconds
EVALUATION_DELAY = 300


def encode(code: str) -> str:
    return base64.urlsafe_b64encode(code.encode()).decode().rstrip("=")


def decode(encoded: str) -> str:
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()


class Playground:
    def __init__(self, page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url
        page.add_init_script(_INIT_SCRIPT)

    def open(self, name: str, fragment: str = "", timeout: int = 30000) -> None:
        self.page.goto(f"{self.base_url}/{name}{fragment}")
        self.wait_status("ok", timeout)

    def view(self, selector: str = EDITOR) -> str:
        return f"__view({selector!r})"

    # ---- editors

    def code(self, selector: str = EDITOR) -> str:
        return self.page.evaluate(f"{self.view(selector)}.state.doc.toString()")

    def output(self) -> str:
        return self.code(OUTPUT)

    def type_code(self, code: str, selector: str = EDITOR) -> None:
        """Replaces the content of an editor like a user, evaluated once typing paused."""
        self.page.evaluate(
            f"(code) => {self.view(selector)}.dispatch("
            f"{{changes: {{from: 0, to: {self.view(selector)}.state.doc.length, insert: code}}, userEvent: 'input'}})",
            code,
        )

    def replace(self, old: str, new: str, selector: str = EDITOR) -> None:
        """Replaces the first occurrence of a text in an editor like a user."""
        start = self.code(selector).index(old)
        self.page.evaluate(
            f"{self.view(selector)}.dispatch({{changes: {{from: {start}, to: {start + len(old)}, insert: {new!r}}},"
            f" userEvent: 'input'}})"
        )

    def set_cursor(self, offset: int, selector: str = EDITOR) -> None:
        self.page.evaluate(
            f"{self.view(selector)}.dispatch({{selection: {{anchor: {offset}}}}}); {self.view(selector)}.focus()"
        )

    def cursor_line(self, selector: str = EDITOR) -> int:
        """The line of the cursor, starting at 1."""
        view = self.view(selector)
        return self.page.evaluate(f"{view}.state.doc.lineAt({view}.state.selection.main.head).number")

    def line_at(self, element_selector: str, selector: str = EDITOR) -> int:
        """The line of an element of an editor, starting at 1."""
        view = self.view(selector)
        return self.page.evaluate(
            f"{view}.state.doc.lineAt({view}.posAtDOM(document.querySelector({element_selector!r}), 0)).number"
        )

    def marked(self, class_name: str, selector: str = EDITOR) -> list[str]:
        return self.page.evaluate(f"__marked({selector!r}, {class_name!r})")

    # ---- evaluation

    def wait_status(self, state: str, timeout: int = 20000) -> None:
        self.page.wait_for_function(
            f"document.getElementById('playground-status').dataset.state === '{state}'", timeout=timeout
        )

    def wait_evaluated(self, timeout: int = 20000) -> None:
        self.page.wait_for_timeout(EVALUATION_DELAY + 150)
        self.page.wait_for_function(
            "['ok', 'error'].includes(document.getElementById('playground-status').dataset.state)", timeout=timeout
        )
        self.page.wait_for_timeout(150)

    @property
    def evaluations(self) -> int:
        return self.page.evaluate("window.__evaluations")

    @property
    def status(self) -> str:
        return self.page.locator("#playground-status").inner_text()

    def note(self, key: str) -> str | None:
        return self.page.evaluate(
            f"document.querySelector('.playground-status-note[data-key={key}]')?.textContent ?? null"
        )

    @property
    def copied(self) -> str | None:
        return self.page.evaluate("window.__copied")

    # ---- documents and files

    def tabs(self) -> list[dict[str, Any]]:
        return self.page.evaluate(
            """() => [...document.querySelectorAll('#playground-documents .playground-document')].map((item) => ({
              label: item.querySelector('.playground-document-label').textContent,
              active: item.querySelector('.nav-link').classList.contains('active'),
              preview: item.classList.contains('playground-document-preview'),
              modified: item.querySelector('.playground-document-modified') !== null,
              closable: item.querySelector('.playground-document-close') !== null,
            }))"""
        )

    def tab(self, label: str):
        return self.page.locator(
            "#playground-documents .playground-document",
            has=self.page.locator(".playground-document-label", has_text=label),
        )

    def shown_file(self) -> str:
        return self.page.evaluate("document.querySelector('.tab-pane[data-file].active').dataset.file")

    def open_file(self, name: str) -> None:
        self.page.locator("#playground-files-toggle").click()
        self.page.locator(f'.playground-file-item[data-file$="/{name}"]').click()
        self.page.wait_for_timeout(150)

    @staticmethod
    def file_editor(name: str) -> str:
        return f'.tab-pane[data-file$="{name}"]'

    def examples(self):
        return self.page.locator(".playground-example")
