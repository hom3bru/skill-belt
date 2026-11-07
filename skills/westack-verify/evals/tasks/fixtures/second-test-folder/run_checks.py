# checks-stf-8c2
"""The project's checks: python run_checks.py. Unit tests in tests/, then the published-URL contract in contract/."""
import sys
import unittest

ok = True
for folder in ("tests", "contract"):
    print("==", folder)
    suite = unittest.defaultTestLoader.discover(folder)
    ok = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() and ok
sys.exit(0 if ok else 1)
