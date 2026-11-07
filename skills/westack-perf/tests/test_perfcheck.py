"""Tests for westack-perf's scripts/perfcheck.py. Local files only.

Run from the repo root:  python -B -m unittest discover -s skills/westack-perf/tests
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import perfcheck  # noqa: E402


def run(values, kind="page", errors=0, limiter="", **extra):
    """values: {metric: [v1, v2, ...]} -> a run file with one entry per index."""
    n = max(len(v) for v in values.values())
    r = {"format": perfcheck.RUN_FORMAT, "kind": kind, "target": "/fast.html", "claim": "LCP stays under 1 s",
         "driver": "host browser pane",
         "environment": {"os": "Windows 11", "browser": "Chrome 152", "viewport": "1025x768", "cache": "cold",
                         "machine": "8 cores, idle"},
         "runs": [{"metrics": {m: v[i] for m, v in values.items() if i < len(v)}, "errors": errors} for i in range(n)],
         "limiter": limiter}
    r.update(extra)
    return r


FAST = {"lcp_ms": [100, 104, 98, 102, 101], "js_bytes": [1000] * 5, "total_requests": [3] * 5, "cls": [0.0] * 5}


class SummaryTests(unittest.TestCase):
    def test_median_range_count(self):
        s = perfcheck.summarize(run(FAST))
        self.assertEqual(s["lcp_ms"], {"median": 101, "min": 98, "max": 104, "n": 5})

    def test_units_from_names(self):
        self.assertEqual([perfcheck.unit(m) for m in ("lcp_ms", "js_bytes", "total_requests", "cls")],
                         ["timing", "size", "count", "unitless"])


class CompareTests(unittest.TestCase):
    def test_a_one_second_block_is_a_regression(self):
        slow = dict(FAST, lcp_ms=[1105, 1110, 1098, 1102, 1120])
        c = perfcheck.compare(run(FAST), run(slow, limiter="a 1 s busy loop in a head script"))
        lcp = next(r for r in c["metrics"] if r["metric"] == "lcp_ms")
        self.assertEqual((c["verdict"], lcp["status"]), ("slower", "regression"))

    def test_a_delta_inside_the_spread_is_no_difference(self):
        noisy = dict(FAST, lcp_ms=[100, 140, 98, 102, 101])
        moved = dict(FAST, lcp_ms=[120, 125, 118, 122, 121])
        c = perfcheck.compare(run(noisy), run(moved))
        self.assertEqual(c["verdict"], "no measurable difference")

    def test_thresholds_by_unit(self):
        t = perfcheck.thresholds()
        base = {"median": 1000, "min": 1000, "max": 1000, "n": 5}

        def st(metric, cur):
            return perfcheck.metric_status(metric, base, {"median": cur, "min": cur, "max": cur, "n": 5}, t)["status"]
        self.assertEqual([st("load_ms", v) for v in (1100, 1300, 1600)], ["ok", "warning", "regression"])
        self.assertEqual([st("js_bytes", v) for v in (1050, 1200, 1300)], ["ok", "warning", "regression"])
        self.assertEqual([st("total_requests", v) for v in (1200, 1400)], ["ok", "warning"])
        self.assertEqual(st("load_ms", 900), "improved")
        small = {"median": 0.02, "min": 0.02, "max": 0.02, "n": 5}
        self.assertEqual(perfcheck.metric_status("cls", small, {"median": 0.15, "min": 0.15, "max": 0.15, "n": 5}, t)["status"], "regression")

    def test_an_absolute_500_ms_rise_is_a_regression_even_under_50_percent(self):
        base = run({"load_ms": [2000] * 5})
        cur = run({"load_ms": [2600] * 5}, limiter="third-party tag")
        self.assertEqual(perfcheck.compare(base, cur)["verdict"], "slower")

    def test_inconclusive_without_runs_limiter_or_with_errors(self):
        slow = dict(FAST, lcp_ms=[1105, 1110, 1098, 1102, 1120])
        self.assertIn("no limiter", " ".join(perfcheck.compare(run(FAST), run(slow))["reasons"]))
        few = {m: v[:3] for m, v in slow.items()}
        c = perfcheck.compare(run(FAST), run(few, limiter="x"))
        self.assertEqual(c["verdict"], "inconclusive")
        self.assertIn("3 runs", " ".join(c["reasons"]))
        c = perfcheck.compare(run(FAST), run(slow, errors=1, limiter="x"))
        self.assertIn("errors", " ".join(c["reasons"]))


class BudgetTests(unittest.TestCase):
    def test_pass_warning_fail_and_grade(self):
        r = run({"fcp_ms": [1700] * 5, "lcp_ms": [3000] * 5, "js_bytes": [100000] * 5, "cls": [0.0] * 5})
        b = perfcheck.budget(r)
        status = {row["metric"]: row["status"] for row in b["metrics"]}
        self.assertEqual((status["fcp_ms"], status["lcp_ms"], status["js_bytes"], status["css_bytes"]),
                         ("warning", "fail", "pass", "n/a"))
        self.assertEqual((b["grade"], b["below_budget"], b["measured"]), ("B", 3, 4))

    def test_grades(self):
        self.assertEqual(perfcheck.budget(run({"fcp_ms": [10] * 5}))["grade"], "A")
        self.assertEqual(perfcheck.budget(run({"fcp_ms": [9000] * 5, "lcp_ms": [9000] * 5, "cls": [0.0] * 5}))["grade"], "D")
        self.assertEqual(perfcheck.budget(run({"x_ms": [1]}))["grade"], "n/a")


class ValidateAndCliTests(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertEqual(perfcheck.validate(run(FAST)), [])
        bad = run(FAST, claim="", driver="")
        bad["runs"][0].pop("errors")
        errors = " | ".join(perfcheck.validate(bad))
        for phrase in ("claim", "driver", "counts its errors"):
            self.assertIn(phrase, errors)
        self.assertTrue(any("machine" in e for e in perfcheck.validate(run(FAST, kind="command", environment={}))))

    def test_cli_exit_codes_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, slow, hist = Path(tmp, "b.json"), Path(tmp, "s.json"), Path(tmp, "h.jsonl")
            base.write_text(json.dumps(run(FAST)), encoding="utf-8")
            slow.write_text(json.dumps(run(dict(FAST, lcp_ms=[1105] * 5), limiter="x")), encoding="utf-8")
            hist.write_text("\n".join(json.dumps(dict(run(FAST), at=a)) for a in ("2026-11-02", "2026-11-01")), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                codes = [perfcheck.main(["compare", str(base), str(base)]), perfcheck.main(["compare", str(base), str(slow)]),
                         perfcheck.main(["validate", str(base)]), perfcheck.main(["nope"])]
            self.assertEqual(codes, [0, 1, 0, 64])
            self.assertEqual([r["at"] for r in perfcheck.history(hist)], ["2026-11-01", "2026-11-02"])


if __name__ == "__main__":
    unittest.main()
