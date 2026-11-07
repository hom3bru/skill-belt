# settings.py - shop settings, read once and cached (olk-set-4c1)
import json
import pathlib

_PATH = pathlib.Path(__file__).with_name("settings.json")
_cache = None


def load():
    """Return the shop settings: read from settings.json on first use, then cached."""
    global _cache
    if _cache is None:
        _cache = json.loads(_PATH.read_text(encoding="utf-8"))
    return _cache
