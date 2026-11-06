const test = require("node:test");
const assert = require("node:assert");
const { parseDate } = require("../src/parseDate");

test("midday", () => {
  assert.strictEqual(parseDate("2026-03-14 12:00:00"), 14);
});
