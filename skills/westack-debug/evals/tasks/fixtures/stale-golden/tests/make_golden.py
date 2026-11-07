# tests/make_golden.py - rewrites tests/golden/invoice.txt from the current code (gld-mk-9f3)
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import invoice  # noqa: E402
from test_invoice import GOLDEN, SAMPLE  # noqa: E402

GOLDEN.write_text("# golden invoice, generated %s by tests/make_golden.py\n" % datetime.date.today()
                  + invoice.render(SAMPLE), encoding="utf-8")
print("wrote", GOLDEN)
