// Runs the browser app's range parser against the cases shared with the Python tests.
// Usage: node --test tests/js/ranges.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PageSpecError, select, isSpec } from "../../docs/ranges.js";

const { cases } = JSON.parse(readFileSync(new URL("../range_cases.json", import.meta.url), "utf8"));

for (const c of cases) {
  test(`${JSON.stringify(c.spec)} on ${c.n} pages`, () => {
    if (c.error) {
      assert.throws(() => select(c.spec, c.n), PageSpecError);
    } else {
      assert.deepEqual(select(c.spec, c.n).map((i) => i + 1), c.pages);
    }
  });
}

test("isSpec", () => {
  assert.equal(isSpec("1-3"), true);
  assert.equal(isSpec(""), false);
  assert.equal(isSpec("\\a.pdf"), false);
});
