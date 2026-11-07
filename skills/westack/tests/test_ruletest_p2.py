"""P2 ruletest items (1.0.0-alpha.5, unreleased): WA-24 errored rules, WA-25 fail-closed rule errors, WA-26 decision
records, WA-27 the closed vocabulary and the matrix revision, WA-28 the probe-corpus diff.

Every check runs the real script on real files. A rule that fails to evaluate is made by replacing the matcher
function of a loaded copy (re and fnmatch do not raise on ordinary input), and each property has a broken copy of
the script's own source with one statement changed."""
import contextlib
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import unittest

import test_ruletest as base

SCRIPT = base.SCRIPT
rule, load, mutated, source = base.rule, base.load, base.mutated, base.source

MATRIX = {"rule_vocabulary": {"revision": 3, "tools": ["shell", "read", "edit"], "path_classes": ["secret", "ci-config"]}}

ALLOW_PUSH = rule("allow-push", "allow", "git push", "git push origin main", "git pull", kind="prefix", layer="user")
NO_FORCE = rule("no-force-push", layer="project")
NO_DROP = rule("no-drop", "deny", "drop database", "drop database prod", "drop table old", kind="prefix",
               unresolved="drop database", alternate="drop database  prod", twin="drop database old")
PROBES = ["git push --force origin main", "git push origin main", "git pull"]


def sha256(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode("utf-8")).hexdigest()


def boom(command):
    raise RuntimeError("the matcher failed")


class P2Base(base.Base):
    def corpus(self, probes=None, name="probes.json"):
        return self.write({"probes": PROBES if probes is None else probes}, name)

    def matrix(self, document=None, name="matrix.json"):
        return self.write(MATRIX if document is None else document, name)

    def run_args(self, *args, module=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = (module or self.module or load()).main([str(a) for a in args])
        return code, json.loads(out.getvalue())

    def faulty(self, *ids):
        """A copy of the script whose matcher raises for a rule whose pattern is one of `ids`."""
        module = load()
        real = module.matcher

        def matcher(kind, pattern):
            return boom if pattern in ids else real(kind, pattern)

        module.matcher = matcher
        return module


class ErroredRules(P2Base):
    """WA-24: matched, did not match and failed to evaluate are three outcomes; errored ids are listed apart."""

    def test_a_rule_that_fails_to_evaluate_is_listed_as_errored_apart_from_passed_and_failed(self):
        module = self.faulty("boom")
        document = {"rules": [rule("ok"), rule("broken", pattern="boom", match="boom now", no_match="calm"),
                              rule("wrong", pattern="git push", match="git pull", no_match="git status")]}
        code, report = self.run_file(document, module=module)
        self.assertEqual((code, report["status"]), (1, "failed"))
        self.assertEqual(report["errored"], ["broken"])
        self.assertEqual([r["status"] for r in report["rules"]], ["passed", "errored", "failed"])
        self.assertIn(("broken", "evaluation-error"), self.codes(report))
        self.assertNotIn(("broken", "must-match-failed"), self.codes(report), "an error is not a miss")

    def test_a_file_without_errors_has_an_empty_errored_list(self):
        code, report = self.run_file({"rules": [rule()]})
        self.assertEqual((code, report["errored"]), (0, []))

    def test_a_copy_that_folds_the_error_into_did_not_match_reports_a_miss_not_an_error(self):
        broken = mutated("raise Unevaluable(type(exc).__name__ + \": \" + str(exc)) from None", "return False")
        module = broken
        real = module.matcher
        module.matcher = lambda kind, pattern: boom if pattern == "boom" else real(kind, pattern)
        document = {"rules": [rule("broken", pattern="boom", match="boom now", no_match="calm")]}
        code, report = self.run_file(document, module=module)
        self.assertEqual(report["errored"], [], "the broken copy lost the error")
        self.assertIn(("broken", "must-match-failed"), self.codes(report))
        self.assertNotIn(("broken", "evaluation-error"), self.codes(report))


class FailClosedDecisions(P2Base):
    """WA-25: an errored allow or ask rule grants nothing; an errored deny still denies."""

    def prepared(self, *rules):
        module = load()
        return module, module.prepare({"rules": list(rules)})

    def test_an_errored_allow_grants_nothing_and_an_errored_deny_still_denies(self):
        module, prepared = self.prepared(ALLOW_PUSH, rule("allow-boom", "allow", "boom", "boom now", "calm", kind="prefix"),
                                         NO_FORCE)
        by_id = {r["id"]: r for r in prepared}
        by_id["allow-boom"]["hit"] = boom
        grant = module.decide(prepared, "boom now")
        self.assertEqual((grant["verdict"], grant["default"], grant["errored"]), ("deny", True, ["allow-boom"]))
        self.assertEqual(grant["decided_by"], [])
        by_id["no-force-push"]["hit"] = boom
        deny = module.decide(prepared, "git push origin main")
        self.assertEqual(deny["verdict"], "deny")
        self.assertEqual([d["id"] for d in deny["decided_by"]], ["no-force-push"])
        self.assertTrue(deny["decided_by"][0]["errored"])
        self.assertEqual([d["id"] for d in deny["overridden"]], ["allow-push"])
        self.assertEqual(sorted(deny["errored"]), ["allow-boom", "no-force-push"])

    def test_an_errored_ask_rule_grants_nothing_so_the_default_applies(self):
        module, prepared = self.prepared(rule("ask-rm", "ask", "rm -r*", "rm -rf build", "rm file", kind="glob"))
        prepared[0]["hit"] = boom
        got = module.decide(prepared, "rm -rf build")
        self.assertEqual((got["verdict"], got["default"], got["errored"]), ("deny", True, ["ask-rm"]))

    def test_a_copy_that_skips_an_errored_deny_lets_the_command_through(self):
        for module, expected in ((load(), "deny"), (mutated('hit = rule["effect"] == "deny"', "hit = False"), "allow")):
            prepared = module.prepare({"rules": [ALLOW_PUSH, NO_FORCE]})
            next(r for r in prepared if r["id"] == "no-force-push")["hit"] = boom
            self.assertEqual(module.decide(prepared, "git push origin main")["verdict"], expected)

    def test_selectors_that_are_exact_or_prefix_cannot_fail_to_evaluate(self):
        module, prepared = self.prepared(rule("p", "deny", "git push", "git push x", "git pull", kind="prefix"))
        self.assertEqual(module.decide(prepared, "\x00\udcff weird")["errored"], [])


class DecisionRecords(P2Base):
    """WA-26: a decision names its deciding rules and layer, the rule-set hash and the input fingerprint."""

    def setUp(self):
        super().setUp()
        self.rules = self.write({"rules": [ALLOW_PUSH, NO_FORCE]}, "rules.json")
        self.corpus_path = self.corpus()

    def record(self, probe="git push --force origin main", module=None):
        code, report = self.run_args(self.rules, "--corpus", self.corpus_path, module=module)
        self.assertEqual(code, 0, report)
        return next(d for d in report["corpus"]["decisions"] if d["probe"] == probe)

    def test_a_denied_command_names_the_deny_rule_its_layer_and_the_files_hash(self):
        got = self.record()
        self.assertEqual(got["verdict"], "deny")
        self.assertEqual(got["decided_by"], [{"id": "no-force-push", "layer": "project", "effect": "deny"}])
        self.assertEqual(got["overridden"], [{"id": "allow-push", "layer": "user", "effect": "allow"}])
        self.assertEqual(got["rules_sha256"], sha256(self.rules.read_bytes()))
        self.assertEqual(got["input_sha256"], sha256("git push --force origin main"))
        self.assertFalse(got["default"])

    def test_an_empty_decided_by_means_default_deny(self):
        got = self.record("git pull")
        self.assertEqual((got["verdict"], got["decided_by"], got["default"]), ("deny", [], True))

    def test_the_strictest_effect_wins_whatever_the_order(self):
        for order in ([ALLOW_PUSH, NO_FORCE], [NO_FORCE, ALLOW_PUSH]):
            module = load()
            prepared = module.prepare({"rules": order})
            self.assertEqual(module.decide(prepared, "git push --force origin main")["verdict"], "deny")
            self.assertEqual(module.decide(prepared, "git push origin main")["verdict"], "allow")

    def test_replaying_the_record_against_the_same_file_gives_the_same_verdict(self):
        module = load()
        got = self.record(module=module)
        replayed = module.replay(got, self.rules)
        self.assertEqual((replayed["status"], replayed["verdict"]), ("same", "deny"))

    def test_replaying_against_a_changed_file_says_the_rules_changed(self):
        module = load()
        got = self.record(module=module)
        changed = self.write({"rules": [ALLOW_PUSH]}, "changed.json")
        replayed = module.replay(got, changed)
        self.assertEqual(replayed["status"], "rules-changed")
        self.assertEqual(replayed["verdict"], "allow", "what the changed file would now decide")

    def test_a_copy_that_logs_only_the_verdict_cannot_be_replayed(self):
        broken = mutated('"rules_sha256": rules_sha256,', "")
        got = self.record(module=broken)
        self.assertNotIn("rules_sha256", got)
        with self.assertRaises(KeyError):
            broken.replay(got, self.rules)


class ClosedVocabulary(P2Base):
    """WA-27: rules name tools and path classes from a closed list; the file carries the matrix revision it passed."""

    def rules_file(self, revision=3, **fields):
        document = {"rules": [rule(**fields)]}
        if revision is not None:
            document["matrix_revision"] = revision
        return self.write(document, "vocab.json")

    def test_an_unknown_tool_is_a_load_error_naming_it(self):
        path = self.rules_file(applies_to=["Bsah"])
        code, report = self.run_args(path, "--matrix", self.matrix())
        self.assertEqual((code, report["status"]), (1, "failed"))
        self.assertEqual(self.codes(report), [("r", "unknown-tool")])
        detail = report["rules"][0]["problems"][0]["detail"]
        self.assertIn("Bsah", detail)
        self.assertIn("shell", detail, "the closed list is shown")

    def test_an_unknown_path_class_is_a_load_error_naming_it(self):
        code, report = self.run_args(self.rules_file(path_classes=["secrets"]), "--matrix", self.matrix())
        self.assertEqual((code, self.codes(report)), (1, [("r", "unknown-path-class")]))
        self.assertIn("secrets", report["rules"][0]["problems"][0]["detail"])

    def test_names_from_the_closed_list_with_the_current_revision_pass(self):
        path = self.rules_file(applies_to=["shell"], path_classes=["secret", "ci-config"])
        code, report = self.run_args(path, "--matrix", self.matrix())
        self.assertEqual((code, report["status"], report["matrix"]["status"]), (0, "passed", "current"))

    def test_a_file_stamped_with_an_older_revision_reports_stale_and_is_not_a_pass(self):
        code, report = self.run_args(self.rules_file(revision=2, applies_to=["shell"]), "--matrix", self.matrix())
        self.assertEqual((code, report["status"], report["matrix"]["status"]), (1, "stale", "stale"))
        self.assertEqual(report["file_problems"][0]["code"], "stale-matrix-revision")

    def test_a_file_that_uses_the_vocabulary_without_a_stamp_or_with_a_newer_one_fails(self):
        for revision, code_name in ((None, "no-matrix-revision"), (9, "bad-matrix-revision"), ("3", "bad-matrix-revision"),
                                    (True, "bad-matrix-revision")):
            with self.subTest(revision=revision):
                code, report = self.run_args(self.rules_file(revision, applies_to=["shell"]), "--matrix", self.matrix())
                self.assertEqual((code, report["status"]), (1, "failed"))
                self.assertEqual(report["file_problems"][0]["code"], code_name)

    def test_a_command_only_file_needs_neither_stamp_nor_matrix(self):
        path = self.write({"rules": [rule()]}, "plain.json")
        code, report = self.run_args(path, "--matrix", self.base / "absent.json")
        self.assertEqual((code, report["status"], report["matrix"]["status"]), (0, "passed", "not-used"))

    def test_a_missing_or_unusable_matrix_blocks_a_file_that_needs_it(self):
        path = self.rules_file(applies_to=["shell"])
        for name, matrix in (("absent", self.base / "absent.json"), ("no-vocabulary", self.matrix({"hosts": []})),
                             ("bad-revision", self.matrix({"rule_vocabulary": {"revision": 0, "tools": ["a"],
                                                                                "path_classes": ["b"]}}))):
            with self.subTest(case=name):
                code, report = self.run_args(path, "--matrix", matrix)
                self.assertEqual((code, report["status"]), (2, "blocked"), report)

    def test_the_default_matrix_is_the_packages_capabilities_json(self):
        document = json.loads((base.ROOT / "hosts" / "capabilities.json").read_bytes().decode("utf-8"))
        vocabulary = document["rule_vocabulary"]
        path = self.write({"matrix_revision": vocabulary["revision"],
                           "rules": [rule(applies_to=[vocabulary["tools"][0]], path_classes=[vocabulary["path_classes"][0]])]})
        code, report = self.run_args(path)
        self.assertEqual((code, report["status"]), (0, "passed"), report)

    def test_a_copy_without_the_vocabulary_check_passes_the_misspelt_tool(self):
        broken = mutated("if name not in allowed:", "if False:")
        path = self.rules_file(applies_to=["Bsah"])
        self.assertEqual(self.run_args(path, "--matrix", self.matrix(), module=broken)[0], 0)
        self.assertEqual(self.run_args(path, "--matrix", self.matrix(), module=load())[0], 1)

    def test_a_copy_that_ignores_the_stamp_passes_a_stale_file(self):
        broken = mutated("elif stamp < current:", "elif False:")
        path = self.rules_file(revision=1, applies_to=["shell"])
        self.assertEqual(self.run_args(path, "--matrix", self.matrix(), module=broken)[0], 0)
        self.assertEqual(self.run_args(path, "--matrix", self.matrix(), module=load())[0], 1)


class ProbeCorpusDiff(P2Base):
    """WA-28: run a probe corpus through two rule files; list newly allowed probes and newly errored rules; tag reach."""

    def files(self, new, old, name="new.json"):
        return self.write({"rules": new}, name), self.write({"rules": old}, "old.json")

    def diff(self, new, old, probes=None, module=None):
        new_path, old_path = self.files(new, old)
        return self.run_args(new_path, "--against", old_path, "--corpus", self.corpus(probes), module=module)

    def test_diffing_against_a_copy_that_drops_a_deny_lists_its_probe_as_newly_allowed(self):
        code, report = self.diff([ALLOW_PUSH], [ALLOW_PUSH, NO_FORCE])
        self.assertEqual((code, report["status"], report["diff"]["status"]), (1, "regressed", "regressed"))
        [item] = report["diff"]["newly_allowed"]
        self.assertEqual((item["probe"], item["old"], item["new"]), ("git push --force origin main", "deny", "allow"))
        self.assertEqual(item["old_decided_by"][0]["id"], "no-force-push")

    def test_identical_files_exit_zero_and_state_the_corpus_size(self):
        code, report = self.diff([ALLOW_PUSH, NO_FORCE], [ALLOW_PUSH, NO_FORCE])
        self.assertEqual((code, report["diff"]["status"], report["diff"]["corpus_size"]), (0, "unchanged", 3))
        self.assertEqual((report["diff"]["newly_allowed"], report["diff"]["newly_errored"]), ([], []))
        self.assertIn("inconclusive", report["diff"]["claim"])

    def test_a_deny_narrowed_to_a_smaller_match_set_is_a_change_although_both_sides_still_deny(self):
        narrower = rule("no-force-push", pattern=r"git push --force origin", match="git push --force origin main",
                        no_match="git push origin main", unresolved="git push --force origin",
                        alternate="git push --force origin dev", twin="git push --force origin main", layer="project")
        code, report = self.diff([narrower], [NO_FORCE], probes=["git push origin main --force"])
        self.assertEqual(code, 0)
        self.assertEqual(report["diff"]["status"], "changed")
        self.assertEqual(report["diff"]["newly_allowed"], [])
        self.assertEqual(report["diff"]["match_set_changes"],
                         [{"id": "no-force-push", "gained": [], "lost": ["git push origin main --force"]}])
        verdicts = {d["verdict"] for d in report["corpus"]["decisions"]}
        self.assertEqual(verdicts, {"deny"}, "the new side still denies, by default")

    def test_a_copy_that_compares_verdicts_only_calls_the_narrowed_deny_unchanged(self):
        broken = mutated("changes.append(", "list.append([], ")
        narrower = rule("no-force-push", pattern=r"git push --force origin", match="git push --force origin main",
                        no_match="git push origin main", unresolved="git push --force origin",
                        alternate="git push --force origin dev", twin="git push --force origin main", layer="project")
        code, report = self.diff([narrower], [NO_FORCE], probes=["git push origin main --force"], module=broken)
        self.assertEqual(report["diff"]["status"], "unchanged")

    def test_a_rule_that_errors_only_in_the_new_file_is_newly_errored(self):
        module = self.faulty("newly-broken")
        broke = rule("watch", "deny", "newly-broken", "newly-broken x", "calm", kind="regex",
                     unresolved="newly-broken", alternate="newly-broken y", twin="newly-broken z", layer="project")
        fine = dict(broke, pattern="never-matches-anything")
        fine.update(must_match="never-matches-anything x", unresolved="never-matches-anything",
                    alternate="never-matches-anything y", twin="never-matches-anything z")
        new_prepared = module.prepare({"rules": [broke]})
        old_prepared = module.prepare({"rules": [fine]})
        result = module.diff(new_prepared, old_prepared, ["newly-broken now", "calm"], "n" * 64, "o" * 64)
        self.assertEqual(result["newly_errored"], ["watch"])
        self.assertEqual(result["status"], "regressed")

    def test_each_rule_is_tagged_matched_shadowed_or_never_reached(self):
        shadowed = rule("allow-force", "allow", "git push --force", "git push --force origin main", "git status",
                        kind="prefix")
        new_path, old_path = self.files([NO_FORCE, shadowed, NO_DROP, ALLOW_PUSH], [NO_FORCE])
        code, report = self.run_args(new_path, "--against", old_path, "--corpus", self.corpus(["git push --force origin main"]))
        tags = report["corpus"]["reach"]
        self.assertEqual(tags, {"no-force-push": "matched", "allow-force": "shadowed", "no-drop": "never-reached",
                                "allow-push": "shadowed"})

    def test_an_empty_or_unreadable_corpus_or_old_file_is_blocked_not_clean(self):
        new_path, old_path = self.files([ALLOW_PUSH], [ALLOW_PUSH])
        cases = {"empty": ("--corpus", self.corpus([])), "absent": ("--corpus", self.base / "absent.json"),
                 "blank-probe": ("--corpus", self.corpus(["git pull", ""]))}
        for name, args in cases.items():
            with self.subTest(case=name):
                code, report = self.run_args(new_path, "--against", old_path, *args)
                self.assertEqual((code, report["status"]), (2, "blocked"), report)
        bad_old = self.write({"rules": [rule(pattern="git (push")]}, "old-bad.json")
        code, report = self.run_args(new_path, "--against", bad_old, "--corpus", self.corpus())
        self.assertEqual((code, report["status"]), (2, "blocked"))

    def test_against_without_a_corpus_is_a_usage_error(self):
        new_path, old_path = self.files([ALLOW_PUSH], [ALLOW_PUSH])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(load().main([str(new_path), "--against", str(old_path)]), 64)
        self.assertIn("--against needs --corpus", err.getvalue())

    def test_a_deny_that_becomes_an_ask_is_loosened_but_not_newly_allowed(self):
        ask = dict(NO_FORCE, effect="ask")
        code, report = self.diff([ask], [NO_FORCE], probes=["git push --force origin main"])
        self.assertEqual((code, report["diff"]["newly_allowed"]), (1, []))
        self.assertEqual([i["new"] for i in report["diff"]["loosened"]], ["ask"])

    def test_a_copy_that_lists_nothing_as_newly_allowed_is_caught(self):
        broken = mutated("newly_allowed if n[\"verdict\"] == \"allow\" else loosened", "loosened")
        code, report = self.diff([ALLOW_PUSH], [ALLOW_PUSH, NO_FORCE], module=broken)
        self.assertEqual(report["diff"]["newly_allowed"], [])
        self.assertEqual(self.diff([ALLOW_PUSH], [ALLOW_PUSH, NO_FORCE], module=load())[1]["diff"]["status"], "regressed")


class P2Cli(P2Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                              timeout=60)

    def test_the_cli_diff_exits_one_on_a_regression_and_writes_nothing(self):
        new_path = self.write({"rules": [ALLOW_PUSH]}, "new.json")
        old_path = self.write({"rules": [ALLOW_PUSH, NO_FORCE]}, "old.json")
        corpus = self.corpus()
        before = sorted(p.name for p in self.base.iterdir())
        done = self.run_cli(new_path, "--against", old_path, "--corpus", corpus)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["diff"]["status"], "regressed")
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), before)
        self.assertEqual(self.run_cli(new_path, "--against", new_path, "--corpus", corpus).returncode, 0)

    def test_the_script_and_these_tests_are_lf_only(self):
        for path in (SCRIPT, pathlib.Path(__file__)):
            self.assertNotIn(b"\r", path.read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
