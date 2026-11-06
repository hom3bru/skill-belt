"""Procedure entries in the host's memory (westack-procedure-1). Standard library; reads one file, writes nothing.

  python procedure.py <entry.md> [--today YYYY-MM-DD]

A procedure is a finished piece of work saved, on the user's explicit save, as steps someone can follow again: when it
applies, the steps, the checks that proved it, the revision it was proved at, an expiry and a trust mark. It lives in
the host's own memory format (Markdown with front matter), never a second store. Exit codes: 0 passed; 1 failed;
64 usage or unreadable input.
"""
import datetime
import json
import pathlib
import re
import sys

__all__ = ["check_procedure", "PROCEDURE_FORMAT", "main"]

PROCEDURE_FORMAT = "westack-procedure-1"
HOST_TYPES = ("project", "reference", "feedback", "user")
TRUST = ("user-confirmed", "curated", "tool-observed", "agent-written", "unknown")
SECTIONS = ("When it applies", "Steps", "Checks that proved it", "Revision", "Expiry", "Trust")
SECRET = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bxox[abprs]-[A-Za-z0-9-]{10,}\b|"
                    r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----|\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")


def _front_matter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, text
    data, parent = {}, None
    for line in lines[1:end]:
        if not line.strip():
            continue
        m = re.match(r"^(\s*)([\w-]+):\s*(.*)$", line)
        if not m:
            continue
        indent, key, value = len(m.group(1)), m.group(2), m.group(3).strip().strip("\"'")
        if indent == 0:
            data[key] = value if value else {}
            parent = key if not value else None
        elif parent and isinstance(data.get(parent), dict):
            data[parent][key] = value
    return data, "\n".join(lines[end + 1:])


def _sections(body):
    found, current = {}, None
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1)
            found[current] = []
        elif current:
            found[current].append(line)
    return {k: "\n".join(v).strip() for k, v in found.items()}


def check_procedure(text, today=None):
    """Problems with one procedure entry; an empty list means it is well formed (and, with today, not expired)."""
    meta, body = _front_matter(text)
    if meta is None:
        return ["front matter (--- ... ---) with name, description and metadata is required: the host's memory format"]
    errors = []
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(meta.get("name", ""))):
        errors.append("name is a short kebab-case slug")
    if not str(meta.get("description", "")).strip():
        errors.append("description says in one line when the procedure applies")
    md = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
    if md.get("type") not in HOST_TYPES:
        errors.append("metadata.type is one of the host's memory types: " + ", ".join(HOST_TYPES))
    if md.get("procedure") != PROCEDURE_FORMAT:
        errors.append("metadata.procedure is " + PROCEDURE_FORMAT)
    sections = _sections(body)
    for name in SECTIONS:
        if not sections.get(name):
            errors.append("the '## %s' section is missing or empty" % name)
    steps = [l for l in sections.get("Steps", "").splitlines() if re.match(r"^\s*\d+[.)]\s+\S", l)]
    if sections.get("Steps") and len(steps) < 2:
        errors.append("Steps lists at least two numbered steps")
    checks = sections.get("Checks that proved it", "")
    if checks and not re.search(r"(?i)\bexit\s+-?\d+|\breceipt\b|\bpassed\b", checks):
        errors.append("Checks that proved it names each check with its result (an exit code or a receipt)")
    if sections.get("Revision") and not re.search(r"\b[0-9a-f]{7,40}\b|\bv?\d+\.\d+", sections["Revision"]):
        errors.append("Revision names the commit or version the checks ran at")
    expiry = sections.get("Expiry", "")
    date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", expiry)
    if expiry and not date:
        errors.append("Expiry gives a date (YYYY-MM-DD), and may add the change that ends it sooner")
    elif date and today is not None:
        try:
            if datetime.date.fromisoformat(date.group(1)) < today:
                errors.append("expired on %s: revalidate (re-run its checks at today's revision) before relying on it"
                              % date.group(1))
        except ValueError:
            errors.append("Expiry's date is not a real date")
    trust = sections.get("Trust", "").split()[:1]
    if sections.get("Trust") and (not trust or trust[0].strip(".,;:") not in TRUST):
        errors.append("Trust starts with one mark: " + ", ".join(TRUST))
    if SECRET.search(text):
        errors.append("the entry holds what looks like a secret: never save one")
    return errors


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        today = None
        if len(argv) == 3 and argv[1] == "--today":
            today = datetime.date.fromisoformat(argv[2])
        elif len(argv) != 1:
            raise ValueError("usage: procedure.py <entry.md> [--today YYYY-MM-DD]")
        errors = check_procedure(pathlib.Path(argv[0]).read_bytes().decode("utf-8"), today)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        sys.stderr.write("procedure.py: %s\n" % exc)
        return 64
    print(json.dumps({"status": "failed" if errors else "passed", "errors": errors,
                      "claim": "the entry's shape, checks, revision, expiry and trust mark; not that its steps still "
                               "work: re-run its checks before relying on it"}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
