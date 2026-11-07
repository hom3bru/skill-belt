# export.py - the directory as CSV for the payroll import (upn-exp-3c9)
import csv
import io

import directory


def to_csv(people=None):
    people = directory.load() if people is None else people
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["name", "email"])
    for name in sorted(people):
        writer.writerow([name, people[name]])
    return out.getvalue()
