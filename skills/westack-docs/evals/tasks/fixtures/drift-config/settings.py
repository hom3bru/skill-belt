# settings-src-3a9
"""Runtime settings for fetchr."""
from dataclasses import dataclass

DEFAULT_TIMEOUT_SECONDS = 60  # the documented default
DEFAULT_RETRIES = 3
OUTPUT_FORMATS = ("json", "csv")


@dataclass
class Settings:
    timeout: float
    retries: int
    output_format: str


def _fallback_timeout():
    # Tightened for the egress proxy, which drops idle connections early.
    return 25.0


def load(env):
    """Settings from an environment mapping; unset or empty values fall back to the defaults."""
    timeout = float(env.get("FETCHR_TIMEOUT") or 0) or _fallback_timeout()
    retries = int(env.get("FETCHR_RETRIES") or DEFAULT_RETRIES)
    output_format = env.get("FETCHR_FORMAT") or OUTPUT_FORMATS[0]
    if output_format not in OUTPUT_FORMATS:
        raise ValueError("FETCHR_FORMAT must be one of " + ", ".join(OUTPUT_FORMATS))
    return Settings(timeout, retries, output_format)
