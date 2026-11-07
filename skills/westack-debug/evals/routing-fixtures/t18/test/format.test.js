const test = require("node:test");
const assert = require("node:assert");
const { formatBytes } = require("../src/format");

test("formatBytes", () => {
  assert.strictEqual(formatBytes(512), "512 B");
  assert.strictEqual(formatBytes(2048), "2.0 KB");
});
