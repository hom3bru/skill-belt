# tdd-fixture: settings loader
import pathlib
import tomllib

DEFAULT = pathlib.Path(__file__).resolve().parents[1] / "config" / "settings.toml"


def load(path=DEFAULT):
    with open(path, "rb") as stream:
        data = tomllib.load(stream)
    http = data["http"]
    if not isinstance(http.get("timeout_seconds"), (int, float)) or http["timeout_seconds"] <= 0:
        raise ValueError("http.timeout_seconds must be a positive number")
    if not isinstance(http.get("retries"), int) or http["retries"] < 0:
        raise ValueError("http.retries must be a non-negative integer")
    return data
