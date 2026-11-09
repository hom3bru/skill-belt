"""Regression controls for the static offline-import guard."""
from pathlib import Path
import tempfile
import unittest

from test_invariants import network_imports


class ReviewInvariantTests(unittest.TestCase):
    def test_additional_network_imports(self):
        statements = ("import asyncio", "from asyncio import open_connection",
                      "import xmlrpc.client", "import http.server", "import poplib",
                      "import telnetlib", "import multiprocessing.connection",
                      "import urllib3", "import aiohttp")
        self.check_statements(statements)

    def test_literal_dynamic_network_imports(self):
        self.check_statements(("__import__('socket')", "importlib.import_module('aiohttp')",
                               "import importlib as loader\nloader.import_module('http.server')",
                               "from importlib import import_module as load\nload('xmlrpc.client')"))

    def check_statements(self, statements):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "helper.py"
            for statement in statements:
                with self.subTest(statement=statement):
                    path.write_text(statement, encoding="utf-8")
                    self.assertTrue(network_imports(path))
