"""Procedure entries (procedural memory, westack-procedure-1): scripts/procedure.py and its command line.

A valid entry passes; entries missing their checks or their expiry are refused, and so are an expired one (with
--today), an unknown trust mark, a single step, a non-host memory type and a secret. The example in
references/procedure.md must itself pass. Broken copies with a rule removed let the bad entry through.
"""
import datetime
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "procedure.py"


def load(path=SCRIPT, name="westack_procedure_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


proc = load()

ENTRY = """---
name: quarantine-a-flaky-suite
description: Procedure: quarantining a flaky test without hiding it
metadata:
  type: project
  procedure: westack-procedure-1
---

## When it applies
A test that fails one run in ten on CI and passes locally.

## Steps
1. Reproduce with the seed and a loop of fifty runs.
2. Mark it with the project's flaky marker and open the tracking issue.
3. Run the suite twice more.

## Checks that proved it
- `python -m pytest tests/test_sync.py -p no:randomly --count 50`: exit 1 on run 7 (the flake reproduced)
- `python -m pytest`: exit 0 twice after the marker

## Revision
4f2a9c1 on main

## Expiry
2027-03-01, or sooner when tests/test_sync.py changes

## Trust
user-confirmed: saved on the user's "remember this"
"""


def without_section(text, name):
    return re.sub(r"## %s\n.*?(?=\n## |\Z)" % re.escape(name), "", text, flags=re.S)


def broken(old, new, name):
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        return load(path, name)


class ProcedureTests(unittest.TestCase):
    def test_a_valid_entry_passes(self):
        self.assertEqual(proc.check_procedure(ENTRY, datetime.date(2026, 11, 4)), [])

    def test_missing_checks_or_expiry_is_refused(self):
        self.assertIn("the '## Checks that proved it' section is missing or empty",
                      proc.check_procedure(without_section(ENTRY, "Checks that proved it")))
        self.assertIn("the '## Expiry' section is missing or empty", proc.check_procedure(without_section(ENTRY, "Expiry")))
        unproven = ENTRY.replace(": exit 1 on run 7 (the flake reproduced)", "").replace(": exit 0 twice after the marker", "")
        self.assertIn("Checks that proved it names each check with its result (an exit code or a receipt)",
                      proc.check_procedure(unproven))
        undated = ENTRY.replace("2027-03-01, or sooner", "when it feels stale, or sooner")
        self.assertIn("Expiry gives a date (YYYY-MM-DD), and may add the change that ends it sooner",
                      proc.check_procedure(undated))

    def test_an_expired_entry_needs_revalidating(self):
        errors = proc.check_procedure(ENTRY, datetime.date(2027, 3, 2))
        self.assertEqual(errors, ["expired on 2027-03-01: revalidate (re-run its checks at today's revision) before "
                                  "relying on it"])

    def test_shape_trust_type_and_secrets(self):
        self.assertIn("Trust starts with one mark: user-confirmed, curated, tool-observed, agent-written, unknown",
                      proc.check_procedure(ENTRY.replace("user-confirmed:", "very sure:")))
        one_step = ENTRY.replace("2. Mark it", "Mark it").replace("3. Run", "Run")
        self.assertIn("Steps lists at least two numbered steps", proc.check_procedure(one_step))
        self.assertIn("metadata.type is one of the host's memory types: project, reference, feedback, user",
                      proc.check_procedure(ENTRY.replace("type: project", "type: procedure")))
        leaked = ENTRY.replace("on main", "on main (token ghp_" + "a" * 36 + ")")
        self.assertIn("the entry holds what looks like a secret: never save one", proc.check_procedure(leaked))
        self.assertTrue(proc.check_procedure("no front matter here")[0].startswith("front matter"))

    def test_the_documented_example_passes(self):
        page = (ROOT / "references" / "procedure.md").read_text(encoding="utf-8")
        example = page.split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"
        self.assertEqual(proc.check_procedure(example, datetime.date(2026, 11, 4)), [])

    def test_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = Path(tmp, "good.md"), Path(tmp, "bad.md")
            good.write_text(ENTRY, encoding="utf-8")
            bad.write_text(without_section(ENTRY, "Expiry"), encoding="utf-8")
            script = str(SCRIPT)
            ok = subprocess.run([sys.executable, "-B", script, str(good), "--today", "2026-11-04"],
                                capture_output=True, text=True)
            self.assertEqual((ok.returncode, json.loads(ok.stdout)["status"]), (0, "passed"))
            no = subprocess.run([sys.executable, "-B", script, str(bad)], capture_output=True, text=True)
            self.assertEqual((no.returncode, json.loads(no.stdout)["status"]), (1, "failed"))
            self.assertEqual(subprocess.run([sys.executable, "-B", script], capture_output=True).returncode, 64)

    def test_the_control_without_the_section_rule_takes_an_unproven_entry(self):
        b = broken("        if not sections.get(name):\n", "        if False:\n", "procedure_no_sections")
        self.assertEqual(b.check_procedure(without_section(ENTRY, "Checks that proved it")), [],
                         "the broken copy saves a procedure nothing proved")

    def test_the_control_without_the_expiry_date_rule(self):
        b = broken("    elif date and today is not None:\n", "    elif False:\n", "procedure_never_expires")
        self.assertEqual(b.check_procedure(ENTRY, datetime.date(2027, 3, 2)), [], "the broken copy trusts it forever")


if __name__ == "__main__":
    unittest.main()
