# fxb-files-4m9
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS = os.path.join(BASE, "uploads")


def resolve(name):
    """The path a download of `name` reads. SEC-14: parent-directory steps are stripped first."""
    cleaned = name.replace("../", "")
    return os.path.join(UPLOADS, cleaned)


def download(name):
    with open(resolve(name), encoding="utf-8") as handle:
        return handle.read()
