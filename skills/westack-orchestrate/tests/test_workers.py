"""Tests for westack-orchestrate's workers.py: the dispatch-plan, return and ledger checker.

Run from the repo root:  python -B -m unittest discover -s skills/westack-orchestrate/tests -v
WORKERS_UNDER_TEST=<path> points the suite at another copy (a broken-copy control). Each check below is also run
against a copy of the script with that one check removed, and must fail there.
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("WORKERS_UNDER_TEST") or HERE.parent / "scripts" / "workers.py")
CORE = HERE.parent.parent / "westack"


def load(path=SCRIPT, name="westack_orchestrate_workers_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wk = load()


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def codes(report, worker=None):
    return {f["code"] for f in report.get("findings", []) if worker is None or f.get("worker") == worker}


def broken(*edits):
    """A copy of the script with each (old, new) edit applied once: the check under test removed."""
    source = SCRIPT.read_text(encoding="utf-8")
    for old, new in edits:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    temp = tempfile.TemporaryDirectory(prefix="westack-workers-broken-")
    path = pathlib.Path(temp.name) / "workers_broken.py"
    path.write_text(source, encoding="utf-8")
    module = load(path, "westack_orchestrate_workers_broken_" + sha(repr(edits))[:12])
    module.temp = temp
    return module


def body(wid, items=("D1: the unit tests for the module pass (source: user run the tests)",
                     "D2: the change is described in the report (source: plan S2)")):
    return ("# Brief: %s\n\nPurpose: change the module named in scope.\n\nScope: do only this.\n\n## Done when\n%s\n\n"
            "## Return\nWrite runs/%s/report.md and end it with the line END-OF-REPORT %s.\n"
            % (wid, "\n".join("- " + item for item in items), wid, wid))


class Fixture(unittest.TestCase):
    """Three workers: w1 and w2 write disjoint folders, w3 is a read-only search worker."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-workers-")
        self.root = pathlib.Path(self.temp.name)
        self.headers = {
            "w1": {"worker": "w1", "tier": "mid", "wait": "report", "tools": "Read, Grep, Edit", "cap": "40 turns",
                   "writes": "src/alpha/", "history": "the assignment only", "kind": "build"},
            "w2": {"worker": "w2", "tier": "mid", "wait": "handle", "tools": "Read, Edit", "cap": "30 minutes",
                   "writes": "src/beta/", "history": "the assignment only", "kind": "build"},
            "w3": {"worker": "w3", "tier": "small", "wait": "report", "tools": "Read, Grep", "cap": "20 turns",
                   "writes": "none", "history": "the assignment plus the last step, quoted as earlier work",
                   "kind": "search"},
        }
        self.bodies = {wid: body(wid) for wid in self.headers}
        self.dispatch = {
            "format": "westack-dispatch-1", "mode": "workers", "why": "user: run the three tickets as parallel workers",
            "fan_out": "three independent pieces with no shared files",
            "coordinator": {"tools": ["Read", "Grep", "Glob", "Edit", "PowerShell", "Agent"]},
            "runs": "runs",
            "workers": [{"id": wid, "brief": "briefs/%s.md" % wid} for wid in self.headers],
        }

    def tearDown(self):
        self.temp.cleanup()

    # ---- writing the fixture -------------------------------------------------------------------------------------
    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        return path

    def save(self):
        for wid, header in self.headers.items():
            lines = ["---"] + ["%s: %s" % (k, v) for k, v in header.items() if v is not None] + ["---", ""]
            self.write("briefs/%s.md" % wid, "\n".join(lines) + self.bodies[wid])
        self.write("dispatch.json", json.dumps(self.dispatch, indent=2))
        return self.root / "dispatch.json"

    def plan(self, module=None):
        return (module or wk).check_plan(self.save(), core=CORE)

    def started(self):
        for number, worker in enumerate(self.dispatch["workers"]):
            worker["handle"] = "agent-%d" % number

    def report(self, wid, items=None, files=None, marker=True, plan=None, extra="", commit=None):
        items = {"D1": "done: python -m unittest, exit 0, 3 passed", "D2": "done: see the patch"} if items is None else items
        lines = ["# Report: " + wid]
        if plan:
            lines.append("plan: " + plan)
        if commit:
            lines.append("commit: " + commit)
        lines += ["", "## Done when"] + ["- %s: %s" % (key, value) for key, value in items.items()]
        if files is None:
            files = []
            if self.headers[wid]["writes"] != "none":
                data = "patch for %s\n" % wid
                self.write("runs/%s/change.patch" % wid, data)
                files = [("runs/%s/change.patch" % wid, sha(data))]
        lines += ["", "## Files"] + ["- %s %s" % pair for pair in files]
        if self.headers[wid].get("kind") == "search" and "## Found" not in extra:
            extra = "## Found\n- billing calls in src/alpha\n\n## Searched, nothing found\n- src/gamma\n\n## Not searched\n- vendor/\n" + extra
        lines += ["", extra]
        if marker:
            lines += ["", "END-OF-REPORT " + wid]
        self.write("runs/%s/report.md" % wid, "\n".join(lines) + "\n")

    def all_reports(self):
        for wid in self.headers:
            self.report(wid)

    def collect(self, module=None, record=None):
        return (module or wk).collect(self.save(), record=record, core=CORE)


# ---- plan: a clean plan ---------------------------------------------------------------------------------------------
class CleanPlanTests(Fixture):
    def test_a_clean_plan_has_no_findings(self):
        report = self.plan()
        self.assertEqual((report["status"], report["findings"]), ("clean", []), report)
        self.assertEqual(report["format"], "westack-workers-1")

    def test_the_cli_prints_json_and_exits_0_clean_1_findings_2_unreadable(self):
        path = self.save()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(wk.main(["plan", str(path), "--core", str(CORE)]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "clean")
        del self.headers["w1"]["cap"]
        path = self.save()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(wk.main(["plan", str(path), "--core", str(CORE)]), 1)
        self.write("dispatch.json", "{not json")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(wk.main(["plan", str(path), "--core", str(CORE)]), 2)
        self.write("dispatch.json", json.dumps({"format": "something-else"}))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(wk.main(["plan", str(path), "--core", str(CORE)]), 2)


# ---- plan: each check, then its broken copy -------------------------------------------------------------------------
class BriefFieldTests(Fixture):
    # The check functions loop without subTest: a subTest would record a broken copy's failure and swallow it.
    def check_fields(self, module):
        for key in ("tools", "cap", "tier", "wait", "history", "writes"):
            saved = self.headers["w2"].pop(key)
            found = [f for f in self.plan(module)["findings"] if f["code"] == "field-missing"]
            self.assertTrue(any(f["worker"] == "w2" and key in f["detail"] for f in found), (key, found))
            self.headers["w2"][key] = saved

    def test_a_brief_must_name_tools_a_cap_a_tier_a_wait_mode_its_writes_and_its_history(self):
        self.check_fields(wk)

    def test_a_copy_without_the_field_check_fails(self):
        module = broken(('            findings.append(finding("field-missing", wid, "the brief header has no " + key))',
                         "            pass"))
        with self.assertRaises(AssertionError):
            self.check_fields(module)
        module.temp.cleanup()

    def check_values(self, module):
        for key, value, code in (("tier", "huge", "bad-tier"), ("wait", "sometimes", "bad-wait"),
                                 ("cap", "a while", "bad-cap")):
            saved = self.headers["w1"][key]
            self.headers["w1"][key] = value
            self.assertIn(code, codes(self.plan(module), "w1"), key)
            self.headers["w1"][key] = saved

    def test_tier_is_read_from_the_contract_and_wait_and_cap_have_fixed_forms(self):
        self.check_values(wk)
        self.assertIn("top", wk.tiers(wk.load_core(CORE)))

    def test_a_copy_that_accepts_any_tier_wait_or_cap_fails(self):
        module = broken(('if header.get("tier") and header["tier"] not in tiers:', "if False:"),
                        ('if header.get("wait") and header["wait"] not in WAITS:', "if False:"),
                        ('if header.get("cap") and not CAP.search(header["cap"]):', "if False:"))
        with self.assertRaises(AssertionError):
            self.check_values(module)
        module.temp.cleanup()

    def check_tools(self, module):
        self.headers["w1"]["tools"] = "Read, Edit, WebFetch"
        found = [f for f in self.plan(module)["findings"] if f["code"] == "tool-not-held"]
        self.assertEqual([(f["worker"], "WebFetch" in f["detail"]) for f in found], [("w1", True)])
        self.headers["w1"]["tools"] = "Read, Edit"
        self.headers["w1"]["removed"] = "Edit"
        self.assertIn("tool-conflict", codes(self.plan(module), "w1"))

    def test_a_brief_cannot_hold_a_tool_the_coordinator_lacks(self):
        self.check_tools(wk)

    def test_a_copy_without_the_subset_check_fails(self):
        module = broken(("if tool.lower() not in held:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_tools(module)
        module.temp.cleanup()


class PlaceholderTests(Fixture):
    def check_placeholders(self, module):
        self.bodies["w2"] = body("w2") + "\nRead {{spec}} first, then <file path>.\nTODO: say which tests.\n"
        found = [f for f in self.plan(module)["findings"] if f["code"] == "placeholder"]
        self.assertEqual({f["worker"] for f in found}, {"w2"})
        text = " ".join(f["detail"] for f in found)
        for token in ("{{spec}}", "<file path>", "TODO"):
            self.assertIn(token, text)
        self.headers["w3"]["plan"] = "docs/plan.md <sha256>"
        self.assertIn("placeholder", codes(self.plan(module), "w3"))

    def test_an_unfilled_placeholder_blocks_the_dispatch(self):
        self.check_placeholders(wk)

    def test_code_generics_and_lowercase_todo_words_are_not_placeholders(self):
        self.bodies["w1"] = body("w1") + "\nThe parser returns List<String>; keep a todo list in your head.\n"
        self.assertNotIn("placeholder", codes(self.plan()))

    def test_a_copy_without_the_placeholder_scan_fails(self):
        module = broken(("for match in PLACEHOLDER.finditer(line):", "for match in []:"))
        with self.assertRaises(AssertionError):
            self.check_placeholders(module)
        module.temp.cleanup()


class DoneWhenAndMarkerTests(Fixture):
    def check_done_when(self, module):
        self.bodies["w1"] = body("w1").replace("## Done when", "## Notes")
        self.assertIn("no-done-when", codes(self.plan(module), "w1"))
        self.bodies["w1"] = body("w1").replace("END-OF-REPORT w1", "the end marker")
        self.assertIn("no-end-marker", codes(self.plan(module), "w1"))
        self.bodies["w1"] = body("w1", items=("D1: one", "D1: two"))
        self.assertIn("duplicate-item", codes(self.plan(module), "w1"))

    def test_a_brief_has_an_itemised_done_when_list_and_names_its_end_marker(self):
        self.check_done_when(wk)

    def test_a_copy_without_the_done_when_check_fails(self):
        module = broken(('findings.append(finding("no-done-when", wid,', 'findings.append(finding("ok", wid,'))
        with self.assertRaises(AssertionError):
            self.check_done_when(module)
        module.temp.cleanup()


class InputTests(Fixture):
    def check_inputs(self, module):
        spec = self.write("docs/spec.md", "the spec\n")
        self.headers["w1"]["inputs"] = "docs/spec.md " + sha("the spec\n")
        self.assertNotIn("input-changed", codes(self.plan(module)))
        spec.write_text("the spec, edited\n", encoding="utf-8")
        self.assertIn("input-changed", codes(self.plan(module), "w1"))
        self.headers["w1"]["inputs"] = "docs/missing.md " + sha("x")
        self.assertIn("input-missing", codes(self.plan(module), "w1"))
        self.headers["w1"]["inputs"] = "docs/spec.md"
        self.assertIn("input-unhashed", codes(self.plan(module), "w1"))

    def test_a_declared_input_must_exist_with_its_stated_hash(self):
        self.check_inputs(wk)

    def test_a_copy_that_skips_the_input_hash_fails(self):
        module = broken(("if digest(source) != expected:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_inputs(module)
        module.temp.cleanup()


class WritesTests(Fixture):
    def check_overlap(self, module):
        self.headers["w2"]["writes"] = "src/alpha/billing.py"
        found = [f for f in self.plan(module)["findings"] if f["code"] == "writes-overlap"]
        self.assertEqual(len(found), 1, found)
        self.assertIn("w1", found[0]["detail"])
        self.assertEqual(found[0]["worker"], "w2")
        for value in ("src/*.py", "runs/w1/notes.md", "."):
            self.headers["w2"]["writes"] = value
            self.assertIn("writes-overlap", codes(self.plan(module)), value)

    def test_writers_must_declare_disjoint_paths(self):
        self.check_overlap(wk)
        self.headers["w2"]["writes"] = "src/beta/, docs/beta.md"
        self.assertNotIn("writes-overlap", codes(self.plan()))

    def test_an_undeclared_or_unportable_write_is_not_conflict_free(self):
        del self.headers["w2"]["writes"]
        self.assertIn("field-missing", codes(self.plan(), "w2"))
        self.headers["w2"]["writes"] = ""
        self.assertIn("writes-undeclared", codes(self.plan(), "w2"))
        for value in ("../outside", "C:/abs/path", "/abs"):
            with self.subTest(writes=value):
                self.headers["w2"]["writes"] = value
                self.assertIn("writes-not-portable", codes(self.plan(), "w2"))

    def test_a_copy_without_the_overlap_check_fails(self):
        module = broken(("if overlaps(mine, theirs):", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_overlap(module)
        module.temp.cleanup()


class ClockTests(Fixture):
    def check_clocks(self, module):
        self.headers["w1"].update(start_by="2026-10-30T11:00:00Z", deadline_at="2026-10-30T09:00:00Z")
        self.assertIn("clock-order", codes(self.plan(module), "w1"))
        self.headers["w1"].update(start_by="2026-10-30T09:00:00", deadline_at="2026-10-30T11:00:00Z")
        self.assertIn("clock-format", codes(self.plan(module), "w1"))
        self.headers["w1"].update(start_by="2026-10-30T09:00:00Z", deadline_at="2026-10-30T11:00:00Z")
        self.assertFalse(codes(self.plan(module), "w1") & {"clock-order", "clock-format"})

    def test_the_deadline_is_absolute_and_after_the_start(self):
        self.check_clocks(wk)

    def test_a_copy_without_the_order_check_fails(self):
        module = broken(('if len(times) == 2 and times["deadline_at"] <= times["start_by"]:', "if False:"))
        with self.assertRaises(AssertionError):
            self.check_clocks(module)
        module.temp.cleanup()


class PlanStampTests(Fixture):
    def check_stamp(self, module):
        text = "# Plan\n\n### S1: alpha\n"
        self.write("docs/plan.md", text)
        self.dispatch["plan"] = {"path": "docs/plan.md", "sha256": sha(text)}
        for wid in self.headers:
            self.headers[wid]["plan"] = "docs/plan.md " + sha(text)
        self.assertFalse(codes(self.plan(module)) & {"plan-stamp", "plan-moved"})
        self.headers["w2"]["plan"] = "docs/plan.md " + sha("an older plan")
        self.assertIn("plan-stamp", codes(self.plan(module), "w2"))
        self.headers["w2"]["plan"] = "docs/plan.md " + sha(text)
        self.write("docs/plan.md", text + "### S2: beta\n")
        self.assertIn("plan-moved", codes(self.plan(module)))

    def test_every_brief_echoes_the_plan_hash_and_the_plan_has_not_moved(self):
        self.check_stamp(wk)

    def test_a_copy_without_the_stamp_check_fails(self):
        module = broken(("if stamp != expected:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_stamp(module)
        module.temp.cleanup()


class ModeAndCapTests(Fixture):
    def check_reasons(self, module):
        self.dispatch["fan_out"] = ""
        self.assertIn("no-reason", codes(self.plan(module)))
        self.dispatch["fan_out"] = "three independent pieces"
        self.dispatch["why"] = ""
        self.assertIn("no-reason", codes(self.plan(module)))
        self.dispatch["why"] = "the host has no subagent tool"
        self.dispatch["mode"] = "inline"
        self.assertIn("mode-mismatch", codes(self.plan(module)))
        for worker in self.dispatch["workers"]:
            worker["ran"] = "inline"
        self.assertNotIn("mode-mismatch", codes(self.plan(module)))

    def test_workers_need_the_users_ask_and_a_fan_out_reason_and_inline_is_labelled(self):
        self.check_reasons(wk)

    def test_a_copy_without_the_reason_check_fails(self):
        module = broken(('if mode == "workers" and not text(data.get("fan_out")):', "if False:"),
                        ('if not text(data.get("why")):', "if False:"))
        with self.assertRaises(AssertionError):
            self.check_reasons(module)
        module.temp.cleanup()

    def add_workers(self, count):
        for number in range(4, 4 + count):
            wid = "w%d" % number
            self.headers[wid] = dict(self.headers["w3"], worker=wid)
            self.bodies[wid] = body(wid)
            self.dispatch["workers"].append({"id": wid, "brief": "briefs/%s.md" % wid})

    def check_cap(self, module):
        self.add_workers(5)  # eight workers
        self.assertIn("too-many-workers", codes(self.plan(module)))
        self.dispatch["max_workers"] = 9
        self.assertIn("cap-without-reason", codes(self.plan(module)))
        self.dispatch["cap_reason"] = "eight disjoint packages, each small"
        self.assertFalse(codes(self.plan(module)) & {"too-many-workers", "cap-without-reason"})

    def test_about_seven_workers_report_to_one_coordinator(self):
        self.check_cap(wk)

    def test_a_copy_without_the_cap_fails(self):
        module = broken(("if started > limit:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_cap(module)
        module.temp.cleanup()

    def check_budget(self, module):
        self.dispatch["budget"] = {"limit": "5 USD"}
        self.assertIn("budget-checks", codes(self.plan(module)))
        self.dispatch["budget"] = {"limit": "5 USD", "checks": "the unit suite and one review per return"}
        self.assertNotIn("budget-checks", codes(self.plan(module)))

    def test_a_budget_reserves_the_checking_first(self):
        self.check_budget(wk)

    def test_a_copy_without_the_budget_check_fails(self):
        module = broken(('if not isinstance(budget, dict) or not text(budget.get("checks")):', "if False:"))
        with self.assertRaises(AssertionError):
            self.check_budget(module)
        module.temp.cleanup()


class IdTests(Fixture):
    def test_ids_are_plain_unique_and_match_the_brief(self):
        self.dispatch["workers"][1]["id"] = "w 2"
        self.headers["w2"]["worker"] = "w 2"
        self.assertIn("bad-id", codes(self.plan()))
        self.dispatch["workers"][1]["id"] = "w1"
        self.assertIn("duplicate-id", codes(self.plan()))
        self.dispatch["workers"][1]["id"] = "w2"
        self.headers["w2"]["worker"] = "w9"
        self.assertIn("id-mismatch", codes(self.plan(), "w2"))

    def test_without_the_core_the_contract_checks_are_reported_not_run(self):
        report = wk.check_plan(self.save(), core=self.root / "no-core-here")
        self.assertEqual(report["status"], "clean")
        self.assertTrue(any("core" in note and "not checked" in note for note in report["notes"]), report["notes"])

    def test_an_unreadable_brief_is_a_finding(self):
        self.dispatch["workers"][0]["brief"] = "briefs/missing.md"
        self.assertIn("brief-unreadable", codes(self.plan(), "w1"))


# ---- collect -------------------------------------------------------------------------------------------------------
class HandleTests(Fixture):
    def check_refusal(self, module):
        self.started()
        del self.dispatch["workers"][2]["handle"]
        self.all_reports()
        report = self.collect(module)
        self.assertEqual(report["status"], "refused")
        self.assertEqual([(f["code"], f["worker"]) for f in report["findings"]], [("missing-handle", "w3")])
        self.assertEqual(report["workers"], {})

    def test_collect_refuses_the_set_when_a_start_handle_is_missing(self):
        self.check_refusal(wk)

    def test_a_copy_that_collects_anyway_fails(self):
        module = broken(("if missing:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_refusal(module)
        module.temp.cleanup()

    def test_work_the_coordinator_did_itself_is_labelled_inline_and_needs_no_handle(self):
        self.started()
        del self.dispatch["workers"][2]["handle"]
        self.dispatch["workers"][2]["ran"] = "inline"
        self.report("w1")
        self.report("w2")
        report = self.collect()
        self.assertEqual(report["workers"]["w3"]["state"], "inline")
        self.assertEqual(report["batch"], "model-reported")


class ReturnTests(Fixture):
    def setUp(self):
        super().setUp()
        self.started()

    def test_whole_returns_are_complete_and_model_reported(self):
        self.all_reports()
        report = self.collect()
        self.assertEqual({w: (v["state"], v["claim"]) for w, v in report["workers"].items()},
                         {w: ("complete", "model-reported") for w in ("w1", "w2", "w3")})
        self.assertEqual((report["batch"], report["status"]), ("model-reported", "clean"))
        self.assertEqual(report["workers"]["w1"]["items"], {"D1": "done", "D2": "done"})
        self.assertRegex(report["workers"]["w1"]["report_sha256"], "^[0-9a-f]{64}$")

    def check_marker(self, module):
        self.all_reports()
        self.report("w2", marker=False)
        report = self.collect(module)
        self.assertEqual(report["workers"]["w2"]["state"], "partial")
        self.assertIn("no-end-marker", codes(report, "w2"))
        self.assertEqual(report["batch"], "partial")

    def test_a_return_without_its_end_marker_is_partial(self):
        self.check_marker(wk)

    def test_a_copy_that_skips_the_marker_check_fails(self):
        module = broken(("if not lines or lines[-1] != marker:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_marker(module)
        module.temp.cleanup()

    def check_items(self, module):
        self.all_reports()
        self.report("w1", items={"D1": "done: ran the tests"})
        self.assertIn("unanswered-item", codes(self.collect(module), "w1"))
        self.report("w1", items={"D1": "done: ran the tests", "D2": "could not"})
        self.assertIn("no-reason", codes(self.collect(module), "w1"))
        self.report("w1", items={"D1": "done: ran the tests", "D2": "could not: the network was removed"})
        report = self.collect(module)
        self.assertEqual(report["workers"]["w1"]["state"], "complete")
        self.assertEqual(report["workers"]["w1"]["items"]["D2"], "could not")

    def test_every_done_when_item_is_answered_and_could_not_gives_a_reason(self):
        self.check_items(wk)

    def test_a_copy_that_skips_the_checklist_fails(self):
        module = broken(("for item in missing_items:", "for item in []:"))
        with self.assertRaises(AssertionError):
            self.check_items(module)
        module.temp.cleanup()

    def check_files(self, module):
        self.all_reports()
        self.write("runs/w1/change.patch", "a different patch\n")
        self.assertIn("file-hash", codes(self.collect(module), "w1"))
        self.assertEqual(self.collect(module)["workers"]["w1"]["state"], "rejected")
        for path in ("runs/w2/notes.md", "runs/w1/*.patch", "runs/w1/.env", "runs/w1/deploy.pem", "../w1.patch"):
            self.report("w1", files=[(path, sha("x"))])
            self.assertIn("file-not-allowed", codes(self.collect(module), "w1"), path)
        self.report("w1", files=[("runs/w1/gone.patch", sha("x"))])
        self.assertIn("file-missing", codes(self.collect(module), "w1"))

    def test_returned_files_are_named_in_the_workers_folder_and_match_their_hash(self):
        self.check_files(wk)

    def test_a_copy_without_the_hash_comparison_fails(self):
        module = broken(("if digest(target) != expected:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_files(module)
        module.temp.cleanup()

    def test_a_copy_that_accepts_any_returned_path_fails(self):
        module = broken(("if not allowed_file(path, folder):", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_files(module)
        module.temp.cleanup()

    def test_a_return_whose_brief_cannot_be_read_is_never_complete(self):
        self.all_reports()
        self.save()
        (self.root / "briefs" / "w1.md").unlink()
        report = wk.collect(self.root / "dispatch.json", core=CORE)
        self.assertIn("brief-unreadable", codes(report, "w1"))
        self.assertEqual(report["workers"]["w1"]["state"], "partial")

    def test_a_writer_that_names_no_artifact_is_unreported(self):
        self.all_reports()
        self.report("w2", files=[])
        self.assertIn("no-artifact", codes(self.collect(), "w2"))
        self.report("w2", files=[], commit="a" * 40)
        self.assertNotIn("no-artifact", codes(self.collect(), "w2"))

    def check_search(self, module):
        self.all_reports()
        self.report("w3", extra="## Found\n- billing calls in src/alpha\n")
        report = self.collect(module)
        self.assertIn("search-lists", codes(report, "w3"))
        self.assertEqual(report["workers"]["w3"]["state"], "partial")

    def test_a_search_return_needs_found_searched_and_not_searched(self):
        self.check_search(wk)

    def test_a_copy_without_the_three_lists_check_fails(self):
        module = broken(('if kind == "search" and not all(', 'if False and not all('))
        with self.assertRaises(AssertionError):
            self.check_search(module)
        module.temp.cleanup()

    def check_stale(self, module):
        text = "# Plan\n"
        self.write("docs/plan.md", text)
        self.dispatch["plan"] = {"path": "docs/plan.md", "sha256": sha(text)}
        for wid in self.headers:
            self.report(wid, plan="docs/plan.md " + sha(text))
        self.report("w2", plan="docs/plan.md " + sha("an older plan"))
        report = self.collect(module)
        self.assertEqual(report["workers"]["w2"]["state"], "stale")
        self.assertEqual(report["workers"]["w1"]["state"], "complete")
        self.report("w1")  # no plan line at all
        self.assertIn("no-plan-echo", codes(self.collect(module), "w1"))

    def test_a_report_built_on_another_plan_hash_is_stale(self):
        self.check_stale(wk)

    def test_a_copy_without_the_echo_check_fails(self):
        module = broken(("if echoed != expected:", "if False:"))
        with self.assertRaises(AssertionError):
            self.check_stale(module)
        module.temp.cleanup()


class RollupTests(Fixture):
    def check_rollup(self, module):
        self.started()
        self.all_reports()
        self.report("w2", marker=False)  # partial
        self.write("runs/w1/change.patch", "tampered\n")  # rejected
        self.assertEqual(self.collect(module)["batch"], "rejected")
        (self.root / "runs" / "w3" / "report.md").unlink()  # missing
        self.assertEqual(self.collect(module)["batch"], "missing")
        self.dispatch["workers"] = []
        report = self.collect(module)
        self.assertEqual((report["batch"], report["status"]), ("inconclusive", "findings"))

    def test_the_batch_takes_its_worst_state_and_an_empty_batch_is_inconclusive(self):
        self.check_rollup(wk)

    def test_a_copy_that_marks_an_empty_batch_complete_fails(self):
        module = broken(('batch = "inconclusive" if not states else', 'batch = "settled" if not states else'))
        with self.assertRaises(AssertionError):
            self.check_rollup(module)
        module.temp.cleanup()

    def test_a_copy_that_takes_the_best_state_fails(self):
        module = broken(("min(states, key=ORDER.index)", "max(states, key=ORDER.index)"))
        with self.assertRaises(AssertionError):
            self.check_rollup(module)
        module.temp.cleanup()


class WakeTests(Fixture):
    """A wake-up is a signal: every call reads every worker, so two returns that land together are both handled."""

    def check_reads_all(self, module):
        self.started()
        report = self.collect(module)
        self.assertEqual((report["returned"], report["in_flight"]), ([], ["w1", "w2", "w3"]))
        self.report("w1")
        self.report("w3")  # two finish while the first is being read
        report = self.collect(module)
        self.assertEqual(report["returned"], ["w1", "w3"])
        self.assertEqual(report["in_flight"], ["w2"])
        self.report("w2")
        self.assertEqual(self.collect(module)["in_flight"], [])

    def test_each_call_reads_every_worker_not_only_the_first_new_return(self):
        self.check_reads_all(wk)

    def test_a_copy_that_stops_at_the_first_new_return_fails(self):
        module = broken(("            returned.append(wid)", "            returned.append(wid)\n            break"))
        with self.assertRaises(AssertionError):
            self.check_reads_all(module)
        module.temp.cleanup()


# ---- the task record: settling and the ledger ----------------------------------------------------------------------
class RecordFixture(Fixture):
    def setUp(self):
        super().setUp()
        self.task = json.loads((CORE / "examples" / "task.json").read_text(encoding="utf-8"))
        self.task["delegates"] = [self.entry(wid) for wid in self.headers]

    def entry(self, wid, **changes):
        item = dict(id=wid, parent=self.task["id"], executor="host subagent", tier="mid", scope="briefs/%s.md" % wid,
                    status="finished", continuable=False, outcome={"disposition": "landed", "ref": "runs/%s/report.md" % wid})
        item.update(changes)
        return item

    def save_task(self):
        path = self.root / "task.0002.json"
        path.write_text(json.dumps(self.task, indent=2), encoding="utf-8")
        return path

    def ledger(self, module=None, dispatch=False, core=CORE):
        return (module or wk).check_ledger(self.save_task(), dispatch=self.save() if dispatch else None, core=core)


class SettleTests(RecordFixture):
    def check_settled(self, module):
        self.started()
        self.all_reports()
        receipt = copy.deepcopy(self.task["evidence"][0])
        receipt.update(id="e-w1", claim_id="w1")
        self.task["evidence"].append(receipt)
        other = copy.deepcopy(receipt)
        other.update(id="e-w2", claim_id="a1", status="failed")
        self.task["evidence"].append(other)
        report = self.collect(module, record=self.save_task())
        self.assertEqual(report["workers"]["w1"]["claim"], "settled")
        self.assertEqual(report["workers"]["w1"]["receipts"], ["e-w1"])
        self.assertEqual(report["workers"]["w2"]["claim"], "model-reported")
        self.assertEqual(report["batch"], "model-reported")

    def test_a_complete_return_is_settled_only_by_a_passing_current_receipt_naming_the_worker(self):
        self.check_settled(wk)

    def test_a_receipt_for_another_patch_settles_nothing(self):
        self.started()
        self.all_reports()
        receipt = copy.deepcopy(self.task["evidence"][0])
        receipt.update(id="e-w1", claim_id="w1", patch_id="0" * 64)
        self.task["evidence"].append(receipt)
        self.assertEqual(self.collect(record=self.save_task())["workers"]["w1"]["claim"], "model-reported")

    def test_a_copy_that_settles_every_complete_return_fails(self):
        module = broken(('claim = "settled" if receipts else "model-reported"', 'claim = "settled"'))
        with self.assertRaises(AssertionError):
            self.check_settled(module)
        module.temp.cleanup()


class LedgerTests(RecordFixture):
    def test_a_closed_ledger_is_clean(self):
        report = self.ledger(dispatch=True)
        self.assertEqual((report["status"], report["findings"]), ("clean", []), report)

    def check_open(self, module):
        self.task["delegates"][1] = self.entry("w2", status="running")
        del self.task["delegates"][1]["outcome"]
        report = self.ledger(module)
        found = [f for f in report["findings"] if f["code"] == "ledger"]
        self.assertTrue(any("w2: delegate ledger entry still open" in f["detail"] for f in found), report)

    def test_an_open_entry_is_a_finding_from_the_cores_own_checker(self):
        self.check_open(wk)
        self.task["delegates"][1] = self.entry("w2", outcome={"disposition": "landed"})
        self.assertTrue(any("a landed outcome needs a ref" in f["detail"] for f in self.ledger()["findings"]))

    def test_a_copy_that_ignores_the_cores_checker_fails(self):
        module = broken(("for message in record.check_delegates(task, True):", "for message in []:"))
        with self.assertRaises(AssertionError):
            self.check_open(module)
        module.temp.cleanup()

    def check_nested(self, module):
        self.task["delegates"][2] = self.entry("w3", parent="w1")
        self.assertIn("nested-worker", codes(self.ledger(module), "w3"))

    def test_a_worker_whose_parent_is_another_worker_is_a_finding(self):
        self.check_nested(wk)

    def test_a_copy_without_the_depth_check_fails(self):
        module = broken(('if entry["parent"] != task["id"]:', "if False:"))
        with self.assertRaises(AssertionError):
            self.check_nested(module)
        module.temp.cleanup()

    def test_a_dispatched_worker_without_an_entry_and_a_waiting_run_are_findings(self):
        self.started()
        del self.task["delegates"][0]
        self.assertIn("no-ledger-entry", codes(self.ledger(dispatch=True), "w1"))
        self.task["delegates"].insert(0, self.entry("w1"))
        self.task["waiting_on"] = dict(what="the vendor's verdict", check=dict(kind="verdict-posted", target="PR 12"),
                                       next_step="read the verdict", expires_at="2999-01-01T00:00:00Z")
        self.assertIn("still-waiting", codes(self.ledger()))

    def test_a_record_off_the_contract_shape_is_reported_and_nothing_else_is_judged(self):
        self.task["delegates"][0]["tier"] = "huge"
        report = self.ledger()
        self.assertEqual(codes(report), {"contract-shape"})

    def test_without_the_core_the_ledger_check_is_not_run(self):
        report = self.ledger(core=self.root / "no-core-here")
        self.assertEqual(report["status"], "not-run")
        out = io.StringIO()
        with redirect_stdout(out):
            code = wk.main(["ledger", str(self.save_task()), "--core", str(self.root / "no-core-here")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
