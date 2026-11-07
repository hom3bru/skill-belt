# check-scg-9d3
"""The project's check: python check.py"""
import io
import sys
import unittest

result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(unittest.defaultTestLoader.discover("tests"))
failed = len(result.failures) + len(result.errors)
print("%d tests, %d failed" % (result.testsRun, failed))
print("CHECKS FAILED" if failed else "All checks passed.")
sys.exit(1 if failed else 0)
