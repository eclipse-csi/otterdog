import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";

import {HIGHLIGHT_VARIABLES} from "./code-theme.js";

// the declarations of a rule of css/app.scss, its selector given in full
function declarations(stylesheet, selector) {
  const start = stylesheet.indexOf(`${selector} {\n  --otterdog-code-`);
  assert.notEqual(start, -1, `no rule ${selector} with the colors of the syntax`);
  return stylesheet.slice(start, stylesheet.indexOf("}", start));
}

test("every color of the syntax is defined for both color modes", () => {
  const stylesheet = readFileSync(new URL("../css/app.scss", import.meta.url), "utf8");
  const light = declarations(stylesheet, ':root,\n[data-bs-theme="light"]');
  const dark = declarations(stylesheet, '[data-bs-theme="dark"]');

  assert.ok(HIGHLIGHT_VARIABLES.length > 10);
  for (const variable of HIGHLIGHT_VARIABLES) {
    assert.ok(light.includes(`${variable}: `), `${variable} has no color in the light mode`);
    assert.ok(dark.includes(`${variable}: `), `${variable} has no color in the dark mode`);
  }
});
