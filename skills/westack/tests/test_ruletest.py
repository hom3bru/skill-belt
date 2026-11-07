"""GS-36: ruletest.py rejects a guard rule that disagrees with its own examples, when the rule file loads.

The checks run the real CLI on real files. Each check can fail: BrokenCopyTests runs the same cases against copies
of the script's own source with one statement changed (a probe never evaluated, a prefix with no word boundary, an
empty rule list passing) and requires those copies to be caught."""
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
SCRIPT = ROOT / "scripts" / "ruletest.py"


def source():
    return SCRIPT.read_bytes().decode("utf-8")


def load(text=None):
    """The real script, or a mutated copy of its source, as a module of its own."""
    module = types.ModuleType("ruletest_under_test")
    module.__file__ = str(SCRIPT)
    exec(compile(source() if text is None else text, str(SCRIPT), "exec"), module.__dict__)
    return module


def mutated(old, new):
    text = source()
    if text.count(old) != 1:
        raise AssertionError("a broken copy needs exactly one occurrence of: " + old)
    return load(text.replace(old, new))


def rule(rule_id="r", effect="deny", pattern="git push .*--force", match="git push --force origin main",
         no_match="git push origin main", extras=True, **more):
    """A rule object. A deny or ask rule also gets the three extra example classes (WA-23), copied from the first
    must-match example so a test of some other property is not about them; the WA-23 tests pass their own."""
    body = {"id": rule_id, "effect": effect, "pattern": pattern, "must_match": match, "must_not_match": no_match}
    if extras and effect in ("deny", "ask"):
        first = match[0] if isinstance(match, list) and match else match
        sample = first if isinstance(first, str) and first.strip() else "git push --force origin main"
        negatives = len(no_match) if isinstance(no_match, list) else 1
        body.update(unresolved=sample, alternate=sample, twin=[sample] * max(negatives, 1))
    body.update(more)
    return {key: value for key, value in body.items() if value is not None}


# Extra examples (WA-23) that fit the default pattern, and the pattern "git push --force".
COMPLETE_EXTRAS = {"unresolved": "git push --force $BRANCH", "alternate": "git push origin main --force",
                   "twin": "git push --force origin main"}
FORCE_ONLY = {"unresolved": "git push --force $BRANCH", "alternate": "git push --force origin",
              "twin": "git push --force origin main"}
# A realistic deny rule that covers both spellings of the flag, with all five example classes.
NO_FORCE = {"pattern": r"git push\b.*(--force\b|-f\b)", "match": "git push --force origin main",
            "no_match": "git push origin main", "unresolved": "git push --force $BRANCH",
            "alternate": "git push origin main -f", "twin": "git push -f origin main"}


class Base(unittest.TestCase):
    module = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-ruletest-")
        self.base = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, document, name="rules.json", raw=None):
        path = self.base / name
        path.write_bytes(raw if raw is not None else json.dumps(document).encode("utf-8"))
        return path

    def run_file(self, document, module=None, **kwargs):
        """(exit code, report) from main() on a file holding the document."""
        module = module or self.module or load()
        path = self.write(document, **kwargs)
        return self.run_path(path, module)

    def run_path(self, path, module=None):
        module = module or self.module or load()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = module.main([str(path)])
        return code, json.loads(out.getvalue())

    def codes(self, report):
        return [(r["id"], p["code"]) for r in report["rules"] for p in r["problems"]]


class RuleAgreement(Base):
    def test_rules_that_agree_with_their_examples_pass(self):
        code, report = self.run_file({"rules": [
            rule("no-force-push"),
            rule("status-ok", "allow", "git status", "git status --short", "git statusx", kind="prefix"),
            rule("ask-recursive-rm", "ask", "rm -r*", "rm -rf build", "rm file.txt", kind="glob")]})
        self.assertEqual((code, report["status"], report["checked"]), (0, "passed", 3), report)
        self.assertEqual(self.codes(report), [])

    def test_a_rule_that_misses_its_own_must_match_example_is_rejected_naming_it(self):
        code, report = self.run_file({"rules": [rule(pattern="git push --force", match="git push -f origin", **FORCE_ONLY)]})
        self.assertEqual((code, report["status"]), (1, "failed"))
        self.assertEqual(self.codes(report), [("r", "must-match-failed")])
        self.assertIn("git push -f origin", report["rules"][0]["problems"][0]["detail"])

    def test_a_rule_that_over_reaches_its_must_not_example_is_rejected_naming_it(self):
        code, report = self.run_file({"rules": [rule("allow-git", "allow", "git", "git status", "git push --force",
                                                     kind="prefix")]})
        self.assertEqual(code, 1)
        self.assertEqual(self.codes(report), [("allow-git", "must-not-match-matched")])
        self.assertIn("git push --force", report["rules"][0]["problems"][0]["detail"])

    def test_every_example_in_a_list_must_hold_and_the_failing_one_is_named(self):
        code, report = self.run_file({"rules": [rule(match=["git push --force a", "git push origin"],
                                                     no_match=["git push a", "git push --force-with-lease"])]})
        self.assertEqual(code, 1)
        self.assertEqual(self.codes(report), [("r", "must-match-failed"), ("r", "must-not-match-matched")])
        details = " ".join(p["detail"] for p in report["rules"][0]["problems"])
        self.assertIn("git push origin", details)
        self.assertIn("--force-with-lease", details)
        self.assertNotIn("'git push a'", details)
        self.assertNotIn("git push --force a", details)

    def test_a_prefix_stops_at_a_word_boundary(self):
        code, report = self.run_file({"rules": [rule("pu", "deny", "git pu", "git pu now", "git push", kind="prefix")]})
        self.assertEqual((code, report["status"]), (0, "passed"), report)
        code, report = self.run_file({"rules": [rule("exact", "deny", "git pull", "git pull", "git pull-request",
                                                     kind="prefix")]})
        self.assertEqual(code, 0, report)

    def test_a_glob_covers_the_whole_command(self):
        code, report = self.run_file({"rules": [rule("g", "deny", "curl *", "curl http://x", "wget http://x",
                                                     kind="glob")]})
        self.assertEqual(code, 0, report)
        code, report = self.run_file({"rules": [rule("g", "deny", "curl", "curl http://x", "wget http://x", kind="glob",
                                                     unresolved="curl", alternate="curl", twin="curl")]})
        self.assertEqual(self.codes(report), [("g", "must-match-failed")])


class RuleShape(Base):
    def test_a_rule_without_a_pair_of_examples_is_rejected(self):
        for name, body in (("no-match", rule(match=None)), ("no-counter", rule(no_match=None)),
                           ("empty-list", rule(match=[])), ("blank", rule(no_match="   ")),
                           ("not-text", rule(match=5)), ("blank-in-list", rule(match=["git push --force a", ""]))):
            with self.subTest(case=name):
                code, report = self.run_file({"rules": [body]})
                self.assertEqual(code, 1, report)
                self.assertTrue({c for _, c in self.codes(report)} & {"no-must-match", "no-must-not-match"}, report)

    def test_a_pattern_that_cannot_be_used_is_rejected(self):
        for name, body in (("bad-regex", rule(pattern="git (push")), ("empty", rule(pattern="")),
                           ("not-text", rule(pattern=3)), ("too-long", rule(pattern="a" * 5000))):
            with self.subTest(case=name):
                code, report = self.run_file({"rules": [body]})
                self.assertEqual(code, 1, report)
                self.assertEqual(self.codes(report), [("r", "bad-pattern")], report)

    def test_unknown_effect_unknown_kind_missing_or_repeated_id_are_rejected(self):
        code, report = self.run_file({"rules": [rule(effect="permit"), rule("k", kind="fuzzy"), rule(rule_id=None),
                                                rule("same"), rule("same")]})
        self.assertEqual(code, 1)
        found = {c for _, c in self.codes(report)}
        self.assertTrue({"bad-effect", "bad-kind", "no-id", "duplicate-id"} <= found, found)

    def test_a_rule_that_is_not_an_object_is_rejected(self):
        code, report = self.run_file({"rules": ["git push", rule()]})
        self.assertEqual(code, 1)
        self.assertEqual(report["checked"], 2)
        self.assertEqual(report["rules"][0]["problems"][0]["code"], "not-an-object")

    def test_one_bad_rule_fails_the_file_and_the_good_ones_are_still_reported(self):
        code, report = self.run_file({"rules": [rule("good"), rule("bad", pattern="nothing here")]})
        self.assertEqual((code, report["status"]), (1, "failed"))
        self.assertEqual([r["status"] for r in report["rules"]], ["passed", "failed"])


class ExtraExampleClasses(Base):
    """WA-23: a deny or ask rule also carries an input with the operand missing or unresolved, an alternate spelling of
    the target and a minimal positive twin of each must-not example, and the rule must match all of them. Allow rules
    keep the two older classes. The cases name the code each failure must produce."""

    def test_a_deny_or_ask_rule_with_all_five_classes_passes(self):
        for effect in ("deny", "ask"):
            with self.subTest(effect=effect):
                code, report = self.run_file({"rules": [rule(effect=effect, **NO_FORCE)]})
                self.assertEqual((code, report["status"]), (0, "passed"), report)

    def test_a_deny_or_ask_rule_missing_a_class_is_rejected_naming_the_class(self):
        for effect in ("deny", "ask"):
            for name in ("unresolved", "alternate", "twin"):
                with self.subTest(effect=effect, missing=name):
                    code, report = self.run_file({"rules": [rule(effect=effect, **dict(NO_FORCE, **{name: None}))]})
                    self.assertEqual(code, 1, report)
                    self.assertEqual(self.codes(report), [("r", "no-%s-example" % name)], report)

    def test_a_blank_or_non_text_extra_example_counts_as_missing(self):
        for value in ("   ", 5, [], ["git push -f origin", ""]):
            with self.subTest(value=value):
                code, report = self.run_file({"rules": [rule(**dict(NO_FORCE, alternate=value))]})
                self.assertEqual((code, self.codes(report)), (1, [("r", "no-alternate-example")]), report)

    def test_an_allow_rule_keeps_the_two_older_classes_and_checks_extras_it_carries(self):
        code, report = self.run_file({"rules": [rule("status-ok", "allow", "git status", "git status --short",
                                                     "git statusx", kind="prefix")]})
        self.assertEqual((code, report["status"]), (0, "passed"), report)
        code, report = self.run_file({"rules": [rule("status-ok", "allow", "git status", "git status --short",
                                                     "git statusx", kind="prefix", alternate="git stat")]})
        self.assertEqual((code, self.codes(report)), (1, [("status-ok", "alternate-failed")]), report)

    def test_a_rule_that_misses_an_alternate_spelling_fails_that_example_alone(self):
        # "git push --force" agrees with its must-match and must-not examples, so the two older classes pass it
        spelled = dict(NO_FORCE, pattern="git push --force", alternate="git push -f origin main",
                       twin="git push --force origin")
        code, report = self.run_file({"rules": [rule(**spelled)]})
        self.assertEqual((code, self.codes(report)), (1, [("r", "alternate-failed")]), report)
        self.assertIn("git push -f origin main", report["rules"][0]["problems"][0]["detail"])
        older = dict(spelled, effect="allow", unresolved=None, alternate=None, twin=None)
        self.assertEqual(self.run_file({"rules": [rule(**older)]})[0], 0)

    def test_a_rule_that_does_not_fire_without_its_operand_fails_the_unresolved_example(self):
        code, report = self.run_file({"rules": [rule(pattern=r"rm -rf \S+", match="rm -rf /tmp/build",
                                                     no_match="rm -f /tmp/build", unresolved="rm -rf",
                                                     alternate="sudo rm -rf /tmp/build", twin="rm -rf /tmp/other")]})
        self.assertEqual((code, self.codes(report)), (1, [("r", "unresolved-failed")]), report)
        self.assertIn("'rm -rf'", report["rules"][0]["problems"][0]["detail"])

    def test_a_twin_must_match_and_pair_with_each_must_not_example(self):
        code, report = self.run_file({"rules": [rule(**dict(NO_FORCE, twin="git push origin main"))]})
        self.assertEqual((code, self.codes(report)), (1, [("r", "twin-failed")]), report)
        two = dict(NO_FORCE, no_match=["git push origin main", "git pull -f"], twin=["git push -f origin main"])
        code, report = self.run_file({"rules": [rule(**two)]})
        self.assertEqual((code, self.codes(report)), (1, [("r", "twin-count")]), report)
        paired = dict(two, twin=["git push -f origin main", "git push --force"])
        self.assertEqual(self.run_file({"rules": [rule(**paired)]})[0], 0)

    def test_the_report_says_what_the_extra_classes_cannot_judge(self):
        claim = " ".join(self.run_file({"rules": [rule(**NO_FORCE)]})[1]["claim"].split())
        for words in ("different spelling", "minimal"):
            self.assertIn(words, claim)


class NothingToCheck(Base):
    """CM-43: no target, malformed input or an unreadable file is blocked, never a pass."""

    def test_a_file_with_no_rules_is_blocked_not_passed(self):
        for name, document in (("empty-list", {"rules": []}), ("no-key", {}), ("list", []), ("not-a-list", {"rules": 5}),
                               ("null", None)):
            with self.subTest(case=name):
                code, report = self.run_file(document)
                self.assertEqual((code, report["status"]), (2, "blocked"), report)
                self.assertIn("reason", report)

    def test_malformed_unreadable_or_oversized_input_is_blocked(self):
        for name, raw in (("not-json", b"{ rules: [}"), ("not-utf8", b"\xff\xfe\x00bad"), ("empty-file", b""),
                          ("deep", b"[" * 5000 + b"]" * 5000)):
            with self.subTest(case=name):
                code, report = self.run_file(None, raw=raw)
                self.assertEqual((code, report["status"]), (2, "blocked"), report)
        code, report = self.run_path(self.base / "absent.json")
        self.assertEqual((code, report["status"]), (2, "blocked"))
        module = load()
        module.LIMIT = 100
        code, report = self.run_file({"rules": [rule()]}, module=module)
        self.assertEqual((code, report["status"]), (2, "blocked"))
        self.assertIn("larger", report["reason"])

    def test_a_byte_order_mark_is_accepted(self):
        raw = b"\xef\xbb\xbf" + json.dumps({"rules": [rule()]}).encode("utf-8")
        code, report = self.run_file(None, raw=raw)
        self.assertEqual((code, report["status"]), (0, "passed"))


class Cli(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], capture_output=True, text=True, timeout=60)

    def test_exit_codes_json_and_no_files_written(self):
        good = self.write({"rules": [rule()]}, "good.json")
        bad = self.write({"rules": [rule(pattern="x")]}, "bad.json")
        empty = self.write({"rules": []}, "empty.json")
        before = sorted(p.name for p in self.base.iterdir())
        results = {name: self.run_cli(str(path)) for name, path in (("good", good), ("bad", bad), ("empty", empty))}
        self.assertEqual({k: v.returncode for k, v in results.items()}, {"good": 0, "bad": 1, "empty": 2})
        for name, done in results.items():
            self.assertEqual(json.loads(done.stdout)["format"], "westack-ruletest-1", name)
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), before, "the helper must write nothing")

    def test_usage_errors_exit_64(self):
        self.assertEqual(self.run_cli().returncode, 64)
        self.assertEqual(self.run_cli("a.json", "b.json").returncode, 64)

    def test_the_report_states_what_a_pass_does_not_mean(self):
        report = json.loads(self.run_cli(str(self.write({"rules": [rule()]}))).stdout)
        claim = " ".join(report["claim"].split())
        for words in ("runs nothing", "own examples", "not a sandbox"):
            self.assertIn(words, claim)


class BrokenCopyTests(Base):
    """Each copy changes one statement of the real source. The cases it must be caught by are named."""

    def test_a_copy_that_never_evaluates_must_match_accepts_a_rule_that_misses_it(self):
        broken = mutated("if not hit(example):", "if False:")
        document = {"rules": [rule(pattern="git push --force", match="git push -f origin", **FORCE_ONLY)]}
        self.assertEqual(self.run_file(document, module=broken)[0], 0)
        self.assertEqual(self.run_file(document, module=load())[0], 1)

    def test_a_copy_that_never_evaluates_must_not_match_accepts_an_over_reaching_rule(self):
        broken = mutated("if hit(example):", "if False:")
        document = {"rules": [rule("allow-git", "allow", "git", "git status", "git push --force", kind="prefix")]}
        self.assertEqual(self.run_file(document, module=broken)[0], 0)
        self.assertEqual(self.run_file(document, module=load())[0], 1)

    def test_a_copy_with_a_prefix_that_has_no_word_boundary_is_caught(self):
        broken = mutated("command.startswith(pattern + \" \")", "command.startswith(pattern)")
        document = {"rules": [rule("pu", "deny", "git pu", "git pu now", "git push", kind="prefix")]}
        self.assertEqual(self.run_file(document, module=broken)[0], 1)
        self.assertEqual(self.run_file(document, module=load())[0], 0)

    def test_a_copy_that_lets_a_rule_without_examples_through_is_caught(self):
        broken = mutated("if not good:", "if False:")
        document = {"rules": [rule(match=None, no_match=None, **COMPLETE_EXTRAS)]}
        self.assertEqual(self.run_file(document, module=broken)[0], 0)
        self.assertEqual(self.run_file(document, module=load())[0], 1)

    def test_a_copy_that_passes_an_empty_rule_list_is_caught(self):
        broken = mutated("if not isinstance(rules, list) or not rules:", "if not isinstance(rules, list):")
        self.assertEqual(self.run_file({"rules": []}, module=broken)[0], 0)
        self.assertEqual(self.run_file({"rules": []}, module=load())[0], 2)

    def test_a_copy_that_lets_an_unusable_pattern_through_is_caught(self):
        broken = mutated("except re.error:", "except ZeroDivisionError:")
        with self.assertRaises(Exception):
            self.run_file({"rules": [rule(pattern="git (push")]}, module=broken)
        self.assertEqual(self.run_file({"rules": [rule(pattern="git (push")]}, module=load())[0], 1)

    def test_a_copy_that_does_not_require_the_extra_classes_accepts_a_deny_rule_without_them(self):
        broken = mutated("if name in rule or effect in EXTRA_EFFECTS:", "if name in rule:")
        for name in ("unresolved", "alternate", "twin"):
            with self.subTest(missing=name):
                document = {"rules": [rule(**dict(NO_FORCE, **{name: None}))]}
                self.assertEqual(self.run_file(document, module=broken)[0], 0)
                self.assertEqual(self.run_file(document, module=load())[0], 1)

    def test_a_copy_that_never_evaluates_an_extra_example_accepts_a_rule_that_misses_it(self):
        broken = mutated("if not hit(sample):", "if False:")
        document = {"rules": [rule(**dict(NO_FORCE, pattern="git push --force", twin="git push --force origin"))]}
        self.assertEqual(self.run_file(document, module=broken)[0], 0)
        self.assertEqual(self.run_file(document, module=load())[0], 1)

    def test_a_copy_that_also_requires_the_classes_of_an_allow_rule_is_caught(self):
        broken = mutated("effect in EXTRA_EFFECTS", "effect in EFFECTS")
        document = {"rules": [rule("status-ok", "allow", "git status", "git status --short", "git statusx",
                                   kind="prefix")]}
        self.assertEqual(self.run_file(document, module=broken)[0], 1)
        self.assertEqual(self.run_file(document, module=load())[0], 0)

    def test_a_copy_that_ignores_the_twin_count_accepts_an_unpaired_twin(self):
        broken = mutated("len(got) != len(must_not)", "False")
        document = {"rules": [rule(**dict(NO_FORCE, no_match=["git push origin main", "git pull -f"]))]}
        self.assertEqual(self.run_file(document, module=broken)[0], 0)
        self.assertEqual(self.run_file(document, module=load())[0], 1)


class ChangelogAndEndings(unittest.TestCase):
    def test_the_script_and_its_tests_are_lf_only(self):
        for path in (SCRIPT, pathlib.Path(__file__)):
            with self.subTest(file=path.name):
                self.assertNotIn(b"\r", path.read_bytes())


if __name__ == "__main__":
    unittest.main()
