import test from "node:test";
import assert from "node:assert/strict";
import { selectionAnchor, utf16Range } from "../src/coordinates.mjs";

test("Unicode, combining marks and multiline selection round trip", () => {
  const text = "# 🍒\nCafe\u0301 hilft.\nZweite Zeile.";
  const start = text.indexOf("Cafe");
  const end = text.length;
  const anchor = selectionAnchor(text, start, end);
  assert.equal(anchor.exact, "Cafe\u0301 hilft.\nZweite Zeile.");
  assert.equal(anchor.start, 4);
  assert.deepEqual(utf16Range(text, anchor.start, anchor.end), [start, end]);
  assert.equal(anchor.prefix, "# 🍒\n");
});

test("reject empty and split-surrogate selections", () => {
  assert.throws(() => selectionAnchor("abc", 1, 1));
  assert.throws(() => selectionAnchor("a🍒b", 2, 4));
  assert.throws(() => selectionAnchor("abc", -1, 2));
});

test("quote context is 32 codepoints not UTF16 units", () => {
  const text = "🍒".repeat(40) + "Text" + "🍒".repeat(40);
  const anchor = selectionAnchor(text, 80, 84);
  assert.equal(Array.from(anchor.prefix).length, 32);
  assert.equal(Array.from(anchor.suffix).length, 32);
  assert.equal(anchor.start, 40);
  assert.equal(anchor.end, 44);
});
