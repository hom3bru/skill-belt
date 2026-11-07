const test = require("node:test");
const assert = require("node:assert");
const http = require("node:http");
const { getJson } = require("../src/fetchProxy");

test("test_fetch_proxy: requests go through HTTP_PROXY", async () => {
  const seen = [];
  const proxy = http.createServer((req, res) => {
    seen.push(req.url);
    res.setHeader("content-type", "application/json");
    res.end('{"ok":true}');
  });
  await new Promise((resolve) => proxy.listen(0, resolve));
  process.env.HTTP_PROXY = "http://127.0.0.1:" + proxy.address().port;
  await getJson("http://example.test/data").catch(() => {});
  proxy.close();
  assert.deepStrictEqual(seen, ["http://example.test/data"]);
});
