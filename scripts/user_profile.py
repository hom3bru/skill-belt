"""Local-only publication deny list. Diagnostics deliberately omit scanned values."""
import json
from pathlib import Path
import re


PROFILE_NAME = "skill-belt-profile.json"
PATH_KEYS = ("research_root", "palette_home", "plans_dir", "cp_home", "projects_root")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate profile key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Nonstandard JSON constant")


def _load_profile(path):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        # A dangling symlink is an existing, unusable configuration.
        if path.is_symlink():
            raise ValueError("Local publication profile cannot be read") from None
        return None
    except (OSError, UnicodeError):
        raise ValueError("Local publication profile cannot be read") from None
    try:
        profile = json.loads(text, object_pairs_hook=_unique_object,
                             parse_constant=_invalid_constant)
        if not isinstance(profile, dict):
            raise ValueError
        for key in ("user_name", "user_handle") + PATH_KEYS:
            if key in profile and not isinstance(profile[key], str):
                raise ValueError
    except (ValueError, RecursionError):
        raise ValueError("Local publication profile is malformed") from None
    return profile


def _normalized(text):
    # JSON strings can escape Unicode and either path separator. Normalizing
    # separator runs also handles the doubled backslashes in serialized paths.
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match[1], 16)), text)
    return re.sub(r"[/\\]+", "/", text)


def _patterns(profile):
    patterns = []
    for key in ("user_name", "user_handle"):
        value = profile.get(key, "").strip()
        if value:
            patterns.append(re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)", re.I))
    paths = [profile.get(key, "").strip() for key in PATH_KEYS]
    name = profile.get("user_name", "").strip()
    if name:
        paths.extend(("C:" + "/Users/" + name, "/Users/" + name))
    for value in paths:
        if value:
            value = _normalized(value).rstrip("/") or "/"
            patterns.append(re.compile(r"(?<!\w)" + re.escape(value) + r"(?![\w.-])", re.I))
    return patterns


def check_files(files, profile_path=None):
    """Check a relative-name -> Path mapping, raising redacted ValueError on failure.

    Missing configuration returns configured=False so callers can retain generic
    CI checks. Existing malformed/unreadable profiles fail closed. Empty optional
    fields are ignored, and notes are never used as deny-list entries. All files
    must be UTF-8, matching the publication verifier's text-tree contract.
    """
    profile_path = (Path.home() / ".claude" / PROFILE_NAME
                    if profile_path is None else Path(profile_path).expanduser())
    profile = _load_profile(profile_path)
    patterns = _patterns(profile) if profile is not None else []
    checked = 0
    for relative, path in files.items():
        relative = _normalized(str(relative))
        if relative.rsplit("/", 1)[-1].casefold() == PROFILE_NAME:
            raise ValueError("Private profile filename in publication")
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ValueError("Publication file cannot be read as UTF-8") from None
        subjects = (relative, text, _normalized(text))
        if any(pattern.search(subject) for pattern in patterns for subject in subjects):
            raise ValueError("Local profile deny-list match in publication")
        checked += 1
    return dict(configured=profile is not None, files_checked=checked,
                patterns_checked=len(patterns))
