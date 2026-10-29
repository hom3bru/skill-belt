"""r16 candidate, third pass: one source builds both editions. Private files are declared, public files are
leak-free under the publication patterns, machine roots live only in local-roots.json, and a copy without
the private files still passes the package check and core routing."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from test_aa import fixture

ROOT = Path(__file__).resolve().parents[1]
# Copied (not imported) from skill-belt scripts/verify.py BLOCKED, read 2026-10-28: Windows user paths (also
# JSON-escaped), private library and session IDs, the private repository, and token/key shapes.
BLOCKED = [re.compile(pattern) for pattern in (
    r"[A-Za-z]:[/\\]{1,2}Users[/\\]", r"libfile_[0-9a-f]{20,}",
    r"01a[0-9a-f]{5}-[0-9a-f-]{27,}", r"github\.com/hom3bru/Maginot",
    r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{50,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----")]
PRIVATE_TERMS = re.compile(r"(?i:\b(?:rss-radar|radar|eddie|maginot)\b)|\bMatt\b|CANDO|egressFetch|intel\.sqlite|gbatch_|antigravity|\bCL:|\bCX:|gstack")
PUBLIC_PROFILES = ("generic", "coding-workflow", "self", "frankenmine", "westack")


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


package = module("r16c_package", ROOT / "scripts" / "package.py")


def shipped(root):
    """Every file the public edition ships from `root`: all package files minus the declared private ones."""
    result, private = {}, package.private_files(root)
    for path in sorted(Path(root).rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"} and rel not in private:
            result[rel] = path
    return result


class EditionDeclarationTests(unittest.TestCase):
    def test_private_files_are_declared_optional(self):
        private = {"references/profiles/radar.md", "references/profiles/maginot.md", "references/profiles/eddie.md",
                   "references/profiles/radar-path-rules.json", "references/profiles/aliases.json",
                   "references/profiles/local-roots.json", "references/historical-findings.md", "tests/test_private_profiles.py"}
        declared = package.private_files(ROOT)  # by rule, so the public edition (files absent) still passes
        self.assertTrue({rel for rel in private if (ROOT / rel).exists()} <= declared)
        self.assertFalse(declared & package.REQUIRED)
        self.assertFalse(declared & package.PUBLIC_PROFILE_FILES)
        for name in PUBLIC_PROFILES:
            self.assertIn(f"references/profiles/{name}.md", package.REQUIRED)

    def test_public_files_carry_no_blocked_pattern(self):
        offenders = {}
        for rel, path in shipped(ROOT).items():
            hits = [p.pattern for p in BLOCKED if p.search(path.read_text(encoding="utf-8", errors="replace"))]
            if hits:
                offenders[rel] = hits
        # A file the public build must replace with an overlay is declared, with its reason. In the canonical
        # source each declared overlay must still be needed; in the public edition the overlays are already
        # applied, so nothing may match at all.
        if (ROOT / "references/profiles/local-roots.json").exists():
            self.assertEqual(set(offenders), set(package.PUBLIC_OVERLAYS), offenders)
        else:
            self.assertEqual(offenders, {})

    def test_public_markdown_links_stay_inside_the_public_edition(self):
        files = shipped(ROOT)
        for rel, path in files.items():
            if path.suffix != ".md":
                continue
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", target) or target.startswith("#"):
                    continue
                linked = (path.parent / target.split("#", 1)[0]).resolve().relative_to(ROOT.resolve()).as_posix()
                self.assertIn(linked, files, f"{rel} links to {target}, which the public edition does not ship")


class RootHintTests(unittest.TestCase):
    def test_public_profiles_are_generic_and_document_root_fallback(self):
        for name in PUBLIC_PROFILES:
            text = (ROOT / "references" / "profiles" / f"{name}.md").read_text(encoding="utf-8")
            lines = [line for line in text.splitlines() if not line.startswith("Owner (")]
            found = [m.group(0) for line in lines for m in [PRIVATE_TERMS.search(line)] if m]
            self.assertEqual(found, [], name)
        for name in ("self", "frankenmine", "westack"):
            text = (ROOT / "references" / "profiles" / f"{name}.md").read_text(encoding="utf-8")
            self.assertIn("local-roots.json", text, name)
            self.assertIn("ask", text, name)
        self.assertIn("skills/frankenmine", (ROOT / "references/profiles/frankenmine.md").read_text(encoding="utf-8"))
        self.assertIn("skills/westack", (ROOT / "references/profiles/westack.md").read_text(encoding="utf-8"))

    # test_local_roots_file_shape moved to test_private_profiles.py.


class PublicCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.copy = self.root / "adopt-adapt"
        shutil.copytree(ROOT, self.copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for rel in package.private_files(ROOT):
            target = self.copy / rel
            if target.exists():
                target.unlink()

    def tearDown(self):
        self.temp.cleanup()

    def test_copy_without_private_files_passes_package_check_and_core_routing(self):
        copy_package = module("r16c_copy_package", self.copy / "scripts" / "package.py")
        (self.copy / "release.json").write_text(json.dumps(copy_package.manifest(self.copy)), encoding="utf-8")
        copy_package.verify(self.copy)
        aa = module("r16c_copy_aa", self.copy / "scripts" / "aa.py")
        profiles = aa.known_profiles()
        self.assertTrue({"generic", "coding-workflow", "self", "frankenmine", "westack", "tooling"} <= profiles)
        self.assertFalse({"radar", "rss-radar", "eddie", "maginot"} & profiles)
        work = self.root / "work"; work.mkdir()
        run, record = fixture(work)
        self.assertEqual(aa.validate(record, run), [])
        for profile in ("coding-workflow", "frankenmine"):
            record["recipients"][0]["profile"] = profile
            record["routing"] = [{"profile": profile, "confidence": "high", "evidence": ["user named it"], "explicit": True}]
            record["items"][0]["decision"]["score"]["rubric"] = aa.rubric_for(profile)  # fourth pass: the profile's own rubric
            self.assertEqual(aa.validate(record, run), [], profile)
        record["recipients"][0]["profile"] = "radar"
        self.assertIn("unknown recipient profile", " ".join(aa.validate(record, run)))


if __name__ == "__main__":
    unittest.main()
