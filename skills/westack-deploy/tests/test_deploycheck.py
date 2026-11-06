"""Tests for westack-deploy's scripts/deploycheck.py: platform detection on throwaway repositories, the read-back against
a local server, and the deploy record's rules. Each rule has an in-suite broken-copy control.

Run from the repo root:  python -B -m unittest discover -s skills/westack-deploy/tests
"""
import copy
import functools
import http.server
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "deploycheck.py"


def load(path=SCRIPT, name="westack_deploycheck_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dc = load()


def broken(old, new, name):
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        return load(path, name)


GRANT = {"by": "the user", "said": "deploy abc1234 to the local fixture folder", "scope": "deploy", "target": "fixture"}


def record(**over):
    r = {"format": dc.FORMAT, "platform": "static", "target": {"name": "fixture", "environment": "local",
                                                               "url": "http://127.0.0.1:8781/"},
         "revision": "abc1234def", "grant": dict(GRANT),
         "steps": [{"name": "copy the built site with the revision stamped", "exit": 0}],
         "readback": {"url": "http://127.0.0.1:8781/", "status": 200, "checks": [
             {"name": "status", "passed": True}, {"name": "revision", "passed": True}]},
         "outcome": "healthy"}
    r.update(over)
    return r


class DetectTests(unittest.TestCase):
    def repo(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for rel, text in files.items():
            p = Path(tmp.name, rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return Path(tmp.name)

    def platforms(self, files, module=None):
        return [(p["platform"], p["evidence"]) for p in (module or dc).detect(self.repo(files))["platforms"]]

    def test_each_platform_from_its_file(self):
        fly = (module_detect := dc.detect(self.repo({"fly.toml": 'app = "shop-api"\nprimary_region = "lhr"\n'})))
        self.assertEqual(fly["platforms"][0], {"platform": "fly", "evidence": "fly.toml", "app": "shop-api",
                                               "url": "https://shop-api.fly.dev"})
        self.assertEqual(self.platforms({"netlify.toml": '[build]\n  publish = "dist"\n'}), [("netlify", "netlify.toml")])
        self.assertEqual(self.platforms({"vercel.json": "{}"}), [("vercel", "vercel.json")])
        self.assertEqual(self.platforms({"Procfile": "web: gunicorn app:app\n"}), [("heroku", "Procfile")])
        self.assertEqual(self.platforms({"railway.toml": ""}), [("railway", "railway.toml")])
        self.assertEqual(self.platforms({"wrangler.toml": 'name = "edge"\n'}), [("cloudflare", "wrangler.toml")])
        self.assertEqual(self.platforms({"dist/index.html": "<p>x</p>"}), [("static", "dist/index.html")])
        self.assertEqual(self.platforms({"index.html": "<p>x</p>"}), [("static", "index.html")])

    def test_a_workflow_counts_only_when_it_deploys(self):
        deploys = {".github/workflows/release.yml": "jobs:\n  ship:\n    steps:\n      - run: flyctl deploy --remote-only\n"}
        self.assertEqual(self.platforms(deploys), [("github-actions", ".github/workflows/release.yml")])
        tests_only = {".github/workflows/ci.yml": "jobs:\n  test:\n    steps:\n      - run: pytest\n"}
        self.assertEqual(self.platforms(tests_only), [])

    def test_nothing_found_says_so(self):
        result = dc.detect(self.repo({"README.md": "# lib\n"}))
        self.assertEqual(result["platforms"], [])
        self.assertIn("ask how this project deploys", result["note"])

    def test_the_control_without_fly_detection_misses_it(self):
        b = broken('    if (repo / "fly.toml").is_file():\n', "    if False:\n", "deploycheck_no_fly")
        self.assertEqual(self.platforms({"fly.toml": 'app = "x"\n'}, b), [], "the broken copy misses fly.toml")


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        Path(self.tmp.name, "index.html").write_text('<meta name="revision" content="abc1234def">', encoding="utf-8")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.tmp.name)
        handler.log_message = lambda *a: None
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/"

    def test_the_revision_is_read_back(self):
        rb = dc.readback(self.url, revision="abc1234")
        self.assertEqual((rb["status"], [c["passed"] for c in rb["checks"]]), (200, [True, True]))

    def test_an_old_page_fails_the_revision_check(self):
        rb = dc.readback(self.url, revision="fff9999")
        self.assertEqual([(c["name"], c["passed"]) for c in rb["checks"]], [("status", True), ("revision", False)])

    def test_a_missing_page_and_a_dead_port(self):
        self.assertEqual(dc.readback(self.url + "nope.html")["status"], 404)
        dead = dc.readback("http://127.0.0.1:9/", timeout=2)
        self.assertIsNone(dead["status"])
        self.assertFalse(dead["checks"][0]["passed"])
        with self.assertRaises(ValueError):
            dc.readback("file:///etc/passwd")


class RecordTests(unittest.TestCase):
    def test_a_healthy_record_is_valid(self):
        self.assertEqual(dc.validate(record()), [])

    def test_the_grant_names_this_target_and_scope(self):
        errs = " | ".join(dc.validate(record(grant=dict(GRANT, target="production"))))
        self.assertIn("the grant must name this target", errs)
        self.assertIn("scope must be deploy", " | ".join(dc.validate(record(grant=dict(GRANT, scope="ship")))))
        self.assertIn("who gave it", " | ".join(dc.validate(record(grant=dict(GRANT, said="")))))

    def test_a_failed_check_cannot_be_healthy(self):
        bad = record(readback={"url": "x", "status": 200, "checks": [{"name": "status", "passed": True},
                                                                     {"name": "revision", "passed": False}]})
        self.assertIn("readback: a read-back that does not show the target healthy makes it failed", dc.validate(bad))
        self.assertEqual(dc.validate(dict(bad, outcome="failed")), [], "failed is the honest outcome, with no revert")

    def test_a_reachable_url_alone_is_not_healthy(self):
        bare = record(readback={"url": "x", "status": 200, "checks": [{"name": "status", "passed": True}]})
        self.assertIn("readback: healthy needs the revision read back: a reachable URL alone does not prove this deploy",
                      dc.validate(bare))

    def test_unverified_needs_its_reason_and_no_status(self):
        self.assertIn("unverified needs unverified_reason: what stopped the read-back",
                      dc.validate(record(outcome="unverified", readback=None)))
        self.assertEqual(dc.validate(record(outcome="unverified", readback=None, unverified_reason="the URL timed out")), [])

    def test_a_rollback_needs_its_own_grant(self):
        rb = {"grant": dict(GRANT, scope="rollback"), "steps": [{"name": "restore the previous folder", "exit": 0}],
              "readback": {"url": "x", "status": 200, "checks": [{"name": "status", "passed": True},
                                                                  {"name": "revision", "passed": True}]},
              "outcome": "healthy"}
        failed = record(outcome="failed", readback={"url": "x", "status": 500, "checks": [{"name": "status", "passed": False}]})
        self.assertIn("rollback: a rollback has its own grant, never the deploy's words reused",
                      dc.validate(dict(failed, rollback=rb)))
        own = dict(rb, grant={"by": "the user", "said": "roll it back", "scope": "rollback", "target": "fixture"})
        self.assertEqual(dc.validate(dict(failed, rollback=own)), [])
        self.assertIn("rollback: the grant's scope must be rollback",
                      dc.validate(dict(failed, rollback=dict(own, grant=dict(own["grant"], scope="deploy")))))

    def test_long_waits_need_a_yes(self):
        self.assertIn("a wait past 20 minutes needs the user's yes (wait_grant)", dc.validate(record(waited_minutes=45)))
        self.assertEqual(dc.validate(record(waited_minutes=45, wait_grant="the user: wait another 20")), [])

    def test_the_control_without_the_healthy_rule_passes_a_failed_check(self):
        b = broken("        if not ok_status or not passed:\n", "        if False:\n", "deploycheck_lenient")
        bad = record(readback={"url": "x", "status": 500, "checks": [{"name": "status", "passed": False},
                                                                     {"name": "revision", "passed": True}]})
        self.assertEqual(b.validate(bad), [], "the broken copy calls a failing target healthy")
        self.assertNotEqual(dc.validate(bad), [])

    def test_the_control_without_the_revision_rule_takes_a_reachable_url(self):
        b = broken('        if not any(isinstance(c, dict) and c.get("name") == "revision" and c.get("passed") is True '
                   'for c in rb["checks"]):\n', "        if False:\n", "deploycheck_no_revision")
        bare = record(readback={"url": "x", "status": 200, "checks": [{"name": "status", "passed": True}]})
        self.assertEqual(b.validate(bare), [], "the broken copy certifies a deploy it never saw")

    def test_the_control_reusing_the_deploy_grant_for_a_rollback(self):
        b = broken('                and rb["grant"].get("said") == record["grant"].get("said"):\n',
                   "                and False:\n", "deploycheck_reused_grant")
        rb = {"grant": dict(GRANT, scope="rollback"), "steps": [{"name": "restore", "exit": 0}], "outcome": "unverified"}
        failed = record(outcome="failed", readback={"url": "x", "status": 500, "checks": [{"name": "status", "passed": False}]})
        self.assertEqual(b.validate(dict(failed, rollback=rb)), [], "the broken copy lets the deploy's words roll back")

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "record.json")
            p.write_text(json.dumps(record()), encoding="utf-8")
            self.assertEqual(dc.main(["validate", str(p)]), 0)
            p.write_text(json.dumps(record(outcome="sideways")), encoding="utf-8")
            self.assertEqual(dc.main(["validate", str(p)]), 1)
            self.assertEqual(dc.main(["detect", tmp]), 0)
        self.assertEqual(dc.main(["bogus"]), 64)


if __name__ == "__main__":
    unittest.main()
