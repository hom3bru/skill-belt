"""Tests for westack-security's reproduction labels (secaudit.py check) and the path-traversal fixture they are proved on.

Run from the repo root:  python -B -m unittest discover -s skills/westack-security/tests -v
Each rule is also run against a broken copy of the script without it, where the bad record must get through.
"""
import copy
import http.client
import importlib.util
import pathlib
import shutil
import sys
import tempfile
import threading
import unittest

from test_secaudit import Fixture, HERE, codes, confirmed, off, record, sa

FIXTURE = HERE.parent / "evals" / "fixtures" / "repro-traversal"
SHA = "a" * 64


def run(**over):
    r = {"image": "westack-repro-traversal", "image_id": "sha256:" + "b" * 64,
         "command": "docker run --rm --network none --read-only westack-repro-traversal", "exit": 0,
         "log_sha256": SHA, "network": "none"}
    r.update(over)
    return r


def reproduced(**over):
    rep = {"label": "reproduced", "budget": {"minutes": 10, "workers": 1}, "container": run(),
           "observed": "GET /%2e%2e/secret.txt returned 200 with the file outside public/"}
    rep.update(over)
    return rep


def repaired(**over):
    rep = reproduced(label="repair-tested", repairs=[
        {"candidate": "commonpath guard in resolve", "patch_sha256": SHA, "result": "fixed", "scratch_copy": True,
         "run": run(exit=1)}])
    rep.update(over)
    return rep


class LabelTests(Fixture):
    def ok(self, rep):
        self.assertEqual(codes(self.check(record(confirmed(reproduction=rep)))), set())

    def test_static_reproduced_and_repair_tested_records_pass(self):
        self.ok({"label": "static"})
        self.ok(reproduced())
        self.ok(repaired())

    def test_reproduced_needs_the_container_receipt(self):
        rep = reproduced(container={"image": "westack-repro-traversal"})
        self.assertCaught(record(confirmed(reproduction=rep)), "reproduced-without-container", off("missing"))

    def test_reproduced_needs_an_observation_and_a_budget(self):
        self.assertCaught(record(confirmed(reproduction=reproduced(observed=""))), "reproduced-without-observation",
                          off('not _text(rep.get("observed"))'))
        self.assertCaught(record(confirmed(reproduction=reproduced(budget={"minutes": 10}))), "reproduction-unbudgeted",
                          ("if not (isinstance(budget.get(\"minutes\")", "if False and (isinstance(budget.get(\"minutes\")"))

    def test_a_networked_container_needs_its_grant(self):
        rep = reproduced(container=run(network="bridge"))
        self.assertCaught(record(confirmed(reproduction=rep)), "reproduction-network-ungranted",
                          ('elif rep["container"].get("network") != "none"', 'elif False'))
        self.ok(dict(rep, network_grant="the user, 2026-11-04: pull python:3.12-slim"))

    def test_repair_tested_needs_one_to_three_tried_repairs(self):
        self.assertCaught(record(confirmed(reproduction=repaired(repairs=[]))), "repair-tested-without-repairs",
                          off("not isinstance(repairs, list) or not repairs"))
        four = repaired()["repairs"] * 4
        self.assertCaught(record(confirmed(reproduction=repaired(repairs=four))), "too-many-repairs",
                          off("len(repairs) > MAX_REPAIRS"))
        untried = [dict(repaired()["repairs"][0], run={"image": "x"})]
        self.assertCaught(record(confirmed(reproduction=repaired(repairs=untried))), "repair-untested",
                          off('_run_receipt_missing(r.get("run"))'))
        on_tree = [dict(repaired()["repairs"][0], scratch_copy=False)]
        self.assertIn("repair-malformed", codes(self.check(record(confirmed(reproduction=repaired(repairs=on_tree))))))

    def test_only_a_confirmed_finding_is_reproduced(self):
        rec = {"id": "F2", "state": "needs-review", "claim": "Maybe a traversal.", "rule": "path.traversal",
               "anchor": "app.py::resolve", "missing_fact": "whether BASE is enforced", "reproduction": reproduced()}
        self.assertCaught(record(rec), "reproduction-unconfirmed",
                          off('"reproduction" in rec and state != "confirmed"'))

    def test_the_report_carries_the_label(self):
        data = record(confirmed(reproduction=repaired()))
        checked, text = sa.render(data, "0" * 64, str(self.root))
        self.assertIsNotNone(text, checked)
        self.assertIn("Reproduction: repair-tested in westack-repro-traversal (exit 0, network none)", text)
        self.assertIn("repairs: commonpath guard in resolve fixed", text)


def load_app(folder, name):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(folder) / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch(app_module, path):
    server = app_module.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8", errors="replace")
    finally:
        server.shutdown()
        server.server_close()


REPAIR = ("    return os.path.join(BASE, unquote(raw_path.split(\"?\", 1)[0]).lstrip(\"/\"))\n",
          "    target = os.path.realpath(os.path.join(BASE, unquote(raw_path.split(\"?\", 1)[0]).lstrip(\"/\")))\n"
          "    return target if os.path.commonpath([target, os.path.realpath(BASE)]) == os.path.realpath(BASE) else None\n")


class FixtureTests(unittest.TestCase):
    def test_the_planted_traversal_is_real(self):
        app = load_app(FIXTURE, "westack_repro_fixture")
        self.assertEqual(fetch(app, "/hello.txt"), (200, "hello from the public folder\n"))
        status, body = fetch(app, "/%2e%2e/secret.txt")
        self.assertEqual(status, 200)
        self.assertIn("FIXTURE-SECRET", body)

    def test_the_commonpath_repair_closes_it_on_a_scratch_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = pathlib.Path(tmp, "scratch")
            shutil.copytree(FIXTURE, scratch, ignore=shutil.ignore_patterns("__pycache__"))
            source = (scratch / "app.py").read_text(encoding="utf-8")
            self.assertEqual(source.count(REPAIR[0]), 1)
            (scratch / "app.py").write_text(source.replace(*REPAIR), encoding="utf-8")
            app = load_app(scratch, "westack_repro_repaired")
            self.assertEqual(fetch(app, "/%2e%2e/secret.txt")[0], 404)
            self.assertEqual(fetch(app, "/hello.txt")[0], 200)
        self.assertEqual((FIXTURE / "app.py").read_text(encoding="utf-8"), source, "the fixture itself is untouched")


if __name__ == "__main__":
    unittest.main()
