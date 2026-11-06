const test = require("node:test");
const assert = require("node:assert");
const { formatClock } = require("../src/clock");

test("formatClock", () => {
  assert.strictEqual(formatClock(90), "01:30");
});
