import json
from pathlib import Path


def load_config(path):
    path = Path(path)
    if path.suffix != ".json":
        raise ValueError("unsupported config format: %s" % path.suffix)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
