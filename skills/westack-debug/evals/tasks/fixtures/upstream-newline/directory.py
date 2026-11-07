# directory.py - the staff directory, one "name,email" per line (upn-dir-5e3)
import pathlib

_PATH = pathlib.Path(__file__).with_name("staff.txt")


def load(path=_PATH):
    """Map each name to an email address."""
    people = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            name, email = line.split(",", 1)
            people[name.strip()] = email
    return people
