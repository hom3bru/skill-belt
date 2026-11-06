import os
import pathlib
import tomllib

PATH = pathlib.Path.home() / ".config" / "notes" / "config.toml"
DEFAULTS = {"store": str(pathlib.Path.home() / ".local" / "share" / "notes"), "editor": os.environ.get("EDITOR", "vi")}


def load():
    values = dict(DEFAULTS)
    if PATH.is_file():
        values.update(tomllib.loads(PATH.read_text(encoding="utf-8")))
    return values
