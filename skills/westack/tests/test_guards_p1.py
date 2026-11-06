"""P1 guards and authority group (1.0.0-alpha.4, unreleased).

GS-22: the write-target helper in evidence.py (`judge_patch`, `safe_path`), tested against real directory
links and against two broken copies of its own source (no link resolution; a text-prefix comparison).
The other items are text rules the package pins by wording: GS-01, GS-03, GS-04, GS-05, GS-18, GS-20,
GS-32, GS-36, GS-62 and CM-15. westack ships no permission engine, hook or restore tool, so those
rules have no behaviour of their own to run; the tests pin what the pages must keep saying."""
import os
import pathlib
import re
import tempfile
import types
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
EVIDENCE = ROOT / "scripts" / "evidence.py"


def text(relative):
    return (ROOT / relative).read_bytes().decode("utf-8")


def flat(relative):
    return re.sub(r"\s+", " ", text(relative))


def load_evidence(source=None):
    """The real evidence.py, or a mutated copy of its source (a broken copy), as a module of its own."""
    source = text("scripts/evidence.py") if source is None else source
    module = types.ModuleType("guards_p1_evidence")
    module.__file__ = str(EVIDENCE)
    exec(compile(source, str(EVIDENCE), "exec"), module.__dict__)
    return module


def mutated(old, new):
    """evidence.py with exactly one statement replaced: a realistic broken copy."""
    source = text("scripts/evidence.py")
    if source.count(old) != 1:
        raise AssertionError("a broken copy needs exactly one occurrence of: " + old)
    return load_evidence(source.replace(old, new))


def link_dir(link, target):
    """A directory link that needs no privilege: a junction on Windows, a symlink elsewhere."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        pathlib.Path(link).symlink_to(target, target_is_directory=True)


def unlink_dir(link):
    try:
        if os.name == "nt":
            pathlib.Path(link).rmdir()
        else:
            pathlib.Path(link).unlink()
    except OSError:
        pass  # cleanup only; TemporaryDirectory removes what is left


# Each case is one patch and the invariant that must name its refusal.
REFUSED = {
    "symlink-escape": ([("modify", "out-link/x.txt")], "escapes-root"),
    "new-file-under-linked-parent": ([("create", "out-link/new/dir/file.txt")], "escapes-root"),
    "shared-prefix-sibling": ([("create", "sib-link/new.txt")], "escapes-root"),
    "rename-target-outside": ([("rename", "inside/a.txt", "out-link/a.txt")], "escapes-root"),
    "rename-source-outside": ([("rename", "out-link/x.txt", "inside/x.txt")], "escapes-root"),
    "delete-through-a-link": ([("delete", "out-link")], "escapes-root"),
    "glob-match-through-a-link": ([("delete", "*/x.txt")], "escapes-root"),
    "unbalanced-glob": ([("delete", "inside/[abc")], "invalid-glob"),
    "embedded-double-star": ([("delete", "inside/a**b")], "invalid-glob"),
    "glob-cannot-create": ([("create", "inside/*.txt")], "invalid-glob"),
    "glob-cannot-rename": ([("rename", "inside/*.txt", "inside/b.txt")], "invalid-glob"),
    "absolute-path": ([("create", "/etc/passwd")], "not-portable"),
    "dot-dot": ([("create", "inside/../../outside/a.txt")], "not-portable"),
    "backslash": ([("create", "inside\\a.txt")], "not-portable"),
    "drive-letter": ([("create", "C:/Windows/a.txt")], "not-portable"),
    "empty-path": ([("create", "")], "not-portable"),
    "not-a-string": ([("create", None)], "not-portable"),
    "unknown-verb": ([("chmod", "inside/a.txt")], "unknown-operation"),
    "wrong-arity": ([("rename", "inside/a.txt")], "unknown-operation"),
    "nothing-to-judge": ([], "no-operations"),
}
ACCEPTED = {
    "new-file": [("create", "inside/new.txt")],
    "new-file-in-new-folders": [("create", "inside/deeper/still/new.txt")],
    "modify-through-an-inside-link": [("modify", "ok-link/a.txt")],
    "rename-inside": [("rename", "inside/a.txt", "inside/b.txt")],
    "delete-inside": [("delete", "inside/a.txt")],
    "glob-delete-inside": [("delete", "inside/*.txt")],
    "glob-matching-nothing": [("delete", "inside/*.nothing")],
}


class WriteTargetBase(unittest.TestCase):
    """A project folder with three directory links: one outside, one to a sibling that shares the project's
    name as a text prefix, and one that stays inside."""
    module = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-guards-")
        base = pathlib.Path(self.temp.name).resolve()
        self.root, outside, sibling = base / "project", base / "outside", base / "project-evil"
        for folder in (self.root / "inside", outside, sibling):
            folder.mkdir(parents=True)
        (self.root / "inside" / "a.txt").write_text("a", encoding="utf-8")
        (outside / "x.txt").write_text("outside", encoding="utf-8")
        self.links = []
        for name, target in (("out-link", outside), ("sib-link", sibling), ("ok-link", self.root / "inside")):
            link_dir(self.root / name, target)
            self.links.append(self.root / name)

    def tearDown(self):
        for link in self.links:
            unlink_dir(link)
        self.temp.cleanup()

    def judge(self, operations, module=None):
        """(None, resolved paths) when judged safe, else (invariant, error)."""
        module = module or self.module
        try:
            return None, module.judge_patch(self.root, operations)
        except module.UnsafeTarget as exc:
            return exc.invariant, exc


class WriteTargetTests(WriteTargetBase):
    module = load_evidence()

    def test_each_unsafe_patch_is_refused_with_its_named_invariant(self):
        for name, (operations, invariant) in REFUSED.items():
            with self.subTest(case=name):
                got, error = self.judge(operations)
                self.assertEqual(got, invariant, str(error))
                self.assertIn(invariant, str(error))

    def test_safe_patches_return_resolved_paths_inside_the_root(self):
        root = self.root.resolve()
        for name, operations in ACCEPTED.items():
            with self.subTest(case=name):
                got, paths = self.judge(operations)
                self.assertIsNone(got, str(paths))
                for path in paths:
                    self.assertTrue(path.is_absolute() and path.is_relative_to(root), path)

    def test_a_link_that_stays_inside_resolves_to_its_target(self):
        _, paths = self.judge([("modify", "ok-link/a.txt")])
        self.assertEqual(paths, [(self.root / "inside" / "a.txt").resolve()])

    def test_glob_expansion_lists_the_files_it_will_touch(self):
        (self.root / "inside" / "b.txt").write_text("b", encoding="utf-8")
        _, paths = self.judge([("delete", "inside/*.txt")])
        self.assertEqual(sorted(p.name for p in paths), ["a.txt", "b.txt"])

    def test_the_whole_patch_is_judged_by_its_worst_path(self):
        operations = [("create", "inside/fine.txt"), ("create", "out-link/bad.txt"), ("delete", "inside/a.txt")]
        got, error = self.judge(operations)
        self.assertEqual(got, "escapes-root")
        self.assertEqual(len(error.failures), 1, error.failures)
        self.assertIn("out-link/bad.txt", str(error))
        self.assertNotIn("fine.txt", str(error), "only the failing paths are named")

    def test_every_failing_path_is_named_not_only_the_first(self):
        got, error = self.judge([("create", "out-link/one.txt"), ("create", "sib-link/two.txt")])
        self.assertEqual(got, "escapes-root")
        self.assertEqual(len(error.failures), 2)
        self.assertTrue("one.txt" in str(error) and "two.txt" in str(error))

    def test_a_glob_wider_than_the_limit_is_refused_not_truncated(self):
        module = load_evidence()
        module.GLOB_LIMIT = 2
        for number in range(5):
            (self.root / "inside" / ("f%d.log" % number)).write_text("x", encoding="utf-8")
        got, error = self.judge([("delete", "inside/*.log")], module)
        self.assertEqual(got, "too-many-matches", str(error))

    def test_a_path_that_cannot_be_resolved_is_refused_by_name(self):
        class Looping:
            def resolve(self):
                raise OSError("too many levels of symbolic links")

        with self.assertRaises(self.module.UnsafeTarget) as caught:
            self.module._resolved(Looping())
        self.assertEqual(caught.exception.invariant, "cannot-resolve")

    def test_a_missing_or_nondirectory_root_is_an_error_not_a_pass(self):
        with self.assertRaises(OSError):
            self.module.judge_patch(self.root / "absent", [("create", "a.txt")])
        with self.assertRaises(OSError):
            self.module.judge_patch(self.root / "inside" / "a.txt", [("create", "a.txt")])

    def test_safe_path_still_contains_evidence_paths_and_names_the_invariant(self):
        self.assertTrue(self.module.safe_path(self.root, "inside/a.txt").samefile(self.root / "inside" / "a.txt"))
        for relative, invariant in (("../a", "not-portable"), ("out-link/x.txt", "escapes-root"),
                                    ("sib-link/new.txt", "escapes-root")):
            with self.subTest(path=relative):
                with self.assertRaises(ValueError) as caught:
                    self.module.safe_path(self.root, relative)
                self.assertEqual(caught.exception.invariant, invariant)

    def test_unsafe_target_is_a_value_error_so_existing_callers_still_catch_it(self):
        self.assertTrue(issubclass(self.module.UnsafeTarget, ValueError))

    def test_the_helper_names_its_limits(self):
        doc = " ".join((self.module.judge_patch.__doc__ or "").split())
        for phrase in ("not a sandbox", "does not cover", "hard link"):
            self.assertIn(phrase, doc)


class BrokenCopyTests(WriteTargetBase):
    """The checks above must be able to fail. Each broken copy is the real source with one statement changed."""
    LINK_CASES = ("symlink-escape", "new-file-under-linked-parent", "shared-prefix-sibling", "rename-target-outside",
                  "rename-source-outside", "delete-through-a-link", "glob-match-through-a-link")

    def refused(self, module, name):
        return self.judge(REFUSED[name][0], module)[0]

    def test_a_copy_that_never_resolves_links_lets_every_link_case_through(self):
        broken = mutated("return path.resolve()", "return path")
        for name in self.LINK_CASES:
            with self.subTest(case=name):
                self.assertIsNone(self.refused(broken, name), "the broken copy should accept " + name)
        # It still refuses what needs no resolution, so the difference is the missing resolution alone.
        self.assertEqual(self.refused(broken, "unbalanced-glob"), "invalid-glob")
        self.assertEqual(self.refused(broken, "dot-dot"), "not-portable")
        self.assertEqual(self.refused(load_evidence(), "symlink-escape"), "escapes-root")

    def test_a_copy_that_compares_text_prefixes_lets_the_sibling_through(self):
        broken = mutated("return resolved.is_relative_to(root)", "return str(resolved).startswith(str(root))")
        self.assertIsNone(self.refused(broken, "shared-prefix-sibling"))
        # A real outside folder still fails the text comparison, so only the sibling case separates the two.
        self.assertEqual(self.refused(broken, "symlink-escape"), "escapes-root")
        self.assertEqual(self.refused(load_evidence(), "shared-prefix-sibling"), "escapes-root")

    def test_a_copy_that_judges_only_the_first_operation_misses_the_worst_path(self):
        broken = mutated("for index, operation in enumerate(operations):", "for index, operation in enumerate(operations[:1]):")
        operations = [("create", "inside/fine.txt"), ("create", "out-link/bad.txt")]
        self.assertIsNone(self.judge(operations, broken)[0])
        self.assertEqual(self.judge(operations, load_evidence())[0], "escapes-root")


class GuardWordingTests(unittest.TestCase):
    """Each text rule keeps its gate words. Whitespace is normalised; phrases are the rule's own terms."""
    CASES = {
        "references/authority.md": {
            "GS-01": ["strictest-first", "deny beats ask beats allow", "never widen", "counts as in force"],
            "GS-03": ["An approval nobody gave is never an approval", "end of stream", "unrecognised answer",
                      "`pending` or `denied`"],
            "GS-04": ["Unattended", "would ask", "named reason", "never left waiting", "Standing allows"],
            "GS-18": ["simple command", "one denied part denies the line", "Unparsed means unknown, never low"],
            "GS-20": ["protected paths", "Secret files stay out of", "on doubt treat the path as protected"],
        },
        # the Host guard section moved from authority.md to guards.md; each pin keeps its phrases and follows its text
        "references/guards.md": {
            "GS-05": ["guard blocked", "never passes silently"],
            "GS-36": ["must match", "must not", "fails open without a word"],
            "CM-15": ["blocking code", "cannot parse its input"],
        },
        "references/isolation.md": {
            "GS-62": ["Gate a restore", "later commits", "not this task's", "pushed", "unclear", "per path",
                      "name every deletion", "bring back", "files, the conversation or both"],
        },
        "hosts/README.md": {
            "CM-15": ["Hook contract", "exit 2", "cannot parse its input", "exit 1", "fails open",
                      "leaves the original output unchanged"],
            "GS-32": ["does not cover", "inconclusive for safety"],
        },
    }

    def test_each_rule_keeps_its_gate_words(self):
        for relative, items in self.CASES.items():
            body = flat(relative)
            for item, phrases in items.items():
                for phrase in phrases:
                    with self.subTest(doc=relative, item=item, phrase=phrase):
                        self.assertIn(phrase, body)

    def test_the_diagnostic_label_stays(self):
        self.assertIn("diagnostic, not a sandbox", flat("references/guards.md"))
        self.assertIn("A diagnostic path check is not a sandbox", flat("hosts/README.md"))
        self.assertIn("hard links", flat("references/guards.md"))

    def test_reading_a_command_states_its_limit_and_rejects_prefix_grants(self):
        body = flat("references/authority.md")
        self.assertIn("`python -c`", body)
        self.assertIn("A prefix match is not a grant for the line", body)

    def test_the_router_did_not_grow(self):
        self.assertLessEqual(len(text("SKILL.md").split()), 600)


def section(body, heading):
    """The text under `## heading` up to the next heading or the Provenance line."""
    match = re.search(r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |^Provenance:|\Z)", body, re.S | re.M)
    if not match:
        raise AssertionError("no section: " + heading)
    return match[1]


LABELS = ("boundary", "heuristic", "advice")


def label_problems(note):
    """What a guard note lacks: one of the three labels and a closing statement of what it does not cover."""
    problems = [label for label in LABELS if label not in note]
    if "does not cover" not in note:
        problems.append("does not cover")
    return problems


class GuardNoteLintTests(unittest.TestCase):
    """GS-32: every guard recommendation is labelled and ends with its limits. The lint reads the pages."""
    NOTES = (("references/guards.md", "Host guard"), ("hosts/README.md", "Control labels"))

    def test_the_guard_notes_carry_a_label_and_a_does_not_cover_line(self):
        for relative, heading in self.NOTES:
            with self.subTest(note=relative + "#" + heading):
                self.assertEqual(label_problems(section(text(relative), heading)), [])

    def test_a_note_missing_its_does_not_cover_line_fails_the_lint(self):
        for relative, heading in self.NOTES:
            with self.subTest(note=relative + "#" + heading):
                broken = section(text(relative), heading).replace("does not cover", "covers")
                self.assertEqual(label_problems(broken), ["does not cover"])

    def test_a_note_missing_a_label_fails_the_lint(self):
        broken = section(text("references/guards.md"), "Host guard").replace("heuristic", "check")
        self.assertEqual(label_problems(broken), ["heuristic"])


class ChangelogAndLineEndingTests(unittest.TestCase):
    ITEMS = ("GS-01", "GS-03", "GS-04", "GS-05", "GS-18", "GS-20", "GS-22", "GS-32", "GS-36", "GS-62", "CM-15")
    TOUCHED = ("references/authority.md", "references/isolation.md", "hosts/README.md", "scripts/evidence.py",
               "tests/test_guards_p1.py")

    def test_the_changelog_cites_every_item_once_under_the_new_section(self):
        body = text("CHANGELOG.md")
        self.assertIn("## 1.0.0-alpha.4 (P1 adoption), unreleased", body)
        mine = body.split("## 1.0.0-alpha.4 (P1 adoption), unreleased")[1].split("\n## ")[0]
        for item in self.ITEMS:
            with self.subTest(item=item):
                self.assertEqual(len(re.findall(r"\b" + item + r"\b", mine)), 1)

    def test_touched_files_are_lf_only(self):
        for relative in self.TOUCHED:
            with self.subTest(file=relative):
                self.assertNotIn(b"\r", (ROOT / relative).read_bytes())

    def test_the_changelog_keeps_one_line_ending_throughout(self):
        # CHANGELOG.md has been CRLF since before this group; an edit must not leave it mixed.
        data = (ROOT / "CHANGELOG.md").read_bytes()
        crlf, lf = data.count(b"\r\n"), data.count(b"\n")
        self.assertIn(crlf, (0, lf), "mixed line endings: %d CRLF of %d lines" % (crlf, lf))


if __name__ == "__main__":
    unittest.main()
