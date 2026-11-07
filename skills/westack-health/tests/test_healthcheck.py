"""Tests for westack-health's scripts/healthcheck.py (detect, score, history, recommend). Local files only.

Run from the repo root:  python -B -m unittest discover -s skills/westack-health/tests

Each scoring rule has an in-suite broken-copy control: a thresholds copy or a script copy with the rule disconnected,
which must miss what the real rule finds.
"""
import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "healthcheck.py"
FIXTURE = HERE.parent / "evals" / "fixtures" / "results-partial.json"
SHA = "0" * 64


def load(path=SCRIPT, name="westack_healthcheck_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hc = load()


def broken(old, new, name):
    """A copy of the script with one rule replaced; the source must contain `old` exactly once."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        module = load(path, name)
    module.THRESHOLDS = hc.THRESHOLDS
    return module


def ran(command="tool", exit=0, **counts):
    return {"status": "ran", "command": command, "exit": exit, "counts": counts, "log": "x.log", "log_sha256": SHA}


def skipped(reason="not installed"):
    return {"status": "skipped", "reason": reason}


def results(**cats):
    base = {"typecheck": ran(errors=0), "lint": ran(exit=1, warnings=3), "tests": ran(executed=50, passed=50, failed=0),
            "deadcode": ran(exit=1, unused=7), "shell": ran(issues=0), "index": ran("codeindex.py doctor", verdict="OK")}
    base.update(cats)
    return {"format": hc.RESULTS_FORMAT, "repo": "example", "date": "2026-11-04", "branch": "main",
            "revision": "abc1234", "categories": base}


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hc.main(list(args))
    return code, out.getvalue()


class BandTests(unittest.TestCase):
    def s(self, cat, entry):
        return hc.category_score(cat, entry, hc.thresholds())[0]

    def test_count_bands(self):
        cases = [("typecheck", 0, 0, 10), ("typecheck", 1, 9, 7), ("typecheck", 1, 10, 4), ("typecheck", 1, 49, 4),
                 ("typecheck", 1, 50, 0), ("lint", 1, 4, 7), ("lint", 1, 5, 4), ("lint", 1, 20, 0),
                 ("deadcode", 1, 19, 4), ("deadcode", 1, 20, 0), ("shell", 1, 4, 7), ("shell", 1, 500, 4)]
        for cat, code, n, want in cases:
            key = hc.thresholds()["count_bands"][cat]["count"]
            with self.subTest(cat=cat, n=n):
                self.assertEqual(self.s(cat, ran(exit=code, **{key: n})), want)

    def test_a_failing_exit_with_no_count_is_never_clean(self):
        self.assertEqual(self.s("lint", ran(exit=2)), 4)
        self.assertEqual(self.s("lint", ran(exit=1, warnings=0)), 4)

    def test_test_pass_rates(self):
        cases = [((50, 50, 0), 0, 10), ((100, 96, 4), 1, 7), ((100, 95, 5), 1, 4), ((100, 81, 19), 1, 4),
                 ((100, 80, 20), 1, 0), ((50, 50, 0), 1, 4)]
        for (e, p, f), code, want in cases:
            with self.subTest(executed=e, passed=p, exit=code):
                self.assertEqual(self.s("tests", ran(exit=code, executed=e, passed=p, failed=f)), want)

    def test_zero_executed_is_not_a_pass_and_unknown_counts_are_not_clean(self):
        self.assertEqual(hc.category_score("tests", ran(executed=0, passed=0, failed=0), hc.thresholds()),
                         (0, "no tests executed: not a pass"))
        self.assertEqual(self.s("tests", ran(exit=0)), 7)
        self.assertEqual(self.s("tests", ran(exit=1)), 4)

    def test_labels(self):
        t = hc.thresholds()
        self.assertEqual([hc.label(x, t) for x in (10, 9, 7, 6, 4, 3, 0)],
                         ["CLEAN", "WARNING", "WARNING", "NEEDS WORK", "NEEDS WORK", "CRITICAL", "CRITICAL"])

    def test_the_control_shifted_bands_miss_fifty_type_errors(self):
        t = copy.deepcopy(hc.thresholds())
        t["count_bands"]["typecheck"]["below"] = [[1000, 7]]
        self.assertEqual(hc.category_score("typecheck", ran(exit=1, errors=50), t)[0], 7,
                         "the broken bands miss what the real ones find")
        self.assertEqual(self.s("typecheck", ran(exit=1, errors=50)), 0)


class CompositeTests(unittest.TestCase):
    def test_weighting(self):
        # typecheck 10, lint 7, tests 10, deadcode 4, shell 10, index 10:
        # (220 + 126 + 280 + 52 + 90 + 100) / 100 = 8.68 -> 8.7
        r = hc.score(results())
        self.assertEqual((r["status"], r["composite"]), ("scored", 8.7))
        self.assertEqual({c: v["score"] for c, v in r["categories"].items()},
                         {"typecheck": 10, "lint": 7, "tests": 10, "deadcode": 4, "shell": 10, "index": 10})
        self.assertEqual(r["history_line"]["score"], 8.7)

    def test_skipped_weight_is_redistributed(self):
        # lint and shell skipped: (220 + 280 + 52 + 100) / 73 = 8.93 -> 8.9
        r = hc.score(results(lint=skipped(), shell=skipped("no shell scripts")))
        self.assertEqual((r["status"], r["composite"]), ("partial coverage", 8.9))
        self.assertEqual(r["coverage"]["checked"], "4/6")
        self.assertEqual(r["coverage"]["skipped"], {"lint": "not installed", "shell": "no shell scripts"})
        self.assertEqual([r["categories"][c]["effective_weight"] for c in ("typecheck", "tests", "deadcode", "index")],
                         [30.1, 38.4, 17.8, 13.7])
        self.assertIsNone(r["history_line"]["lint"])

    def test_the_index_dimension(self):
        t = hc.thresholds()
        self.assertEqual([hc.category_score("index", ran(verdict=v), t)[0] for v in ("OK", "WARN", "ERR")], [10, 7, 0])
        # no index for this repository: its 10 is shared out, (220 + 126 + 280 + 52 + 90) / 90 = 8.53 -> 8.5
        r = hc.score(results(index=skipped("no westack-onboard index for this repository")))
        self.assertEqual((r["status"], r["composite"], r["coverage"]["checked"]), ("partial coverage", 8.5, "5/6"))
        bad = results(index=ran("codeindex.py doctor", verdict="fine"))
        self.assertIn("index: counts.verdict must be one of OK, WARN, ERR", " | ".join(hc.score(bad)["errors"]))

    def test_the_control_an_index_map_that_scores_warn_as_clean(self):
        t = copy.deepcopy(hc.thresholds())
        t["index"]["WARN"] = 10
        self.assertEqual(hc.category_score("index", ran(verdict="WARN"), t)[0], 10, "the broken map misses the warning")

    def test_capture_errors_and_empty_runs_are_not_scored(self):
        r = hc.score(results(lint={"status": "error", "reason": "log could not be written"}))
        self.assertEqual((r["status"], r["composite"]), ("not scored: capture failed", None))
        self.assertNotIn("history_line", r)
        none = {c: skipped() for c in hc.thresholds()["weights"]}
        r = hc.score(results(**none))
        self.assertEqual((r["status"], r["composite"]), ("not scored: no checks ran", None))

    def test_validation(self):
        r = results()
        del r["categories"]["shell"]
        r["categories"]["tests"] = ran(executed=10, passed=8, failed=1)
        r["categories"]["lint"] = {"status": "ran", "command": "ruff check .", "exit": 0}
        r["categories"]["style"] = skipped()
        errors = " | ".join(hc.score(r)["errors"])
        for phrase in ("shell: missing", "passed plus failed must equal executed", "lint: a run keeps its full log",
                       "style: not a weighted category"):
            self.assertIn(phrase, errors)

    def test_the_control_equal_weights_miss_the_weighting(self):
        t = copy.deepcopy(hc.thresholds())
        t["weights"] = {c: 1 for c in t["weights"]}
        self.assertEqual(hc.score(results(), t)["composite"], 8.5, "51 / 6: the broken weights miss the real 8.7")

    def test_the_control_without_redistribution_the_skipped_weight_drags_the_score(self):
        b = broken('total = sum(t["weights"][c] for c in scored)', 'total = sum(t["weights"].values())',
                   "healthcheck_no_redistribution")
        r = b.score(results(lint=skipped(), shell=skipped("no shell scripts")))
        self.assertEqual(r["composite"], 6.5, "652 / 100: the broken copy misses the redistribution")


class RecommendTests(unittest.TestCase):
    def case(self):
        # tests 7 (impact 28*3=84), deadcode 4 (13*6=78), lint 7 (18*3=54); typecheck and shell clean
        return results(tests=ran(exit=1, executed=100, passed=96, failed=4))

    def test_ranked_by_weight_times_deficit(self):
        recs = hc.recommend(self.case())["recommendations"]
        self.assertEqual([(r["category"], r["impact"], r["priority"]) for r in recs],
                         [("tests", 84, "high"), ("deadcode", 78, "medium"), ("lint", 54, "low")])

    def test_the_control_ranking_by_deficit_alone_puts_dead_code_first(self):
        b = broken('-cv[1]["weight"] * (10 - cv[1]["score"])', '-(10 - cv[1]["score"])', "healthcheck_no_weight_rank")
        recs = b.recommend(self.case())["recommendations"]
        self.assertEqual(recs[0]["category"], "deadcode", "the broken copy misses the weighting in the ranking")


class HistoryTests(unittest.TestCase):
    def line(self, **over):
        r = hc.score(results())["history_line"]
        r.update(over)
        return r

    def test_first_run_and_comparable_trends(self):
        self.assertEqual(hc.history([], results())[1]["trend"], "first run")
        code, r = hc.history([self.line(score=8.0, lint=4)], results())
        self.assertEqual((code, r["trend"], r["delta"]), (0, "improving", 0.7))
        code, r = hc.history([self.line(score=9.1, deadcode=7)], results())
        self.assertEqual((code, r["trend"], r["delta"]), (1, "declining", -0.4))
        self.assertEqual(r["declines"], [{"category": "deadcode", "previous": 7, "current": 4, "delta": -3}])

    def test_changed_coverage_is_not_compared(self):
        code, r = hc.history([self.line(shell=None, score=9.9)], results())
        self.assertEqual((code, r["trend"]), (0, "coverage changed: not comparable"))
        self.assertNotIn("delta", r)

    def test_an_unscored_run_has_no_trend(self):
        none = {c: skipped() for c in hc.thresholds()["weights"]}
        code, r = hc.history([self.line()], results(**none))
        self.assertEqual((code, r["trend"]), (2, "none"))


class DetectTests(unittest.TestCase):
    def test_a_declared_health_stack_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "tsconfig.json").write_text("{}", encoding="utf-8")
            Path(tmp, "AGENTS.md").write_text("# Rules\n\n## Health Stack\n\n- test: python -B run.py\n- lint: none\n"
                                              "- types: mypy src\n- style: black --check .\n\n## Other\n- shell: x\n",
                                              encoding="utf-8")
            d = hc.detect(Path(tmp))
            self.assertEqual(d["source"], "AGENTS.md Health Stack")
            self.assertEqual(d["categories"]["tests"]["command"], "python -B run.py")
            self.assertEqual(d["categories"]["typecheck"]["command"], "mypy src")
            self.assertIsNone(d["categories"]["lint"]["command"])
            self.assertIsNone(d["categories"]["shell"]["command"], "a line after the section is not part of it")
            self.assertEqual(d["unknown"], ["style"])

    def test_detected_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "pyproject.toml").write_text("[tool.ruff]\n[tool.pytest.ini_options]\n", encoding="utf-8")
            Path(tmp, "build.sh").write_text("echo hi\n", encoding="utf-8")
            with mock.patch.object(hc.shutil, "which", return_value=None):
                d = hc.detect(Path(tmp))
            cats = d["categories"]
            self.assertEqual((cats["lint"]["command"], cats["tests"]["command"]), ("ruff check .", "python -m pytest"))
            self.assertEqual(cats["shell"]["reason"], "1 shell scripts, shellcheck not on PATH")
            self.assertIsNone(cats["typecheck"]["command"])


class CliTests(unittest.TestCase):
    def test_exit_codes(self):
        self.assertEqual(run("score", str(FIXTURE))[0], 0)
        self.assertEqual(json.loads(run("score", str(FIXTURE))[1])["status"], "partial coverage")
        self.assertEqual(run("recommend", str(FIXTURE))[0], 0)
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp, "none.json")
            empty.write_text(json.dumps(results(**{c: skipped() for c in hc.thresholds()["weights"]})),
                             encoding="utf-8")
            self.assertEqual(run("score", str(empty))[0], 2)
            bad = Path(tmp, "bad.json")
            bad.write_text(json.dumps({"format": "other"}), encoding="utf-8")
            self.assertEqual(run("score", str(bad))[0], 1)
            hist = Path(tmp, "history.jsonl")
            hist.write_text(json.dumps(hc.score(results())["history_line"]) + "\n\n", encoding="utf-8")
            self.assertEqual(run("history", str(hist), str(FIXTURE))[0], 0)
            self.assertEqual(run("history", str(Path(tmp, "missing.jsonl")), str(FIXTURE))[0], 0)
        self.assertEqual(run("score")[0], 64)


if __name__ == "__main__":
    unittest.main()
