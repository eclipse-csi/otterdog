import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";

// The font of the dashboard, served with the assets: css/app.scss imports the @font-face of its package and names its
// family first, else the pages would fall back on the font of the system without any error.

const STYLESHEET = readFileSync(new URL("../css/app.scss", import.meta.url), "utf8");

// the font faces imported from a package of fontsource, e.g. @fontsource-variable/inter/wght
function importedFaces() {
  const imports = [...STYLESHEET.matchAll(/^@import "(@fontsource[^"]+)";$/gm)].map((match) => match[1]);
  return imports.map((name) => readFileSync(new URL(`../../node_modules/${name}.css`, import.meta.url), "utf8"));
}

test("the font of the dashboard is the family of the imported font faces", () => {
  const family = STYLESHEET.match(/^\$font-family-sans-serif: "([^"]+)"/m)?.[1];
  const faces = importedFaces();

  assert.ok(faces.length > 0, "no font faces imported");
  for (const css of faces) {
    const families = new Set([...css.matchAll(/font-family: '([^']+)'/g)].map((match) => match[1]));
    assert.deepEqual([...families], [family]);
  }
});

test("the upright and the italic font faces are imported", () => {
  const styles = new Set(importedFaces().flatMap((css) => [...css.matchAll(/font-style: (\w+)/g)].map((m) => m[1])));

  assert.deepEqual([...styles].sort(), ["italic", "normal"]);
});
