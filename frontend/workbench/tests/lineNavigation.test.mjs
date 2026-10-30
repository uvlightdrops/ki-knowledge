import test from "node:test";
import assert from "node:assert/strict";
import { lineNavigation } from "../src/lineNavigation.mjs";

test("short texts include every line without requiring headings", () => {
  assert.deepEqual(lineNavigation(""), [1]);
  assert.deepEqual(lineNavigation("plain\ntext\nlast"), [1, 2, 3]);
  assert.deepEqual(lineNavigation("one\r\ntwo\rthree\nfour"), [1, 2, 3, 4]);
});

test("long texts have evenly spaced numeric jumps plus first and last line", () => {
  assert.deepEqual(lineNavigation("text\n".repeat(183)), [
    1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 184,
  ]);
});

test("large documents keep the navigation bounded, ordered and within the text", () => {
  for (const count of [20, 21, 100, 1000, 10001, 100000]) {
    const lines = lineNavigation("line\n".repeat(count - 1));
    assert.equal(lines[0], 1);
    assert.equal(lines.at(-1), count);
    assert.ok(lines.length <= 22);
    assert.ok(lines.every((line, index) => index === 0 || line > lines[index - 1]));
  }
});
