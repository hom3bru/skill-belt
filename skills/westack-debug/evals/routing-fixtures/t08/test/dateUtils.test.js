const test = require("node:test");
const assert = require("node:assert");
const { daysUntil, isWeekend } = require("../src/dateUtils");

test("daysUntil counts to the release date", () => {
  assert.strictEqual(daysUntil("2026-12-25"), 55);
});

test("isWeekend", () => {
  assert.strictEqual(isWeekend("2026-11-07"), true);
  assert.strictEqual(isWeekend("2026-11-09"), false);
});
