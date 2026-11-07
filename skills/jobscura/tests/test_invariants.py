"""Static guardrails, not proof of arbitrary Python's runtime behavior."""
import ast
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NETWORK_IMPORTS = {"socket", "ssl", "urllib.request", "http.client", "ftplib", "smtplib",
                   "imaplib", "webbrowser", "requests", "httpx", "asyncio", "xmlrpc.client",
                   "http.server", "poplib", "telnetlib", "multiprocessing.connection", "urllib3", "aiohttp"}


def network_imports(path):
    findings = []
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    importlib_names = {"importlib"}
    importer_names = {"__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            importlib_names.update(alias.asname or alias.name for alias in node.names if alias.name == "importlib")
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            importer_names.update(alias.asname or alias.name for alias in node.names if alias.name == "import_module")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [module] + [module + "." + alias.name for alias in node.names]
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            function = node.func
            importer = (isinstance(function, ast.Name) and function.id in importer_names
                        or isinstance(function, ast.Attribute) and function.attr == "import_module"
                        and isinstance(function.value, ast.Name) and function.value.id in importlib_names)
            names = [node.args[0].value] if importer and isinstance(node.args[0].value, str) else []
        else:
            continue
        for name in names:
            if any(name == forbidden or name.startswith(forbidden + ".") for forbidden in NETWORK_IMPORTS):
                findings.append((node.lineno, name))
    return findings


class OfflineInvariants(unittest.TestCase):
    def test_helpers_do_not_import_network_clients(self):
        helpers = sorted((ROOT / "scripts").glob("*.py")) + sorted((ROOT / "skills").glob("*/scripts/*.py"))
        self.assertTrue(helpers)
        for path in helpers:
            with self.subTest(helper=str(path.relative_to(ROOT))):
                self.assertEqual(network_imports(path), [])

    def test_no_network_and_submission_boundaries_remain_explicit(self):
        sentences = {
            "references/helpers.md": "They make no network calls.",
            "skills/application-packet/SKILL.md": "No network, credentials, model API, paid service, upload, browser interaction,",
            "skills/application-tracking/SKILL.md": "Never submit an application or contact an employer from this skill.",
        }
        for name, sentence in sentences.items():
            with self.subTest(document=name):
                self.assertIn(sentence, (ROOT / name).read_text(encoding="utf-8"))
        packet = (ROOT / "skills/application-packet/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Not for drafting, browser autofill, uploading or submitting.", packet)

    def test_scanner_detects_injected_import(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "helper.py"
            original = (ROOT / "scripts/grounding.py").read_text(encoding="utf-8")
            copy.write_text(original + "\nimport urllib.request\n", encoding="utf-8")
            self.assertEqual(network_imports(copy)[-1][1], "urllib.request")
            for statement in ("from urllib import request", "from http.client import HTTPConnection",
                              "import requests.sessions", "import ssl as tls"):
                copy.write_text(statement, encoding="utf-8")
                self.assertTrue(network_imports(copy), statement)


if __name__ == "__main__":
    unittest.main()
