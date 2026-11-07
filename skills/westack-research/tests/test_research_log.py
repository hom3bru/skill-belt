"""Tests for westack-research's research_log.py: the search log and claim ledger checker.

Run from the repo root:  python -B -m unittest discover -s skills/westack-research/tests -v
RESEARCH_LOG_UNDER_TEST=<path> points the suite at another copy. Each check is also run against a copy of the script
with that one rule removed (a broken copy): the bad log must get through there, or the test protects nothing.
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("RESEARCH_LOG_UNDER_TEST") or HERE.parent / "scripts" / "research_log.py")
CORE = HERE.parent.parent / "westack"


def load(path=SCRIPT, name="westack_research_log_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rl = load()


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def codes(report, check=None):
    return {f["code"] for f in report.get("findings", []) if check is None or f.get("check") == check}


def broken(*edits):
    """A copy of the script with each (old, new) edit applied once: the rule under test removed."""
    source = SCRIPT.read_text(encoding="utf-8")
    for old, new in edits:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    with tempfile.TemporaryDirectory(prefix="westack-research-broken-") as temp:
        path = pathlib.Path(temp) / "research_log_broken.py"
        path.write_text(source, encoding="utf-8")
        return load(path, "westack_research_log_broken_" + sha(repr(edits))[:12])


def off(condition):
    """The edit that turns one `if <condition>:` into `if False:`."""
    return ("if " + condition + ":", "if False:")


S1 = ("# tidepool 1.6 configuration\n\nSince version 1.6, prepared statements work in transaction mode when "
      "`prepared_cache` is set.\n\nThe default pool size is 20 connections.\n")
S2 = ("<html><body><h1>tidepool 1.4 configuration</h1><p>In transaction mode, prepared statements are "
      "<b>not supported</b> in 1.4.</p></body></html>\n")
S3 = ("Caching Tool Calls for Agents\nAna Rivera, Bo Chen\n\n4 Results\nOn the SWE-style benchmark, caching cut cost "
      "by 16%.\n\n6 Limitations\nWe did not measure latency under load.\n")
S4 = "tidepool 1.6 release notes (a copy)\n\nPrepared statements now work in transaction mode.\n"


class Fixture(unittest.TestCase):
    """A depth-first question with a one-round follow-up cap: four searches, four accepted sources (two primary docs,
    a paper with its two index records, a mirror copy), one rejected tutorial, four claims, three gaps."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-research-")
        self.root = pathlib.Path(self.temp.name)
        self.files = {
            "sources/S1.md": S1, "sources/S2.html": S2, "sources/S3.txt": S3, "sources/S4.md": S4,
            "results/Q1.json": json.dumps([
                {"title": "tidepool 1.6 configuration", "url": "https://tidepool.example/docs/1.6/config"},
                {"title": "tidepool 1.6 release notes", "url": "https://tidepool.example/releases/1.6"}]),
            "results/Q2.json": json.dumps({"results": [
                {"id": "W123", "arxiv": "2409.01234", "title": "Caching Tool Calls for Agents"}]}),
            "results/Q3.json": json.dumps([]),
            "results/Q4.json": json.dumps([
                {"title": "tidepool 1.4 configuration", "url": "https://tidepool.example/docs/1.4/config"},
                {"title": "Pooling tips", "url": "https://blog.example/pooling"}]),
            "index/arxiv.json": json.dumps({"title": "Caching Tool Calls for Agents", "year": 2024,
                                            "authors": ["Ana Rivera", "Bo Chen"]}),
            "index/openalex.json": json.dumps({"title": "Caching tool calls for agents", "year": 2024,
                                               "first_author": "Rivera, Ana"}),
        }

        def call(at, url, window="any", ranking="relevance"):
            return {"at": at, "url": url, "window": window, "ranking": ranking, "status": "ok", "attempt": 1}

        arxiv_window = "2023-01-01..2026-10-30"
        self.log = {
            "format": "westack-research-log-1",
            "question": "Can the orders API use prepared statements through tidepool in transaction mode?",
            "decision": "keep or drop prepared statements before the pooler migration",
            "depth": "depth-first",
            "follow_up_cap": 1,
            "status": "complete",
            "pacing": {"export.arxiv.org": 3},
            "searches": [
                {"id": "Q1", "round": 0, "query": "tidepool prepared statements transaction mode", "where": "web search",
                 "window": "any", "ranking": "relevance", "results": "results/Q1.json",
                 "calls": [call("2026-10-30T10:00:00Z", "https://search.example/q1")]},
                {"id": "Q2", "round": 0, "query": "tool call caching agents cost", "where": "arXiv API",
                 "window": arxiv_window, "ranking": "relevance", "results": "results/Q2.json",
                 "calls": [call("2026-10-30T10:01:00Z", "https://export.arxiv.org/api/query?page=1", arxiv_window),
                           call("2026-10-30T10:01:04Z", "https://export.arxiv.org/api/query?page=2", arxiv_window)]},
                {"id": "Q3", "round": 0, "query": "tidepool connection limit release notes", "where": "web search",
                 "window": "any", "ranking": "relevance", "results": "results/Q3.json",
                 "calls": [call("2026-10-30T10:03:00Z", "https://search.example/q3")]},
                {"id": "Q4", "round": 1, "gap": "no primary source for the pinned 1.4 behaviour",
                 "query": "tidepool 1.4 configuration", "where": "web search", "window": "any",
                 "ranking": "relevance", "results": "results/Q4.json",
                 "calls": [call("2026-10-30T10:04:00Z", "https://search.example/q4")]},
            ],
            "fetches": [
                {"at": "2026-10-30T10:02:00Z", "url": "https://export.arxiv.org/pdf/2409.01234", "status": "failed",
                 "attempt": 1, "error": "503", "source": "S3"},
                {"at": "2026-10-30T10:02:05Z", "url": "https://export.arxiv.org/pdf/2409.01234", "status": "ok",
                 "attempt": 2, "source": "S3"},
            ],
            "sources": [
                {"id": "S1", "title": "tidepool 1.6 configuration", "url": "https://tidepool.example/docs/1.6/config",
                 "kind": "primary", "version": "1.6.0", "retrieved": "2026-10-30", "saved": "sources/S1.md",
                 "found_by": {"search": "Q1"}, "status": "accepted"},
                {"id": "S2", "title": "tidepool 1.4 configuration", "url": "https://tidepool.example/docs/1.4/config",
                 "kind": "primary", "version": "1.4.2", "retrieved": "2026-10-30", "saved": "sources/S2.html",
                 "found_by": {"search": "Q4"}, "status": "accepted"},
                {"id": "S3", "title": "Caching Tool Calls for Agents", "arxiv": "2409.01234", "year": 2024,
                 "first_author": "Rivera", "kind": "primary", "published": "2024-09-02", "retrieved": "2026-10-30",
                 "saved": "sources/S3.txt", "found_by": {"search": "Q2"}, "status": "accepted",
                 "index_check": {"records": [{"index": "arxiv", "file": "index/arxiv.json"},
                                             {"index": "openalex", "file": "index/openalex.json"}],
                                 "matched": "arxiv"}},
                {"id": "S4", "title": "tidepool 1.6 release notes", "kind": "mirror",
                 "url": "https://copy.example/tidepool-1.6", "original_url": "https://tidepool.example/releases/1.6",
                 "version": "1.6.0", "retrieved": "2026-10-30", "saved": "sources/S4.md",
                 "found_by": {"search": "Q1"}, "status": "accepted"},
                {"id": "S5", "title": "Pooling tips", "url": "https://blog.example/pooling", "kind": "secondary",
                 "found_by": {"search": "Q4"}, "status": "rejected",
                 "reason": "a tutorial written for 1.2; the 1.4 and 1.6 docs supersede it"},
            ],
            "claims": [
                {"id": "C1", "text": "tidepool 1.6.0 supports prepared statements in transaction mode when "
                                     "prepared_cache is set.", "strength": "present",
                 "cites": [{"source": "S1", "location": "line 3", "basis": "read",
                            "excerpt": "Since version 1.6, prepared statements work in transaction mode when "
                                       "`prepared_cache` is set."},
                           {"source": "S4", "location": "line 3", "basis": "read",
                            "excerpt": "Prepared statements now work in transaction mode."}]},
                {"id": "C2", "text": "On 1.4.2, the version this project pins, prepared statements are not supported "
                                     "in transaction mode.", "strength": "present",
                 "cites": [{"source": "S2", "location": "the transaction mode paragraph", "basis": "read",
                            "excerpt": "In transaction mode, prepared statements are not supported in 1.4."}]},
                {"id": "C3", "text": "The paper reports a 16% cost cut on its benchmark.", "strength": "present",
                 "contested": True, "check": "recomputed the paper's results table: receipts/c3.txt",
                 "cites": [{"source": "S3", "location": "section 4", "basis": "read",
                            "excerpt": "On the SWE-style benchmark, caching cut cost by 16%."}]},
                {"id": "C4", "text": "The default pool size is 20 connections.", "strength": "claimed",
                 "cites": [{"source": "S1", "location": "search snippet", "basis": "snippet",
                            "excerpt": "The default pool size is 20 connections."}]},
            ],
            "gaps": [
                {"id": "G1", "text": "The paper did not measure latency under load.", "origin": "stated",
                 "source": "S3", "location": "section 6"},
                {"id": "G2", "text": "Neither the docs nor the paper cover pool behaviour across restarts.",
                 "origin": "inferred", "from": ["S1", "S3"]},
                {"id": "G3", "text": "Caching may interact with prepared_cache.", "origin": "speculative"},
            ],
            "searched_for": [{"text": "No release note states a connection limit.", "queries": ["Q3"]}],
            "delegates": [{"id": "w1", "report": "runs/w1/report.md", "found": ["S2"],
                           "nothing_found": [{"what": "a published benchmark of tidepool", "queries": ["Q3"]}],
                           "not_searched": ["vendor forums"]}],
            "removed": [{"text": "tidepool 1.6 is 40% faster", "why": "only the mirror copy says it"}],
            "not_done": [{"check": "vendor forums", "why": "not searched by w1; forums are not primary"},
                         {"check": "ran tidepool 1.6 locally", "why": "no environment granted"}],
            "spend": {"limit_usd": 1.0, "entries": [
                {"what": "pilot: five pages through a paid crawl", "usd": 0.05, "pilot": True},
                {"what": "bulk: forty pages", "usd": 0.4, "bulk": True}]},
        }

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        return path

    def source(self, sid):
        return next(s for s in self.log["sources"] if s["id"] == sid)

    def claim(self, cid):
        return next(c for c in self.log["claims"] if c["id"] == cid)

    def search(self, qid):
        return next(s for s in self.log["searches"] if s["id"] == qid)

    def save(self, hashes=True):
        for relative, data in self.files.items():
            self.write(relative, data)
        if hashes:
            for source in self.log["sources"]:
                if "saved" in source and "sha256" not in source and source["saved"] in self.files:
                    source["sha256"] = sha(self.files[source["saved"]])
        return self.write("log.json", json.dumps(self.log, indent=2))

    def check_log(self, module=None, record=None, core=CORE):
        return (module or rl).check(self.save(), record=record, core=core)

    def assert_caught(self, code, change, edit, check=None):
        """The changed log is caught with `code`; a copy with `edit` lets it through (the broken-copy control)."""
        change()
        report = self.check_log()
        self.assertIn(code, codes(report, check), report.get("findings"))
        control = self.check_log(broken(edit))
        self.assertNotIn(code, codes(control, check), "the broken copy still catches it, so the test shows nothing")
        return report


# ---- a clean log ----------------------------------------------------------------------------------------------------
class CleanLogTests(Fixture):
    def test_a_clean_log_has_no_findings_and_every_check_ran_or_had_nothing_to_check(self):
        report = self.check_log()
        self.assertEqual(report["findings"], [], report["findings"])
        self.assertEqual(report["status"], "clean")
        self.assertEqual(set(report["checks"]), set(rl.CHECKS))
        for name, status in report["checks"].items():
            self.assertIn(status, {"passed", "not-applicable"}, name)
        self.assertEqual(report["checks"]["record"], "not-applicable")
        self.assertEqual(report["sha256"], sha((self.root / "log.json").read_bytes()))

    def test_the_report_says_what_it_cannot_check(self):
        report = self.check_log()
        text = " ".join(report["not_checked"]).lower()
        for needle in ("paraphrase", "primary", "framework", "relevan", "documentation", "licence file", "includes"):
            self.assertIn(needle, text)

    def test_the_command_line_prints_json_and_exits_0_1_2_or_64(self):
        path = self.save()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(rl.main(["check", str(path), "--core", str(CORE)]), 0)
        self.assertEqual(json.loads(out.getvalue())["format"], rl.FORMAT)
        self.claim("C3")["strength"] = "verified"
        path = self.save()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rl.main(["check", str(path), "--core", str(CORE)]), 1)
        self.write("bad.json", "{not json")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rl.main(["check", str(self.root / "bad.json")]), 2)
        with redirect_stdout(io.StringIO()), open(os.devnull, "w") as sink:
            import contextlib
            with contextlib.redirect_stderr(sink):
                self.assertEqual(rl.main([]), 64)

    def test_it_reads_files_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for module in ("socket", "urllib", "http", "subprocess", "requests", "shutil"):
            self.assertNotRegex(source, r"(?m)^\s*(?:import|from)\s+%s\b" % module)
        self.assertNotRegex(source, r"write_text|write_bytes|open\([^)]*['\"][wa]")


# ---- shape ----------------------------------------------------------------------------------------------------------
class ShapeTests(Fixture):
    def test_another_format_is_unreadable(self):
        self.log["format"] = "westack-dispatch-1"
        report = self.check_log()
        self.assertEqual(report["status"], "unreadable")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rl.main(["check", str(self.root / "log.json")]), 2)

    def test_a_missing_field_and_a_bad_value_are_findings(self):
        del self.log["decision"]
        self.log["depth"] = "deep"
        self.log["follow_up_cap"] = 3
        found = codes(self.check_log(), "shape")
        self.assertIn("field-missing", found)
        self.assertIn("bad-value", found)

    def test_ids_are_unique(self):
        self.log["claims"].append(copy.deepcopy(self.claim("C4")))
        self.assertIn("duplicate-id", codes(self.check_log(), "shape"))

    def test_a_complete_log_with_no_claims_is_not_clean(self):
        def change():
            self.log["claims"] = []
            self.log["gaps"] = []
            for source in self.log["sources"]:
                source["status"] = "rejected"
                source["reason"] = "not needed"
        self.assert_caught("empty-log", change, off('not data.get("claims") and data.get("status") == "complete"'))

    def test_a_blocked_log_with_no_claims_is_a_note_not_a_finding(self):
        self.log["claims"], self.log["gaps"] = [], []
        self.log["status"], self.log["reason"] = "blocked", "every source was behind a login"
        for source in self.log["sources"]:
            source["status"], source["reason"] = "rejected", "behind a login"
        report = self.check_log()
        self.assertNotIn("empty-log", codes(report))
        self.assertTrue(any("blocked" in note for note in report["notes"]))


# ---- OR-1: rounds ---------------------------------------------------------------------------------------------------
class RoundTests(Fixture):
    def test_a_round_past_the_declared_cap_fails(self):
        def change():
            extra = copy.deepcopy(self.search("Q4"))
            extra.update(id="Q5", round=2, query="tidepool prepared_cache default")
            self.log["searches"].append(extra)
        self.assert_caught("round-over-cap", change, off("number > cap"), "rounds")

    def test_the_cap_itself_is_at_most_two(self):
        self.log["follow_up_cap"] = 5
        self.assertIn("bad-value", codes(self.check_log(), "shape"))

    def test_a_follow_up_round_names_its_gap(self):
        self.assert_caught("round-no-gap", lambda: self.search("Q4").pop("gap"),
                           off('number >= 1 and not text(search.get("gap"))'), "rounds")

    def test_a_round_targets_one_gap(self):
        def change():
            extra = copy.deepcopy(self.search("Q4"))
            extra.update(id="Q5", gap="no benchmark of tidepool", query="tidepool benchmark latency")
            self.log["searches"].append(extra)
        self.assert_caught("round-many-gaps", change, off("len(targets) > 1"), "rounds")

    def test_a_repeated_query_is_caught_after_normalisation(self):
        def change():
            extra = copy.deepcopy(self.search("Q4"))
            extra.update(id="Q5", query="Transaction mode: TIDEPOOL prepared statements!")
            self.log["searches"].append(extra)
        self.assert_caught("repeated-query", change, off("key in seen_queries"), "rounds")

    def test_a_paraphrase_is_not_detected_and_the_report_says_so(self):
        extra = copy.deepcopy(self.search("Q4"))
        extra.update(id="Q5", query="pgbouncer-style pooler prepared queries in txn pooling")
        self.log["searches"].append(extra)
        report = self.check_log()
        self.assertNotIn("repeated-query", codes(report))
        self.assertTrue(any("paraphrase" in line for line in report["not_checked"]))


# ---- OR-2: one window and ranking per search ------------------------------------------------------------------------
class WindowTests(Fixture):
    EDIT = off('call.get("window") != search.get("window") or call.get("ranking") != search.get("ranking")')

    def test_a_widened_window_fails(self):
        self.assert_caught("window-changed",
                           lambda: self.search("Q2")["calls"][1].update(window="2015-01-01..2026-10-30"),
                           self.EDIT, "window")

    def test_a_changed_ranking_fails(self):
        self.search("Q2")["calls"][1]["ranking"] = "date"
        self.assertIn("window-changed", codes(self.check_log(), "window"))

    def test_a_logged_query_that_never_ran_fails(self):
        self.search("Q3")["calls"] = []
        self.assertIn("no-calls", codes(self.check_log(), "window"))


# ---- OR-3: cite only what came back ---------------------------------------------------------------------------------
class ResultTests(Fixture):
    def recalled(self):
        self.log["sources"].append(
            {"id": "S6", "title": "Agent Caching at Scale", "arxiv": "2409.01243", "year": 2024, "first_author": "Rivera",
             "kind": "primary", "published": "2024-09-03", "retrieved": "2026-10-30", "saved": "sources/S3.txt",
             "found_by": {"search": "Q2"}, "status": "accepted",
             "index_check": copy.deepcopy(self.source("S3")["index_check"])})
        self.claim("C3")["cites"].append({"source": "S6", "location": "section 4", "basis": "read",
                                          "excerpt": "On the SWE-style benchmark, caching cut cost by 16%."})

    def test_a_recalled_identifier_is_flagged(self):
        self.assert_caught("recalled", self.recalled,
                           off("not any(same_work(source, result) for result in found)"), "results")

    def test_a_source_with_no_found_by_is_recalled(self):
        self.source("S1").pop("found_by")
        self.assertIn("recalled", codes(self.check_log(), "results"))

    def test_a_given_or_linked_source_needs_no_search(self):
        self.source("S1")["found_by"] = {"given": "the user's request named this page"}
        self.source("S4")["found_by"] = {"link": "S1"}
        self.assertEqual(codes(self.check_log(), "results"), set())

    def test_a_link_from_an_unknown_source_fails(self):
        self.source("S4")["found_by"] = {"link": "S9"}
        self.assertIn("recalled", codes(self.check_log(), "results"))

    def test_an_unsaved_result_set_fails(self):
        del self.files["results/Q4.json"]
        self.assertIn("results-unsaved", codes(self.check_log(), "results"))

    def test_duplicates_match_by_identifier_then_title(self):
        def change():
            twin = copy.deepcopy(self.source("S3"))
            twin.update(id="S6", title="Caching tool calls for agents (v2)")
            self.log["sources"].append(twin)
            self.claim("C3")["cites"].append(dict(self.claim("C3")["cites"][0], source="S6"))
        self.assert_caught("duplicate-source", change, off("same_work(source, other)"), "results")

    def test_an_exact_title_matches_a_result_with_no_identifier(self):
        self.files["results/Q1.json"] = json.dumps([{"title": "TidePool 1.6  Configuration"},
                                                    {"title": "tidepool 1.6 release notes"}])
        self.assertEqual(codes(self.check_log(), "results"), set())


# ---- OR-4 and the strength caps -------------------------------------------------------------------------------------
class ReadingTests(Fixture):
    def test_a_snippet_or_listing_cannot_lift_a_claim_above_claimed(self):
        self.assert_caught("snippet-only", lambda: self.claim("C4").update(strength="present"),
                           off("not read_cites"), "reading")

    def test_the_same_claim_at_claimed_passes(self):
        self.claim("C4")["cites"][0]["basis"] = "listing"
        self.assertEqual(codes(self.check_log(), "reading"), set())

    def test_a_mirror_alone_cannot_lift_a_claim_above_claimed(self):
        self.assert_caught("copy-only", lambda: self.claim("C1")["cites"].pop(0), off("not firm_cites"), "reading")

    def test_one_secondary_source_alone_is_claimed(self):
        def change():
            self.source("S1")["kind"] = "secondary"
            self.claim("C1")["cites"].pop(1)
        self.assert_caught("single-secondary", change,
                           off("not primary_cites and len(firm_sources) < 2"), "reading")

    def test_two_secondary_sources_that_agree_can_be_present(self):
        self.source("S1")["kind"] = "secondary"
        self.source("S4")["kind"] = "secondary"
        self.assertEqual(codes(self.check_log(), "reading"), set())

    def test_tested_needs_a_run_with_its_receipt(self):
        self.assert_caught("no-run-receipt", lambda: self.claim("C2").update(strength="tested"),
                           off("needs_run and not ran_receipt"), "reading")

    def test_a_run_with_its_receipt_can_be_tested(self):
        self.claim("C2")["strength"] = "tested"
        self.claim("C2")["cites"].append({"source": "S2", "location": "probe output", "basis": "ran",
                                          "receipt": "receipts/probe-1.4.txt",
                                          "excerpt": "In transaction mode, prepared statements are not supported in 1.4."})
        self.assertEqual(codes(self.check_log(), "reading"), set())


# ---- SS-66: strength in the core's words ----------------------------------------------------------------------------
class StrengthTests(Fixture):
    def test_a_word_outside_the_vocabulary_fails(self):
        self.assert_caught("unknown-strength", lambda: self.claim("C3").update(strength="verified"),
                           off('claim.get("strength") not in levels'), "strength")

    def test_the_words_are_read_from_the_core_vocabulary_not_hard_coded(self):
        temp = tempfile.TemporaryDirectory(prefix="westack-research-core-")
        self.addCleanup(temp.cleanup)
        core = pathlib.Path(temp.name)
        (core / "references").mkdir()
        text = (CORE / "references" / "evidence-vocabulary.md").read_text(encoding="utf-8")
        text = text.replace("| observed |", "| replicated | Someone else reran it. | Yours. |\n| observed |", 1)
        (core / "references" / "evidence-vocabulary.md").write_text(text, encoding="utf-8")
        self.claim("C3")["strength"] = "replicated"
        self.assertNotIn("unknown-strength", codes(self.check_log(core=core)))
        self.assertIn("unknown-strength", codes(self.check_log()))

    def test_without_the_core_the_strength_checks_are_not_run(self):
        temp = tempfile.TemporaryDirectory(prefix="westack-research-nocore-")
        self.addCleanup(temp.cleanup)
        report = self.check_log(core=pathlib.Path(temp.name))
        self.assertEqual(report["checks"]["strength"], "not-run")
        self.assertEqual(report["checks"]["reading"], "not-run")
        self.assertEqual(report["status"], "incomplete")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rl.main(["check", str(self.root / "log.json"), "--core", temp.name]), 2)

    def test_a_contested_claim_needs_a_check(self):
        self.assert_caught("contested-unchecked", lambda: self.claim("C3").pop("check"),
                           off('claim.get("contested") is True and not text(claim.get("check"))'), "strength")


# ---- FY-1: identifiers in two indexes -------------------------------------------------------------------------------
class IdentifierTests(Fixture):
    def test_an_identifier_with_no_index_check_fails(self):
        self.assert_caught("identifier-unchecked", lambda: self.source("S3").pop("index_check"),
                           off("not isinstance(check_spec, dict)"), "identifiers")

    def test_one_index_is_not_two(self):
        self.assert_caught("index-not-independent",
                           lambda: self.source("S3")["index_check"]["records"].pop(1),
                           off("len(indexes) < 2"), "identifiers")

    def test_an_identifier_that_resolves_to_another_paper_is_flagged(self):
        def change():
            self.files["index/openalex.json"] = json.dumps({"title": "Agent Caching at Scale", "year": 2024,
                                                            "first_author": "Rivera"})
        report = self.assert_caught("index-mismatch", change,
                                    off("normal(found_value, field) != normal(source.get(field), field)"),
                                    "identifiers")
        detail = " ".join(f["detail"] for f in report["findings"] if f["code"] == "index-mismatch")
        self.assertIn("openalex", detail)
        self.assertIn("title", detail)

    def test_a_record_that_only_shows_the_id_resolves_is_incomplete(self):
        def change():
            self.files["index/openalex.json"] = json.dumps({"id": "2409.01234", "resolved": True})
        self.assert_caught("index-incomplete", change, off("missing_fields"), "identifiers")

    def test_the_matched_record_is_named(self):
        def change():
            self.source("S3")["index_check"]["matched"] = "crossref"
        self.assert_caught("index-unmatched", change, off('check_spec.get("matched") not in indexes'), "identifiers")

    def test_a_year_mismatch_is_flagged(self):
        self.files["index/arxiv.json"] = json.dumps({"title": "Caching Tool Calls for Agents", "year": 2023,
                                                     "authors": ["Ana Rivera"]})
        self.assertIn("index-mismatch", codes(self.check_log(), "identifiers"))


# ---- FY-4: the query floor and searched-for claims ------------------------------------------------------------------
class QueryTests(Fixture):
    def test_a_depth_first_question_needs_three_distinct_queries(self):
        def change():
            self.log["searches"] = [s for s in self.log["searches"] if s["id"] in ("Q1", "Q2")]
            self.source("S2")["found_by"] = {"link": "S1"}
            self.source("S5")["found_by"] = {"link": "S1"}
            self.log["searched_for"] = []
            self.log["delegates"] = []
            self.log["not_done"] = self.log["not_done"][1:]
        self.assert_caught("query-floor", change, off("len(distinct) < floor"), "queries")

    def test_a_one_fact_lookup_needs_one_query(self):
        self.log["depth"] = "straightforward"
        self.log["follow_up_cap"] = 1
        self.assertEqual(codes(self.check_log(), "queries"), set())

    def test_a_straightforward_read_of_given_pages_needs_no_query(self):
        self.log.update(depth="straightforward", follow_up_cap=0, searches=[], searched_for=[], delegates=[],
                        fetches=[], spend={"limit_usd": 0, "entries": []})
        self.log["sources"] = [s for s in self.log["sources"] if s["id"] in ("S1", "S4")]
        self.source("S1")["found_by"] = {"given": "the user pasted the link"}
        self.source("S4")["found_by"] = {"link": "S1"}
        self.log["claims"] = [self.claim("C1"), self.claim("C4")]
        self.log["gaps"] = [g for g in self.log["gaps"] if g["origin"] == "speculative"]
        self.log["not_done"] = self.log["not_done"][1:]
        self.assertEqual(codes(self.check_log()), set())

    def test_a_search_claim_with_no_logged_query_fails(self):
        self.assert_caught("search-claim-unlogged",
                           lambda: self.log["searched_for"].append({"text": "No CVE mentions tidepool.", "queries": []}),
                           off("not queries or any(query not in search_ids for query in queries)"), "queries")

    def test_a_delegate_nothing_found_entry_maps_to_a_logged_query(self):
        self.log["delegates"][0]["nothing_found"][0]["queries"] = ["Q9"]
        self.assertIn("search-claim-unlogged", codes(self.check_log(), "queries"))


# ---- AX-2: request pacing and failures ------------------------------------------------------------------------------
class PacingTests(Fixture):
    def test_two_calls_closer_than_the_published_interval_are_flagged(self):
        self.assert_caught("too-fast",
                           lambda: self.search("Q2")["calls"][1].update(at="2026-10-30T10:01:01Z"),
                           off("gap < minimum"), "pacing")

    def test_a_failure_records_its_url_and_attempt(self):
        self.assert_caught("failure-unrecorded", lambda: self.log["fetches"][0].pop("attempt"),
                           off('not text(request.get("url")) or not is_count(request.get("attempt"))'), "pacing")

    def test_a_host_with_no_published_rule_is_not_paced(self):
        self.search("Q3")["calls"][0]["at"] = "2026-10-30T10:00:00Z"
        self.assertEqual(codes(self.check_log(), "pacing"), set())

    def test_an_unreadable_time_is_a_finding(self):
        self.search("Q2")["calls"][0]["at"] = "ten past ten"
        self.assertIn("bad-time", codes(self.check_log(), "pacing"))


# ---- WA-83 (research half): the delegate's three lists --------------------------------------------------------------
class DelegateTests(Fixture):
    def test_a_return_without_its_three_lists_fails(self):
        self.assert_caught("delegate-lists", lambda: self.log["delegates"][0].pop("not_searched"),
                           off("not isinstance(delegate.get(key), list)"), "delegates")

    def test_a_found_entry_names_a_logged_source(self):
        self.log["delegates"][0]["found"].append("S9")
        self.assertIn("found-unknown", codes(self.check_log(), "delegates"))

    def test_a_not_searched_lead_is_taken_up_or_listed_as_not_done(self):
        self.assert_caught("lead-dropped", lambda: self.log["not_done"].pop(0),
                           off("normal_text(lead) not in closed_leads"), "delegates")

    def test_a_lead_taken_up_by_a_later_round_is_closed(self):
        self.log["not_done"].pop(0)
        self.search("Q4")["gap"] = "vendor forums"
        self.assertEqual(codes(self.check_log(), "delegates"), set())


# ---- RS-1: gaps by origin -------------------------------------------------------------------------------------------
class GapTests(Fixture):
    def test_a_stated_gap_cites_a_location(self):
        self.assert_caught("stated-unlocated",
                           lambda: self.log["gaps"][1].update(origin="stated"),
                           off('not (gap.get("source") in source_ids and text(gap.get("location")))'), "gaps")

    def test_an_inferred_gap_names_the_sources_it_came_from(self):
        self.assert_caught("inferred-unsourced", lambda: self.log["gaps"][1].update({"from": ["S1"]}),
                           off("len(inferred_from) < 2"), "gaps")

    def test_an_unknown_origin_fails(self):
        self.log["gaps"][2]["origin"] = "obvious"
        self.assertIn("bad-origin", codes(self.check_log(), "gaps"))


# ---- FY-2: every number and citation traces to the source wording ---------------------------------------------------
class TraceTests(Fixture):
    def test_a_planted_percentage_is_caught(self):
        def change():
            self.claim("C1")["text"] = "tidepool 1.6.0 supports prepared statements in transaction mode, 40% faster."
        self.assert_caught("number-untraced", change, off("token not in allowed"), "trace")

    def test_a_version_traces_to_the_source_entry(self):
        self.claim("C2")["text"] = "tidepool 1.4.2 does not support prepared statements in transaction mode."
        self.assertEqual(codes(self.check_log(), "trace"), set())

    def test_an_excerpt_missing_from_the_saved_original_fails(self):
        self.assert_caught("excerpt-not-in-source",
                           lambda: self.claim("C3")["cites"][0].update(excerpt="caching cut cost by 60%."),
                           off("normal_text(excerpt) not in saved_text"), "trace")

    def test_a_citation_to_an_unknown_source_fails(self):
        self.claim("C2")["cites"][0]["source"] = "S9"
        self.assertIn("unknown-source", codes(self.check_log(), "trace"))

    def test_every_accepted_source_is_cited(self):
        def change():
            self.claim("C1")["cites"].pop(1)
            self.claim("C1")["strength"] = "present"
        self.assert_caught("uncited-source", change, off('source["id"] not in cited_ids'), "trace")

    def test_a_citation_carries_its_excerpt(self):
        self.claim("C2")["cites"][0].pop("excerpt")
        self.assertIn("no-excerpt", codes(self.check_log(), "trace"))

    def test_a_binary_original_needs_a_text_copy(self):
        self.files["sources/S3.pdf"] = b"%PDF-1.7\n\xff\xfe\x00binary"
        self.source("S3")["saved"] = "sources/S3.pdf"
        self.assertIn("excerpt-unverifiable", codes(self.check_log(), "trace"))
        self.source("S3")["text"] = "sources/S3.txt"
        self.assertNotIn("excerpt-unverifiable", codes(self.check_log(), "trace"))


# ---- FY-3 provenance, pins, mirrors and saved originals -------------------------------------------------------------
class SourceTests(Fixture):
    def test_a_rejected_source_says_why(self):
        self.assert_caught("rejected-without-reason", lambda: self.source("S5").pop("reason"),
                           off('status == "rejected" and not text(source.get("reason"))'), "sources")

    def test_an_accepted_source_is_pinned_by_date_and_version(self):
        self.assert_caught("unpinned", lambda: self.source("S2").pop("version"),
                           off('not iso_date(source.get("retrieved")) or not (text(source.get("version")) or '
                               'text(source.get("published")))'), "sources")

    def test_a_mirror_records_the_original_and_retrieval_urls(self):
        self.assert_caught("mirror-unrecorded", lambda: self.source("S4").pop("original_url"),
                           off('kind == "mirror" and not (text(source.get("original_url")) and text(source.get("url")))'),
                           "sources")

    def test_a_saved_original_that_changed_is_caught(self):
        def change():
            self.source("S1")["sha256"] = sha(S1)
            self.files["sources/S1.md"] = S1 + "\nEdited later.\n"
        self.assert_caught("saved-changed", change, off('digest(saved_path) != source.get("sha256")'), "sources")

    def test_an_accepted_source_is_saved(self):
        self.source("S2").pop("saved")
        self.assertIn("not-saved", codes(self.check_log(), "sources"))

    def test_a_partial_or_blocked_run_says_why_and_what_was_not_done(self):
        self.assert_caught("status-unreasoned", lambda: self.log.update(status="partial"),
                           off('data.get("status") != "complete" and not (text(data.get("reason")) and '
                               'data.get("not_done"))'), "sources")


# ---- DG-37: a repository's licence is its licence file, cross-checked with the host's licence field -----------------
class LicenceTests(Fixture):
    """S6 is a repository the user named, read for one claim; each test varies its licence entry."""

    README = "# design-mcp\n\nDesign patterns for agents.\n\nLicense: MIT\n"
    LICENCE_FILE = "MIT License\n\nCopyright (c) 2026 Example Author\n"
    FILE_CHECK = off("not has_file")
    HOST_CHECK = off('licence_key(licence.get("host")) != licence_key(licence.get("name"))')
    ENTRY_CHECK = off('not (isinstance(licence, dict) and licence_key(licence.get("name")) and '
                      'licence.get("status") in LICENCE_STATUSES)')

    def repository(self, licence):
        self.files["sources/S6.md"] = self.README
        self.files["sources/S6-LICENSE"] = self.LICENCE_FILE
        self.log["sources"].append(
            {"id": "S6", "title": "design-mcp", "url": "https://git.example/acme/design-mcp/blob/c2000d1/README.md",
             "kind": "primary", "version": "c2000d1", "retrieved": "2026-10-31", "saved": "sources/S6.md",
             "found_by": {"given": "the user named the repository"}, "status": "accepted", "licence": licence})
        self.log["claims"].append(
            {"id": "C5", "text": "design-mcp's README names MIT as its licence.", "strength": "claimed",
             "cites": [{"source": "S6", "location": "line 5", "basis": "read", "excerpt": "License: MIT"}]})

    def test_a_log_without_a_licence_entry_is_unchanged(self):
        report = self.check_log()
        self.assertEqual(report["checks"]["licence"], "not-applicable")
        self.assertEqual(report["status"], "clean")

    def test_a_licence_named_only_in_a_readme_is_unverified(self):
        """The brief's fixture: the README says MIT, there is no licence file and the host's field is null."""
        report = self.assert_caught(
            "licence-unverified",
            lambda: self.repository({"name": "MIT", "status": "verified", "file": None, "host": None}),
            self.FILE_CHECK, "licence")
        detail = " ".join(f["detail"] for f in report["findings"] if f["code"] == "licence-unverified")
        self.assertIn("ideas only", detail)
        self.assertEqual(report["checks"]["licence"], "failed")

    def test_a_licence_file_named_but_not_saved_is_unverified(self):
        self.repository({"name": "MIT", "status": "verified", "file": "sources/LICENSE-not-saved", "host": "MIT"})
        self.assertIn("licence-unverified", codes(self.check_log(), "licence"))

    def test_a_host_field_naming_another_licence_fails_the_cross_check(self):
        self.assert_caught(
            "licence-mismatch",
            lambda: self.repository({"name": "MIT", "status": "verified", "file": "sources/S6-LICENSE",
                                     "host": "Apache-2.0"}),
            self.HOST_CHECK, "licence")

    def test_a_null_host_field_beside_a_licence_file_fails_the_cross_check(self):
        self.repository({"name": "MIT", "status": "verified", "file": "sources/S6-LICENSE", "host": None})
        self.assertIn("licence-mismatch", codes(self.check_log(), "licence"))

    def test_a_saved_licence_file_with_an_agreeing_host_field_is_verified(self):
        self.repository({"name": "MIT", "status": "verified", "file": "sources/S6-LICENSE", "host": "MIT License"})
        report = self.check_log()
        self.assertEqual(report["findings"], [], report["findings"])
        self.assertEqual(report["checks"]["licence"], "passed")

    def test_a_licence_kept_unverified_is_clean_and_noted(self):
        self.repository({"name": "MIT", "status": "unverified", "file": None, "host": None})
        report = self.check_log()
        self.assertEqual(report["findings"], [], report["findings"])
        self.assertEqual(report["checks"]["licence"], "passed")
        self.assertTrue(any("S6" in note and "ideas only" in note for note in report["notes"]), report["notes"])

    def test_a_licence_entry_gives_its_name_and_status(self):
        self.assert_caught("bad-value",
                           lambda: self.repository({"name": "MIT", "file": None, "host": None}),
                           self.ENTRY_CHECK, "licence")
        self.log["sources"][-1]["licence"] = "MIT"
        self.assertIn("bad-value", codes(self.check_log(), "licence"))


# ---- SI-1: name each artifact on its own ----------------------------------------------------------------------------
class ArtifactTests(Fixture):
    """SI-1. S6 is a bot's profile: it uses two of a plugin's skills and has two of its own. S7 is the plugin. Each test
    varies how the log records the two."""

    PROFILE = ("dr-bot, a shared bot\n\nUses the kit plugin's setup-kit and verify-kit skills.\n"
               "Its own skills: design-rubric and weekly-audit.\n")
    PLUGIN = "# kit plugin\n\nSkills: setup-kit, verify-kit, explain-number.\n"
    LICENCE_FILE = "MIT License\n\nCopyright (c) 2026 Example Author\n"
    MERGED = off("not (part in run.by_source and part != sid)")
    UNPINNED = off("not (pinned(other) and other.get(\"licence\") is not None)")

    def bot_and_plugin(self, includes=("S7",), plugin=True):
        self.files["sources/S6.md"] = self.PROFILE
        self.log["sources"].append(
            {"id": "S6", "title": "dr-bot", "url": "https://bots.example/dr-bot", "kind": "primary",
             "published": "2026-10-31", "retrieved": "2026-10-31", "saved": "sources/S6.md",
             "found_by": {"given": "the user pasted the profile"}, "status": "accepted", "includes": list(includes),
             "licence": {"name": "none stated", "status": "unverified", "file": None, "host": None}})
        self.log["claims"].append(
            {"id": "C5", "text": "dr-bot's own skills are design-rubric and weekly-audit.", "strength": "claimed",
             "cites": [{"source": "S6", "location": "line 4", "basis": "read",
                        "excerpt": "Its own skills: design-rubric and weekly-audit."}]})
        if plugin:
            self.files["sources/S7.md"] = self.PLUGIN
            self.files["sources/S7-LICENSE"] = self.LICENCE_FILE
            self.log["sources"].append(
                {"id": "S7", "title": "kit plugin", "url": "https://git.example/acme/plugins/blob/4dd1d05/kit/README.md",
                 "kind": "primary", "version": "4dd1d05", "retrieved": "2026-10-31", "saved": "sources/S7.md",
                 "found_by": {"link": "S6"}, "status": "accepted",
                 "licence": {"name": "MIT", "status": "verified", "file": "sources/S7-LICENSE", "host": "MIT"}})
            self.log["claims"].append(
                {"id": "C6", "text": "The kit plugin ships setup-kit and verify-kit.", "strength": "claimed",
                 "cites": [{"source": "S7", "location": "line 3", "basis": "read",
                            "excerpt": "Skills: setup-kit, verify-kit, explain-number."}]})

    def test_a_log_without_parts_is_unchanged(self):
        report = self.check_log()
        self.assertEqual((report["status"], report["checks"]["artifacts"]), ("clean", "not-applicable"))

    def test_the_bot_and_the_plugin_on_their_own_rows_pass(self):
        self.bot_and_plugin()
        report = self.check_log()
        self.assertEqual(report["findings"], [], report["findings"])
        self.assertEqual(report["checks"]["artifacts"], "passed")

    def test_a_merged_row_fails(self):
        """The brief's fixture: the plugin is named inside the bot's row instead of on a row of its own."""
        report = self.assert_caught("artifact-merged", lambda: self.bot_and_plugin(includes=("kit plugin",), plugin=False),
                                    self.MERGED, "artifacts")
        self.assertEqual(report["checks"]["artifacts"], "failed")
        self.log["sources"][-1]["includes"] = ["S6"]
        self.assertIn("artifact-merged", codes(self.check_log(), "artifacts"), "a row cannot be its own part")

    def test_a_part_without_its_own_licence_fails(self):
        self.assert_caught("artifact-unpinned", lambda: (self.bot_and_plugin(), self.source("S7").pop("licence")),
                           self.UNPINNED, "artifacts")

    def test_a_part_without_its_own_pin_fails(self):
        self.assert_caught("artifact-unpinned", lambda: (self.bot_and_plugin(), self.source("S7").pop("version")),
                           self.UNPINNED, "artifacts")

    def test_includes_is_a_list_of_source_ids(self):
        self.assert_caught("bad-value", lambda: (self.bot_and_plugin(), self.source("S6").update(includes="S7")),
                           off("not (isinstance(parts, list) and all(text(part) for part in parts))"), "artifacts")


# ---- treg row 8: spend ----------------------------------------------------------------------------------------------
class SpendTests(Fixture):
    def test_a_running_total_past_the_limit_fails(self):
        self.assert_caught("over-budget", lambda: self.log["spend"]["entries"].append({"what": "second bulk", "usd": 0.6}),
                           off("limit is not None and total > limit"), "spend")

    def test_bulk_spend_waits_for_a_pilot(self):
        self.assert_caught("no-pilot", lambda: self.log["spend"]["entries"].reverse(),
                           off('entry.get("bulk") is True and not piloted'), "spend")


# ---- the task record that cites the log -----------------------------------------------------------------------------
class RecordTests(Fixture):
    def record(self, log_hash=None, cite=True):
        task = json.loads((CORE / "examples" / "task.json").read_text(encoding="utf-8"))
        path = self.save()
        task["evidence"][0]["artifact_sha256"] = log_hash or sha(path.read_bytes())
        task["evidence"][0]["artifact"] = "research/log.json"
        if cite:
            task["observations"] = [{"id": "o1", "kind": "confirmed", "text": "research answered; see the log",
                                     "evidence_ids": ["e1"]}]
        return self.write("task.0001.json", json.dumps(task, indent=2))

    def test_a_record_that_cites_the_log_passes(self):
        record = self.record()
        report = rl.check(self.root / "log.json", record=record, core=CORE)
        self.assertEqual(report["checks"]["record"], "passed", report["findings"])

    def test_a_record_whose_receipt_holds_another_hash_fails(self):
        record = self.record(log_hash="0" * 64)
        report = rl.check(self.root / "log.json", record=record, core=CORE)
        self.assertIn("record-no-receipt", codes(report, "record"))
        control = broken(off("not log_receipts")).check(self.root / "log.json", record=record, core=CORE)
        self.assertNotIn("record-no-receipt", codes(control, "record"))

    def test_a_receipt_no_observation_cites_fails(self):
        record = self.record(cite=False)
        report = rl.check(self.root / "log.json", record=record, core=CORE)
        self.assertIn("record-uncited", codes(report, "record"))
        control = broken(off("not cited_by")).check(self.root / "log.json", record=record, core=CORE)
        self.assertNotIn("record-uncited", codes(control, "record"))

    def test_a_malformed_record_is_reported_through_the_core_contract(self):
        record = self.record()
        task = json.loads(record.read_text(encoding="utf-8"))
        task["evidence"][0]["status"] = "fine"
        record.write_text(json.dumps(task), encoding="utf-8")
        self.assertIn("record-shape", codes(rl.check(self.root / "log.json", record=record, core=CORE), "record"))

    def test_without_the_core_the_record_check_is_not_run(self):
        record = self.record()
        temp = tempfile.TemporaryDirectory(prefix="westack-research-nocore-")
        self.addCleanup(temp.cleanup)
        shutil.copytree(CORE / "references", pathlib.Path(temp.name) / "references")
        report = rl.check(self.root / "log.json", record=record, core=pathlib.Path(temp.name))
        self.assertEqual(report["checks"]["record"], "not-run")
        self.assertEqual(report["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
