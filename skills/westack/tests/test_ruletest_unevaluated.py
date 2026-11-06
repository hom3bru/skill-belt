"""OC-9 (seven-repos and OpenCode addendum, 1.0.0-alpha.12): a rule naming an effect, kind, tool class or path class
the checker does not know is `unevaluated`, listed apart from matched, unmatched and errored, so a deny cannot fall
silent after a vocabulary change.

Every check runs the real script on real files, and each property has a broken copy of the script's own source with
one statement changed: one that stops listing such rules, and one that drops them before deciding a probe corpus (the
permissive reader the OpenCode policy docs describe), which lets the deny they carried stop applying."""
import json
import unittest

import test_ruletest as base
import test_ruletest_p2 as p2

rule, load, mutated = base.rule, base.load, base.mutated

ALLOW_PUSH = p2.ALLOW_PUSH
# A deny written for a newer reader: its selector kind is one this checker does not know.
NEWER_DENY = rule("no-force-push", kind="path-glob")
PROBES = ["git push --force origin main", "git push origin main"]


class UnevaluatedRules(p2.P2Base):
    def test_a_rule_with_a_kind_the_checker_does_not_know_is_listed_unevaluated_not_unmatched(self):
        code, report = self.run_file({"rules": [ALLOW_PUSH, NEWER_DENY]})
        self.assertEqual((code, report["status"]), (1, "failed"))
        self.assertEqual(report["unevaluated"], ["no-force-push"])
        self.assertEqual([r["status"] for r in report["rules"]], ["passed", "unevaluated"])
        self.assertIn(("no-force-push", "bad-kind"), self.codes(report))
        self.assertNotIn(("no-force-push", "must-match-failed"), self.codes(report), "unknown is not unmatched")
        self.assertEqual(report["errored"], [])

    def test_an_unknown_effect_is_unevaluated_too(self):
        code, report = self.run_file({"rules": [rule("r", effect="deny-unless-approved")]})
        self.assertEqual((code, report["unevaluated"]), (1, ["r"]))
        self.assertIn(("r", "bad-effect"), self.codes(report))

    def test_an_unknown_tool_or_path_class_is_unevaluated(self):
        matrix = self.matrix()
        for field, name in (("applies_to", "webfetch"), ("path_classes", "credentials")):
            with self.subTest(field=field):
                path = self.write({"matrix_revision": 3, "rules": [rule("r", **{field: [name]})]})
                code, report = self.run_args(path, "--matrix", matrix)
                self.assertEqual((code, report["status"], report["unevaluated"]), (1, "failed", ["r"]))

    def test_a_malformed_value_is_failed_not_unevaluated(self):
        # unevaluated means a name from a vocabulary this checker lacks; a number or a blank is simply broken
        for name, body in (("number", rule("r", effect=5)), ("blank", rule("r", kind="  ")),
                           ("missing", {k: v for k, v in rule("r").items() if k != "effect"})):
            with self.subTest(case=name):
                code, report = self.run_file({"rules": [body]})
                self.assertEqual((code, report["unevaluated"]), (1, []))
                self.assertEqual(report["rules"][0]["status"], "failed")

    def test_a_clean_file_has_an_empty_unevaluated_list(self):
        code, report = self.run_file({"rules": [ALLOW_PUSH, p2.NO_FORCE]})
        self.assertEqual((code, report["unevaluated"]), (0, []))

    def test_the_cli_prints_the_list(self):
        code, report = self.run_args(self.write({"rules": [ALLOW_PUSH, NEWER_DENY]}))
        self.assertEqual((code, report["unevaluated"]), (1, ["no-force-push"]))

    def test_a_copy_that_stops_listing_them_lets_the_rule_through_unlisted(self):
        broken = mutated("unevaluated = bool(foreign)", "unevaluated = False")
        code, report = self.run_file({"rules": [ALLOW_PUSH, NEWER_DENY]}, module=broken)
        self.assertEqual(report["unevaluated"], [], "the broken copy lost the list")
        self.assertEqual([r["status"] for r in report["rules"]], ["passed", "failed"])


class CorpusStaysClosed(p2.P2Base):
    """A file holding an unevaluated rule decides no probe; a reader that drops the rule lets its deny fall silent."""

    def corpus_report(self, module):
        rules = self.write({"rules": [ALLOW_PUSH, NEWER_DENY]})
        return self.run_args(rules, "--corpus", self.corpus(PROBES), module=module)

    def test_no_probe_is_decided_while_a_rule_is_unevaluated(self):
        code, report = self.corpus_report(load())
        self.assertEqual(code, 1)
        self.assertIn("skipped", report["corpus"])
        self.assertNotIn("decisions", report["corpus"])

    def test_a_copy_that_drops_the_unknown_rule_allows_the_force_push(self):
        broken = mutated('        if (rule["id"] in seen or rule.get("effect") not in EFFECTS or kind not in KINDS',
                         '        if kind not in KINDS:\n            continue\n'
                         '        if (rule["id"] in seen or rule.get("effect") not in EFFECTS or kind not in KINDS')
        code, report = self.corpus_report(broken)
        verdicts = {d["probe"]: d["verdict"] for d in report["corpus"]["decisions"]}
        self.assertEqual(verdicts["git push --force origin main"], "allow", "the deny fell silent in the broken copy")


class Docstring(unittest.TestCase):
    def test_the_docstring_names_the_outcome(self):
        text = " ".join(base.source().split())
        for phrase in ("`unevaluated`", "never read as \"did not match\"", "a deny cannot fall silent after a "
                       "vocabulary change"):
            self.assertIn(phrase, text)

    def test_the_test_file_is_lf_only(self):
        with open(__file__, "rb") as stream:
            self.assertNotIn(b"\r", stream.read())


if __name__ == "__main__":
    unittest.main()
