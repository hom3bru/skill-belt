"""The validator split: record.py (task-record contract), evidence.py (receipts, controls,
fingerprint, snapshot) and skillmeta.py (front matter and package checks), with validate.py a thin
CLI that keeps every earlier name. Also the package rules for westack front matter."""
import ast
import importlib.util
import pathlib
import shutil
import sys
import tempfile
import unittest

import test_westack as fixtures

ROOT = fixtures.ROOT
SCRIPTS = ROOT / "scripts"
v = fixtures.v

# Every top-level name of validate.py before the split (westack (then called estack) 0.3.0 at 8e35821).
EARLIER = """BASE CONTRACT RUNTIME NON_EXECUTION LIMIT REPARSE_POINT LINK_TAGS FINGERPRINT_HEADER ALWAYS_SKIP
DEFAULT_EXCLUDE MANIFEST_FORMAT VERSION_NAME GIT_OBJECT GIT_REF FRONT_MATTER_KEYS FRONT_MATTER_NESTED
ADJUDICATION_NEXT REQUIREMENT_NEXT DECISION_NEXT digest read_json read_small_text write_new shape safe_path
scope_path portable within is_link check_excludes fingerprint_hash fingerprint definition plain_folder
store_manifest load_manifest diff_entries git_location git_revision resolve_revision observe snapshot timestamp
freshness approval_matches reconcile supports same_content check_receipt check_previous check_supersession short
check_task version_parts next_version check_chain package_files front_matter plain_scalar check_package start_task
task_context resolve_into_root load_version add_receipt refresh main""".split()

HOME = {
    "evidence": """RUNTIME NON_EXECUTION LIMIT FINGERPRINT_HEADER DEFAULT_EXCLUDE MANIFEST_FORMAT digest read_json
        write_new safe_path portable within is_link fingerprint store_manifest load_manifest diff_entries
        git_revision resolve_revision observe snapshot timestamp supports same_content check_receipt
        control_errors""".split(),
    "record": """CONTRACT ADJUDICATION_NEXT shape definition freshness reconcile check_previous check_task
        check_chain start_task task_context add_receipt refresh""".split(),
    "skillmeta": "FRONT_MATTER_KEYS front_matter plain_scalar package_files check_package skill_metadata".split(),
}
FORBIDDEN_MODULES = {"subprocess", "socket", "urllib", "http", "ftplib", "smtplib", "ctypes", "multiprocessing"}


def load_alone(name):
    """Load one helper module by path, as a sub-skill or tool would."""
    spec = importlib.util.spec_from_file_location("split_probe_" + name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SplitLayoutTests(unittest.TestCase):
    def test_modules_exist_and_load_alone(self):
        for name in HOME:
            with self.subTest(module=name):
                self.assertTrue((SCRIPTS / (name + ".py")).is_file())
                module = load_alone(name)
                for attr in HOME[name]:
                    self.assertTrue(hasattr(module, attr), name + " lacks " + attr)

    def test_validate_keeps_every_earlier_name(self):
        missing = [name for name in EARLIER if not hasattr(v, name)]
        self.assertEqual(missing, [])

    def test_validate_reexports_the_home_objects(self):
        for name, attrs in HOME.items():
            module = sys.modules[next(k for k in sys.modules if k.startswith("westack_" + name + "_"))]
            for attr in attrs:
                with self.subTest(attr=attr):
                    self.assertIs(getattr(v, attr), getattr(module, attr))

    def test_validate_is_a_thin_cli(self):
        tree = ast.parse((SCRIPTS / "validate.py").read_text(encoding="utf-8"))
        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.assertEqual(sorted(functions), ["_sibling", "main"])
        self.assertLess(len((SCRIPTS / "validate.py").read_text(encoding="utf-8").splitlines()), 200)


class HelperHygieneTests(unittest.TestCase):
    """Standard library only; no subprocess, network or eval; writes by exclusive create. The build tool
    (build_core_block.py) rewrites sub-skill files through a temporary file, so only the first rule binds it."""
    FILES = ("validate.py", "record.py", "evidence.py", "skillmeta.py", "checks.py", "registry.py", "core_check.py",
             "ruletest.py", "procedure.py")
    ALL = FILES + ("build_core_block.py",)

    def tree(self, name):
        return ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))

    def test_every_script_is_covered(self):
        self.assertEqual(sorted(p.name for p in SCRIPTS.glob("*.py")), sorted(self.ALL))

    def test_no_process_network_or_eval(self):
        for name in self.ALL:
            for node in ast.walk(self.tree(name)):
                with self.subTest(file=name, line=getattr(node, "lineno", 0)):
                    if isinstance(node, ast.Import):
                        self.assertFalse({a.name.split(".")[0] for a in node.names} & FORBIDDEN_MODULES)
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotIn((node.module or "").split(".")[0], FORBIDDEN_MODULES)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, {"eval", "exec", "compile", "__import__"})
                    if isinstance(node, ast.Attribute):
                        self.assertNotIn(node.attr, {"system", "popen", "startfile", "spawnl", "execv"})

    def test_writes_use_exclusive_create(self):
        for name in self.FILES:
            for node in ast.walk(self.tree(name)):
                if not isinstance(node, ast.Call) or not isinstance(node.func, (ast.Attribute, ast.Name)):
                    continue
                called = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                owner = (node.func.value.id if isinstance(node.func, ast.Attribute)
                         and isinstance(node.func.value, ast.Name) else None)
                with self.subTest(file=name, line=node.lineno):
                    self.assertNotIn(called, {"write_text", "write_bytes"})
                    self.assertNotIn(owner, {"shutil"})
                    if owner == "os":
                        self.assertNotIn(called, {"replace", "rename", "remove", "unlink", "rmdir", "removedirs"})
                    if called == "open":
                        modes = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                        modes += [k.value.value for k in node.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
                        for mode in modes:
                            self.assertFalse(set(mode) & set("wa+"), "non-exclusive write mode " + mode)


class WestackFrontMatterTests(unittest.TestCase):
    """Package rules: name westack or westack-<slug>; metadata.stack westack and a version;
    a sub-skill also names the core range it needs."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-split-fm-")
        self.base = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def package(self, folder, *lines, body="# Body\n"):
        target = self.base / folder
        target.mkdir()
        (target / "SKILL.md").write_text("---\n" + "\n".join(lines) + "\n---\n" + body, encoding="utf-8", newline="\n")
        return v.check_package(target)

    def test_core_needs_stack_and_version(self):
        self.assertEqual(self.package("westack", "name: westack", "description: Router.", "metadata:",
                                      "  stack: westack", "  version: 1.0.0-alpha.0"), [])
        errors = self.package("westack2", "name: westack", "description: Router.")
        self.assertTrue(any("metadata.stack" in e for e in errors), errors)

    def test_foreign_stack_is_rejected(self):
        errors = self.package("westack-review", "name: westack-review", "description: Review.", "metadata:",
                              "  stack: otherstack", "  version: 1.0.0", '  requires_core: ">=1.0.0-alpha.0 <2"')
        self.assertTrue(any("metadata.stack must be westack" in e for e in errors), errors)

    def test_sub_skill_needs_a_core_range(self):
        ok = self.package("westack-review", "name: westack-review", "description: Review.", "metadata:",
                          "  stack: westack", "  version: 0.1.0", '  requires_core: ">=1.0.0-alpha.0 <2"')
        self.assertEqual(ok, [])
        errors = self.package("westack-debug", "name: westack-debug", "description: Debug.", "metadata:",
                              "  stack: westack", "  version: 0.1.0")
        self.assertTrue(any("requires_core" in e for e in errors), errors)

    def test_other_names_are_rejected(self):
        errors = self.package("otherskill", "name: otherskill", "description: Old.", "metadata:", "  stack: westack",
                              "  version: 0.3.0")
        self.assertTrue(any("name must be westack" in e for e in errors), errors)

    def test_metadata_values_are_parsed(self):
        keys, nested, errors = load_alone("skillmeta").skill_metadata(
            "---\nname: westack-x\ndescription: \"A: b\"\nmetadata:\n  stack: westack\n"
            "  requires_core: \">=1.0.0-alpha.0 <2\"\n---\nbody\n")
        self.assertEqual(errors, [])
        self.assertEqual(keys["description"], "A: b")
        self.assertEqual(nested, {"stack": "westack", "requires_core": ">=1.0.0-alpha.0 <2"})

    def test_shipped_router_passes(self):
        self.assertEqual(v.check_package(ROOT), [])


if __name__ == "__main__":
    unittest.main()
