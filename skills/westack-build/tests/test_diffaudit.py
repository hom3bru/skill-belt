"""Tests for westack-build's diffaudit.py: the delivery diff audit over saved git output.

Run from the repo root:  python -m unittest discover -s skills/westack-build/tests -v
DIFFAUDIT_UNDER_TEST=<path> points the suite at another copy (a broken-copy control).
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = pathlib.Path(os.environ.get("DIFFAUDIT_UNDER_TEST") or HERE.parent / "scripts" / "diffaudit.py")


def load():
    spec = importlib.util.spec_from_file_location("westack_build_diffaudit_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


da = load()


def modified(path, removed=(), added=(), context=("ctx",)):
    """A minimal git diff block for one modified file."""
    lines = ["diff --git a/%s b/%s" % (path, path), "index 1111111..2222222 100644", "--- a/" + path, "+++ b/" + path,
             "@@ -1,%d +1,%d @@" % (len(context) + len(removed), len(context) + len(added))]
    lines += [" " + c for c in context] + ["-" + r for r in removed] + ["+" + a for a in added]
    return "\n".join(lines) + "\n"


def new_file(path, added):
    lines = ["diff --git a/%s b/%s" % (path, path), "new file mode 100644", "index 0000000..3333333",
             "--- /dev/null", "+++ b/" + path, "@@ -0,0 +1,%d @@" % len(added)] + ["+" + a for a in added]
    return "\n".join(lines) + "\n"


def deleted_file(path, removed):
    lines = ["diff --git a/%s b/%s" % (path, path), "deleted file mode 100644", "index 3333333..0000000",
             "--- a/" + path, "+++ /dev/null", "@@ -1,%d +0,0 @@" % len(removed)] + ["-" + r for r in removed]
    return "\n".join(lines) + "\n"


def flags(report, path):
    entry = next(f for f in report["files"] if f["path"] == path)
    return set(entry["flags"])


def evidence(report, path):
    return " | ".join(next(f for f in report["files"] if f["path"] == path)["evidence"])


class Verdicts(unittest.TestCase):
    def test_an_empty_change_is_not_a_change(self):
        report = da.audit("")
        self.assertEqual((report["verdict"], report["exit_code"]), ("empty", 2))

    def test_text_that_is_not_a_diff_cannot_be_audited(self):
        with self.assertRaises(da.AuditError):
            da.audit("hello, this is not a diff\n")

    def test_an_in_scope_source_edit_is_clean(self):
        report = da.audit(modified("src/money.py", ["    return '$' + s"], ["    return symbol + s"]),
                          allow=["src/**"])
        self.assertEqual((report["verdict"], report["exit_code"]), ("clean", 0))
        self.assertEqual(flags(report, "src/money.py"), set())

    def test_an_edit_outside_the_allowed_paths_needs_a_decision(self):
        report = da.audit(modified("src/legacy.py", ["x = 1"], ["x = 2"]), allow=["src/money.py", "tests/**"])
        self.assertIn("out-of-scope", flags(report, "src/legacy.py"))
        self.assertEqual((report["verdict"], report["exit_code"]), ("needs-decision", 1))

    def test_without_allowed_paths_scope_is_reported_unchecked(self):
        report = da.audit(modified("anywhere/x.py", ["a"], ["b"]))
        self.assertEqual(report["scope"], "not-checked")
        self.assertNotIn("out-of-scope", flags(report, "anywhere/x.py"))


class ExistingTests(unittest.TestCase):
    def test_a_loosened_assertion_is_reported_with_the_removed_line(self):
        diff = modified("tests/test_receipt.py", ["        self.assertEqual(len(line), 32)"],
                        ["        self.assertLessEqual(len(line), 40)"])
        report = da.audit(diff, allow=["**"])
        self.assertIn("existing-test-changed", flags(report, "tests/test_receipt.py"))
        self.assertIn("assertion-removed", evidence(report, "tests/test_receipt.py"))
        self.assertIn("assertEqual(len(line), 32)", evidence(report, "tests/test_receipt.py"))
        self.assertEqual(report["exit_code"], 1)

    def test_an_added_skip_marker_is_reported(self):
        diff = modified("tests/test_parse.py", [], ["    @unittest.skip('flaky')"])
        report = da.audit(diff, allow=["**"])
        self.assertIn("existing-test-changed", flags(report, "tests/test_parse.py"))
        self.assertIn("skip-added", evidence(report, "tests/test_parse.py"))

    def test_javascript_focus_and_skip_markers_are_reported(self):
        for line in ("  it.skip('rounds', () => {", "  test.only('rounds', () => {", "  xit('rounds', () => {"):
            with self.subTest(line=line):
                report = da.audit(modified("src/__tests__/round.test.js", [], [line]), allow=["**"])
                self.assertIn("skip-added", evidence(report, "src/__tests__/round.test.js"))

    def test_a_removed_test_definition_is_reported(self):
        diff = modified("tests/test_parse.py", ["    def test_rejects_bare_number(self):",
                                                "        with self.assertRaises(ValueError):"], [])
        report = da.audit(diff, allow=["**"])
        self.assertIn("test-removed", evidence(report, "tests/test_parse.py"))

    def test_any_changed_expectation_line_needs_a_decision(self):
        diff = modified("tests/test_money.py", ["EXPECTED = '$12.50'"], ["EXPECTED = '12.50'"])
        report = da.audit(diff, allow=["**"])
        self.assertIn("existing-test-changed", flags(report, "tests/test_money.py"))

    def test_adding_tests_to_an_existing_test_file_is_fine(self):
        diff = modified("tests/test_money.py", [], ["    def test_eur(self):",
                                                    "        self.assertEqual(format_total(12.5, 'EUR'), '12.50 €')"])
        report = da.audit(diff, allow=["**"])
        self.assertEqual(flags(report, "tests/test_money.py"), {"tests-added"})
        self.assertEqual(report["exit_code"], 0)

    def test_a_new_test_file_is_fine(self):
        report = da.audit(new_file("tests/test_currency.py", ["import unittest", "assert True"]), allow=["**"])
        self.assertEqual(flags(report, "tests/test_currency.py"), {"tests-added"})

    def test_a_moved_assertion_is_not_a_removed_one(self):
        line = "        self.assertEqual(total, 5)"
        diff = modified("tests/test_cart.py", [line], ["        # moved below", line])
        report = da.audit(diff, allow=["**"])
        self.assertNotIn("assertion-removed", evidence(report, "tests/test_cart.py"))

    def test_deleting_or_renaming_a_test_file_needs_a_decision(self):
        deleted = da.audit(deleted_file("tests/test_old.py", ["def test_a():", "    assert f() == 1"]), allow=["**"])
        self.assertIn("existing-test-changed", flags(deleted, "tests/test_old.py"))
        self.assertIn("file-deleted", evidence(deleted, "tests/test_old.py"))
        renamed = ("diff --git a/tests/test_a.py b/tests/disabled_a.py\nsimilarity index 100%\n"
                   "rename from tests/test_a.py\nrename to tests/disabled_a.py\n")
        report = da.audit(renamed, allow=["**"])
        self.assertIn("existing-test-changed", flags(report, "tests/disabled_a.py"))
        self.assertIn("renamed from tests/test_a.py", evidence(report, "tests/disabled_a.py"))

    def test_narrowing_test_selection_in_configuration_is_reported(self):
        diff = modified("pytest.ini", ["addopts = -q"], ["addopts = -q --deselect tests/test_tax.py::test_rounding"])
        report = da.audit(diff, allow=["**"])
        self.assertIn("test-selection-changed", flags(report, "pytest.ini"))


class DeferredExecution(unittest.TestCase):
    def test_ci_hooks_and_build_files_are_deferred_execution(self):
        for path in (".github/workflows/ci.yml", ".git/hooks/pre-commit", ".husky/pre-push", "Makefile",
                     "tests/conftest.py", "setup.py", ".claude/settings.json", "docker/Dockerfile"):
            with self.subTest(path=path):
                report = da.audit(modified(path, ["a"], ["b"]), allow=["**"])
                self.assertIn("deferred-execution", flags(report, path))
                self.assertEqual(report["exit_code"], 1)

    def test_explicitly_scoped_deferred_execution_is_reported_but_not_blocking(self):
        report = da.audit(modified(".github/workflows/ci.yml", ["a"], ["b"]), allow=["**"],
                          deferred_ok=[".github/workflows/ci.yml"])
        self.assertEqual(flags(report, ".github/workflows/ci.yml"), {"deferred-execution-in-scope"})
        self.assertEqual(report["exit_code"], 0)

    def test_package_json_scripts_count_but_a_version_bump_does_not(self):
        scripts = modified("package.json", ['    "test": "jest"'], ['    "test": "jest --passWithNoTests"'],
                           context=('  "scripts": {',))
        self.assertIn("deferred-execution", flags(da.audit(scripts, allow=["**"]), "package.json"))
        bump = modified("package.json", ['    "left-pad": "1.0.0"'], ['    "left-pad": "1.0.1"'],
                        context=('  "dependencies": {',))
        self.assertNotIn("deferred-execution", flags(da.audit(bump, allow=["**"]), "package.json"))


class ProtectedFloor(unittest.TestCase):
    """GS-20: files that become code or steer the agent need their own answer even inside --allow. The floor is
    deferred-execution: a broad grant (--allow **) does not reach it, only --deferred-ok does."""
    STEERING = ("AGENTS.md", "CLAUDE.md", "docs/CLAUDE.md", "CLAUDE.local.md", "GEMINI.md", ".cursorrules",
                ".cursor/rules/style.mdc", ".windsurfrules", ".clinerules", ".github/copilot-instructions.md",
                ".github/instructions/py.instructions.md")
    MCP = (".mcp.json", "pkg/.mcp.json", ".cursor/mcp.json", ".vscode/mcp.json", ".gemini/settings.json")
    IGNORE = (".claudeignore", ".cursorignore", ".aiderignore", ".codeiumignore", ".geminiignore", "sub/.claudeignore")
    FLOOR = (".agents/skills/x/SKILL.md", "pkg/.agents/config.toml", ".git/config", ".git/info/exclude",
             "vendor/lib/.git/config", ".gitconfig", ".aws/credentials", "home/.aws/config")
    ORDINARY = ("src/agents.py", "docs/agents.md", "docs/CLAUDE-notes.md", "README.md", ".gitignore",
                "src/gitconfig_loader.py", "docs/aws_setup.md", "src/awsome.py", "agents/notes.md", "mcp.json.md",
                "src/claudeignore.py", ".github/ISSUE_TEMPLATE/bug.md")

    def test_each_protected_path_is_deferred_execution_under_a_broad_grant(self):
        for path in self.STEERING + self.MCP + self.IGNORE + self.FLOOR:
            with self.subTest(path=path):
                report = da.audit(modified(path, ["a"], ["b"]), allow=["**"])
                self.assertIn("deferred-execution", flags(report, path))
                self.assertEqual(report["exit_code"], 1)

    def test_paths_with_similar_names_are_not_swept_in(self):
        for path in self.ORDINARY:
            with self.subTest(path=path):
                report = da.audit(modified(path, ["a"], ["b"]), allow=["**"])
                self.assertNotIn("deferred-execution", flags(report, path))
                self.assertEqual(report["exit_code"], 0)

    def test_a_new_steering_file_is_caught_without_a_diff_hunk(self):
        report = da.audit("", status="?? AGENTS.md\n?? .mcp.json\n?? notes.md\n", allow=["**"])
        self.assertIn("deferred-execution", flags(report, "AGENTS.md"))
        self.assertIn("deferred-execution", flags(report, ".mcp.json"))
        self.assertNotIn("deferred-execution", flags(report, "notes.md"))
        self.assertEqual(report["needs_decision"], [".mcp.json", "AGENTS.md"])

    def test_only_a_named_deferred_ok_path_releases_the_floor(self):
        diff = modified("AGENTS.md", ["a"], ["b"]) + modified(".aws/config", ["a"], ["b"])
        report = da.audit(diff, allow=["**"], deferred_ok=["AGENTS.md"])
        self.assertEqual(flags(report, "AGENTS.md"), {"deferred-execution-in-scope"})
        self.assertIn("deferred-execution", flags(report, ".aws/config"))
        self.assertEqual(report["exit_code"], 1)

    def test_the_documented_flag_names_the_floor(self):
        doc = " ".join(da.__doc__.split())
        for words in ("agent steering files", ".git", ".aws"):
            self.assertIn(words, doc)


class ScratchAndUntracked(unittest.TestCase):
    def test_untracked_scratch_files_are_reported(self):
        status = "?? repro_bug.py\n?? debug_output.txt\n?? src/money_helpers.py\n"
        report = da.audit(modified("src/money.py", ["a"], ["b"]), status=status, allow=["src/**", "tests/**"])
        self.assertIn("scratch-candidate", flags(report, "repro_bug.py"))
        self.assertIn("out-of-scope", flags(report, "repro_bug.py"))
        self.assertIn("scratch-candidate", flags(report, "debug_output.txt"))
        self.assertEqual(flags(report, "src/money_helpers.py"), set())
        self.assertEqual(next(f for f in report["files"] if f["path"] == "repro_bug.py")["change"], "untracked")

    def test_untracked_files_alone_are_a_change(self):
        report = da.audit("", status="?? notes.md\n", allow=["**"])
        self.assertEqual(report["verdict"], "clean")

    def test_paths_dirty_before_the_work_started_are_flagged_not_judged(self):
        report = da.audit(modified("src/a.py", ["x"], ["y"]), allow=["src/**"], start_status=" M src/a.py\n?? old.txt\n",
                          status="?? old.txt\n")
        self.assertIn("preexisting-dirty", flags(report, "src/a.py"))
        self.assertNotIn("old.txt", [f["path"] for f in report["files"]])
        self.assertEqual(report["preexisting"], ["old.txt", "src/a.py"])


class CheckConfigChanged(unittest.TestCase):
    """SS-12: a linter, formatter or type-check configuration, or an ignore file, is a gate. Editing one is the
    cheapest way to silence a failing check, so it needs a decision unless the edit states a reason. A first-time
    creation is fine."""

    FLAG = "check-config-changed"

    def silencing_diff(self):
        return (modified(".eslintignore", [], ["src/legacy/"], context=("dist/",))
                + modified("ruff.toml", ['ignore = ["E501"]'], ['ignore = ["E501", "F401"]'], context=("[lint]",)))

    def run_cli(self, script, diff):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "d.txt"
            path.write_text(diff, encoding="utf-8")
            done = subprocess.run([sys.executable, "-B", str(script), str(path), "--allow", "**"],
                                  capture_output=True, text=True, timeout=60)
        return done.returncode, json.loads(done.stdout)

    def check_cli(self, script):
        code, report = self.run_cli(script, self.silencing_diff())
        self.assertEqual(code, 1, report)
        self.assertEqual(report["counts"].get(self.FLAG), 2, report["counts"])
        self.assertIn(".eslintignore", report["needs_decision"])
        self.assertIn("ruff.toml", report["needs_decision"])

    def test_added_ignore_entries_and_loosened_lint_rules_exit_1(self):
        self.check_cli(SCRIPT)

    def test_a_copy_without_the_check_exits_0_on_the_same_diff(self):
        source = SCRIPT.read_text(encoding="utf-8")
        old = "found = _check_config(entry)"
        self.assertEqual(source.count(old), 1)
        with tempfile.TemporaryDirectory() as tmp:
            broken = pathlib.Path(tmp) / "diffaudit_without_check_config.py"
            broken.write_text(source.replace(old, "found = []"), encoding="utf-8")
            code, report = self.run_cli(broken, self.silencing_diff())
            self.assertEqual((code, report["verdict"]), (0, "clean"))
            with self.assertRaises(AssertionError):
                self.check_cli(broken)

    def test_the_whole_family_of_check_configs_is_covered(self):
        for path in (".eslintrc.json", "eslint.config.js", ".prettierrc", "prettier.config.cjs", ".stylelintrc.yml",
                     ".flake8", ".pylintrc", "mypy.ini", "pyrightconfig.json", ".golangci.yml", ".rubocop.yml",
                     "rustfmt.toml", ".clang-format", "biome.json", "web/app/.eslintrc.cjs", ".editorconfig"):
            with self.subTest(path=path):
                self.assertIn(self.FLAG, flags(da.audit(modified(path, ["a: 1"], ["a: 2"]), allow=["**"]), path))

    def test_a_first_time_creation_is_fine(self):
        for diff, path in ((new_file(".eslintrc.json", ['{"extends": "standard"}']), ".eslintrc.json"),
                           (new_file(".prettierignore", ["dist/"]), ".prettierignore")):
            with self.subTest(path=path):
                report = da.audit(diff, allow=["**"])
                self.assertNotIn(self.FLAG, flags(report, path))
        report = da.audit("", status="?? ruff.toml\n", allow=["**"])
        self.assertNotIn(self.FLAG, flags(report, "ruff.toml"))

    def test_an_edit_that_states_its_reason_is_not_flagged(self):
        commented = modified(".eslintignore", [], ["# generated by protoc, never hand-edited", "src/gen/"], context=("dist/",))
        self.assertNotIn(self.FLAG, flags(da.audit(commented, allow=["**"]), ".eslintignore"))
        inline = modified("ruff.toml", [], ['ignore = ["E501"]  # long URLs in the changelog'], context=("[lint]",))
        self.assertNotIn(self.FLAG, flags(da.audit(inline, allow=["**"]), "ruff.toml"))
        js = modified("eslint.config.js", [], ["  // legacy bundle is generated, not linted", "  ignores: ['legacy/**'],"])
        self.assertNotIn(self.FLAG, flags(da.audit(js, allow=["**"]), "eslint.config.js"))
        bare = modified("ruff.toml", [], ['ignore = ["E501"]'], context=("[lint]",))
        self.assertIn(self.FLAG, flags(da.audit(bare, allow=["**"]), "ruff.toml"))

    def test_removing_an_ignore_entry_tightens_the_gate_but_removing_a_rule_loosens_it(self):
        tightened = modified(".eslintignore", ["src/legacy/"], [], context=("dist/",))
        self.assertNotIn(self.FLAG, flags(da.audit(tightened, allow=["**"]), ".eslintignore"))
        loosened = modified(".eslintrc.json", ['  "no-unused-vars": "error",'], [], context=('  "rules": {',))
        self.assertIn(self.FLAG, flags(da.audit(loosened, allow=["**"]), ".eslintrc.json"))
        gone = da.audit(deleted_file(".eslintrc.json", ["{}"]), allow=["**"])
        self.assertIn(self.FLAG, flags(gone, ".eslintrc.json"))
        no_ignore = da.audit(deleted_file(".eslintignore", ["dist/"]), allow=["**"])
        self.assertNotIn(self.FLAG, flags(no_ignore, ".eslintignore"), "deleting an ignore file exempts nothing")

    def test_shared_files_count_only_when_the_change_touches_a_check_setting(self):
        ruff = modified("pyproject.toml", ['ignore = ["E501"]'], ['ignore = ["E501", "F401"]'], context=("[tool.ruff.lint]",))
        self.assertIn(self.FLAG, flags(da.audit(ruff, allow=["**"]), "pyproject.toml"))
        mypy = modified("setup.cfg", ["ignore_missing_imports = False"], ["ignore_missing_imports = True"], context=("[mypy]",))
        self.assertIn(self.FLAG, flags(da.audit(mypy, allow=["**"]), "setup.cfg"))
        version = modified("pyproject.toml", ['version = "1.0.0"'], ['version = "1.0.1"'], context=("[project]",))
        self.assertNotIn(self.FLAG, flags(da.audit(version, allow=["**"]), "pyproject.toml"))
        package = modified("package.json", ['  "eslintConfig": {"extends": "strict"}'], ['  "eslintConfig": {"extends": "off"}'])
        self.assertIn(self.FLAG, flags(da.audit(package, allow=["**"]), "package.json"))
        deps = modified("package.json", ['    "left-pad": "1.0.0"'], ['    "left-pad": "1.0.1"'], context=('  "dependencies": {',))
        self.assertNotIn(self.FLAG, flags(da.audit(deps, allow=["**"]), "package.json"))
        strict = modified("tsconfig.json", ['    "strict": true,'], ['    "strict": false,'], context=('  "compilerOptions": {',))
        self.assertIn(self.FLAG, flags(da.audit(strict, allow=["**"]), "tsconfig.json"))
        paths = modified("tsconfig.json", ['    "@/*": ["src/*"]'], ['    "@/*": ["app/*"]'], context=('    "paths": {',))
        self.assertNotIn(self.FLAG, flags(da.audit(paths, allow=["**"]), "tsconfig.json"))

    def test_the_flag_needs_a_decision_and_names_the_changed_lines(self):
        report = da.audit(modified(".flake8", ["max-line-length = 79"], ["max-line-length = 200"]), allow=["**"])
        self.assertEqual((report["verdict"], report["exit_code"]), ("needs-decision", 1))
        self.assertIn("max-line-length = 200", evidence(report, ".flake8"))


class FormatOnlyHunks(unittest.TestCase):
    """NR-25: a hunk inside an allowed file that only reformats (whitespace, quote style, import order) traces to no
    request. Both sides are normalised; a hunk that then changes nothing needs a decision."""

    FLAG = "format-only-hunk"

    def quote_swap(self):
        return modified("src/money.py", ["    return '$' + s"], ['    return "$" + s'])

    def run_cli(self, script, diff):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "d.txt"
            path.write_text(diff, encoding="utf-8")
            done = subprocess.run([sys.executable, "-B", str(script), str(path), "--allow", "src/**"],
                                  capture_output=True, text=True, timeout=60)
        return done.returncode, json.loads(done.stdout)

    def test_a_quote_style_swap_in_an_allowed_file_exits_1(self):
        code, report = self.run_cli(SCRIPT, self.quote_swap())
        self.assertEqual((code, report["verdict"]), (1, "needs-decision"), report)
        self.assertIn(self.FLAG, flags(report, "src/money.py"))
        self.assertIn("format-only: hunk 1", evidence(report, "src/money.py"))
        self.assertNotIn("out-of-scope", flags(report, "src/money.py"))

    def test_spacing_reindenting_and_rewrapping_are_format_only(self):
        for name, removed, added in (
                ("spacing", ["total=price*qty"], ["total = price * qty"]),
                ("commas", ["call(a,b,  c)"], ["call(a, b, c)"]),
                ("indent", ["  if x:", "    return y"], ["    if x:", "        return y"]),
                ("wrap", ["value = compute(alpha, beta, gamma)"], ["value = compute(", "    alpha, beta, gamma", ")"]),
                ("blank", ["x = 1", "", "", "y = 2"], ["x = 1", "", "y = 2"])):
            with self.subTest(case=name):
                report = da.audit(modified("src/a.py", removed, added), allow=["src/**"])
                self.assertIn(self.FLAG, flags(report, "src/a.py"))
                self.assertEqual(report["exit_code"], 1)

    def test_reordered_imports_are_format_only(self):
        report = da.audit(modified("src/a.py", ["import sys", "import json", "from os import path"],
                                   ["import json", "from os import path", "import sys"]), allow=["src/**"])
        self.assertIn(self.FLAG, flags(report, "src/a.py"))

    def test_a_hunk_that_also_changes_meaning_is_not_format_only(self):
        for name, removed, added in (
                ("value", ["    return '$' + s"], ['    return "EUR " + s']),
                ("words", ["return value"], ["returnvalue"]),
                ("string", ['msg = "a b"'], ['msg = "a c"']),
                ("added", [], ["def eur(s):", "    return s"]),
                ("order", ["a = 1", "b = 2"], ["b = 2", "a = 1"]),
                ("into-block", ["if x:", "    a()", "b()"], ["if x:", "    a()", "    b()"])):
            with self.subTest(case=name):
                report = da.audit(modified("src/a.py", removed, added), allow=["src/**"])
                self.assertNotIn(self.FLAG, flags(report, "src/a.py"))

    def test_only_the_reformatting_hunk_is_named(self):
        diff = modified("src/a.py", ["x = 1"], ["x = 2"]).rstrip("\n").split("\n")
        diff += ["@@ -20,1 +20,1 @@", "-y=3", "+y = 3"]
        report = da.audit("\n".join(diff) + "\n", allow=["src/**"])
        self.assertIn("format-only: hunk 2", evidence(report, "src/a.py"))
        self.assertNotIn("hunk 1", evidence(report, "src/a.py"))

    def test_a_new_file_is_not_judged_for_formatting(self):
        report = da.audit(new_file("src/b.py", ["x = 1", ""]), allow=["src/**"])
        self.assertNotIn(self.FLAG, flags(report, "src/b.py"))

    def test_a_copy_without_the_check_exits_0_on_the_quote_swap(self):
        source = SCRIPT.read_text(encoding="utf-8")
        old = "found = _format_only(entry)"
        self.assertEqual(source.count(old), 1)
        with tempfile.TemporaryDirectory() as tmp:
            broken = pathlib.Path(tmp) / "diffaudit_without_format_only.py"
            broken.write_text(source.replace(old, "found = []"), encoding="utf-8")
            code, report = self.run_cli(broken, self.quote_swap())
            self.assertEqual((code, report["verdict"]), (0, "clean"))

    def test_a_copy_that_ignores_indentation_depth_calls_a_moved_line_format_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        old = "return len(old[2]) != len(new[2]) or old[2] == new[2]"
        self.assertEqual(source.count(old), 1)
        moved = modified("src/a.py", ["if x:", "    a()", "b()"], ["if x:", "    a()", "    b()"])
        with tempfile.TemporaryDirectory() as tmp:
            broken = pathlib.Path(tmp) / "diffaudit_without_depth.py"
            broken.write_text(source.replace(old, "return True"), encoding="utf-8")
            self.assertEqual(self.run_cli(SCRIPT, moved)[1]["files"][0]["flags"], [])
            self.assertEqual(self.run_cli(broken, moved)[1]["files"][0]["flags"], [self.FLAG])

    def test_the_documented_flag_list_names_it(self):
        self.assertIn(self.FLAG, da.__doc__)
        self.assertIn(self.FLAG, da.DECIDE)


class Parsing(unittest.TestCase):
    def test_globs(self):
        self.assertTrue(da.matches("src/a/b.py", ["src/**"]))
        self.assertTrue(da.matches("src/x.py", ["src/**"]))
        self.assertFalse(da.matches("srcx/y.py", ["src/**"]))
        self.assertTrue(da.matches("tests/test_a.py", ["**/test_*.py"]))
        self.assertTrue(da.matches("pkg/tests/data/x.json", ["**/tests/**"]))
        self.assertFalse(da.matches("src/a.py", ["*.py"]))

    def test_utf16_and_crlf_input_decodes(self):
        raw = modified("src/a.py", ["x"], ["y"]).replace("\n", "\r\n").encode("utf-16")
        self.assertEqual(da.decode(raw), modified("src/a.py", ["x"], ["y"]))

    def test_quoted_paths_and_binary_files(self):
        diff = ('diff --git "a/src/caf\\303\\251.py" "b/src/caf\\303\\251.py"\nindex 1..2 100644\n'
                'Binary files "a/src/caf\\303\\251.py" and "b/src/caf\\303\\251.py" differ\n')
        report = da.audit(diff, allow=["src/**"])
        self.assertEqual([f["path"] for f in report["files"]], ["src/café.py"])

    def test_cli_reads_files_prints_json_and_runs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            diff = pathlib.Path(tmp) / "d.txt"
            diff.write_text(modified("tests/test_x.py", ["    assert f() == 2"], ["    assert f() >= 1"]), encoding="utf-8")
            status = pathlib.Path(tmp) / "s.txt"
            status.write_text("?? scratch.py\n", encoding="utf-8")
            done = subprocess.run([sys.executable, "-B", str(SCRIPT), str(diff), "--status", str(status),
                                   "--allow", "src/**", "--allow", "tests/**"], capture_output=True, text=True, timeout=60)
            report = json.loads(done.stdout)
            self.assertEqual(done.returncode, 1)
            self.assertEqual(report["format"], "westack-build-diffaudit-1")
            self.assertIn("ran nothing", report["claim"])
            missing = subprocess.run([sys.executable, "-B", str(SCRIPT), str(pathlib.Path(tmp) / "nope.txt")],
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(missing.returncode, 64)


if __name__ == "__main__":
    unittest.main()
