#!/usr/bin/env python3
"""westack-office-hours design-document check. Standard library only; reads a document and optional local profile, writes nothing.

  python ohcheck.py doc <design.md>

Checks the shape the session promises, not whether the idea is good: the mode line, the sections that mode needs,
numbered premises each marked agreed or disagreed, at least two approaches each with effort, risk, pros and cons,
a recommendation that names one of them, the user's own choice recorded, open questions, one next action, and none
of the hedging phrases the session rules out.
Exit codes: 0 the document has the shape; 1 it does not; 64 usage or unreadable input.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

SECTIONS = {
    "demand": ["Problem", "Demand evidence", "Status quo", "Who and the narrowest wedge", "Constraints", "Premises",
               "Approaches", "Recommendation", "Choice", "Open questions", "Success criteria", "Next action"],
    "builder": ["Problem", "What makes it worth building", "Constraints", "Premises", "Approaches", "Recommendation",
                "Choice", "Open questions", "Success criteria", "Next action"],
}
HEDGES = ["that's an interesting approach", "there are many ways to think about this", "you might want to consider",
          "that could work", "i can see why you'd think that"]
APPROACH_FIELDS = ("Effort", "Risk", "Pros", "Cons")


def sections(text: str) -> dict:
    out, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def owner_names() -> list:
    profile_path = Path.home() / ".claude" / "skill-belt-profile.json"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        profile = {}
    if not isinstance(profile, dict):
        raise ValueError("invalid profile")
    name = profile.get("user_name", "the user")
    aliases = profile.get("legacy_user_names", [])
    if (not isinstance(name, str) or not isinstance(aliases, list)
            or any(not isinstance(alias, str) for alias in aliases)):
        raise ValueError("invalid owner names")
    return ["the user", "they"] + [value.strip() for value in [name] + aliases if value.strip()]


def check_doc(text: str) -> list:
    problems = []
    mode_m = re.search(r"^Mode:\s*(demand|builder)\s*$", text, re.M | re.I)
    if not mode_m:
        return ["the document needs a 'Mode: demand' or 'Mode: builder' line"]
    mode = mode_m.group(1).lower()
    secs = sections(text)
    for name in SECTIONS[mode]:
        if not secs.get(name):
            problems.append(f"section '## {name}' is missing or empty")
    premises = re.findall(r"^\s*\d+\.\s+(.+)$", secs.get("Premises", ""), re.M)
    if not premises:
        problems.append("Premises lists no numbered statements")
    for p in premises:
        if not re.search(r"\((?:agreed|disagreed)\b", p, re.I):
            problems.append(f"premise not marked (agreed) or (disagreed): {p[:60]}")
    approaches = re.split(r"^###\s+", secs.get("Approaches", ""), flags=re.M)[1:]
    names = []
    for block in approaches:
        name = block.splitlines()[0].strip()
        names.append(name)
        for field in APPROACH_FIELDS:
            if not re.search(rf"^\s*-?\s*{field}:\s*\S", block, re.M):
                problems.append(f"approach '{name}' has no {field}")
    if len(approaches) < 2:
        problems.append("at least two approaches are needed (one of them the smallest that ships)")
    rec = secs.get("Recommendation", "")
    if names and not any(n.lower() in rec.lower() for n in names):
        problems.append("the recommendation names none of the approaches")
    choice = secs.get("Choice", "")
    if names and not any(n.lower() in choice.lower() for n in names):
        problems.append("the user's choice names none of the approaches")
    try:
        owners = "|".join(re.escape(name) for name in owner_names())
    except (OSError, ValueError, UnicodeError):
        return ["local user profile is unreadable or invalid"]
    if choice and not re.search(rf"(?<!\w)(?:{owners})(?!\w).*\b(?:chose|picked|said)\b", choice, re.I | re.S):
        problems.append("Choice must record that the user chose, in their words, not the recommendation repeated")
    lowered = text.lower()
    for hedge in HEDGES:
        if hedge in lowered:
            problems.append(f"a hedge the session rules out: '{hedge}'")
    return problems


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] != "doc":
        print("usage: ohcheck.py doc <design.md>", file=sys.stderr)
        return 64
    try:
        text = Path(argv[1]).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ohcheck.py: cannot read {argv[1]}: {exc}", file=sys.stderr)
        return 64
    problems = check_doc(text)
    print(json.dumps({"status": "ok" if not problems else "problems", "problems": problems}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
