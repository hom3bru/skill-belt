#!/usr/bin/env python3
"""westack-ship's aging-PR helper. Standard library only; reads saved git output, runs no command, writes nothing.

  python modernize.py rangediff <range-diff.txt>   the pairs in a saved `git range-diff` output
  python modernize.py check     <modernize.json>   check a modernize record (westack-ship-modernize-1)

A record carries the disposition (modernize, rework or close) and its evidence. Modernize needs the replay on a new
branch, no merge commits in the range, a range-diff whose changed and dropped patches are each explained, and the tests
run after; rework and close push nothing; close is a recommendation, never done here; a push needs a grant naming the
branch and a lease pinned to the head that was read, never --force. Exit codes: 0 ok; 1 invalid; 64 usage.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

FORMAT = "westack-ship-modernize-1"
DISPOSITIONS = ("modernize", "rework", "close")
PAIR = re.compile(r"^\s*(\d+|-+):\s+([0-9a-f]{4,40}|-+)\s+([=!<>])\s+(\d+|-+):\s+([0-9a-f]{4,40}|-+)\s?(.*)$")
STATUS = {"=": "same", "!": "changed", "<": "dropped", ">": "added"}


def parse_rangediff(text: str) -> list:
    """Each pair line of `git range-diff` output: old and new positions and commits, the status, the subject."""
    pairs = []
    for line in text.splitlines():
        m = PAIR.match(line)
        if m:
            old_n, old_c, mark, new_n, new_c, subject = m.groups()
            pairs.append({"old": None if old_n.startswith("-") else int(old_n),
                          "old_commit": None if old_c.startswith("-") else old_c,
                          "status": STATUS[mark],
                          "new": None if new_n.startswith("-") else int(new_n),
                          "new_commit": None if new_c.startswith("-") else new_c, "subject": subject.strip()})
    return pairs


def _text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def check(rec: dict) -> list:
    if not isinstance(rec, dict) or rec.get("format") != FORMAT:
        return [f"format must be {FORMAT}"]
    errors = []
    for key in ("branch", "base", "old_head", "merge_base"):
        if not _text(rec.get(key)):
            errors.append(f"{key} is required (read before anything moved)")
    disposition = rec.get("disposition")
    if disposition not in DISPOSITIONS:
        return errors + [f"disposition is one of {', '.join(DISPOSITIONS)}"]
    if not _text(rec.get("reason")):
        errors.append("reason: why this disposition, in the PR's own terms")
    push = rec.get("push")
    if rec.get("closed") is True and not _text(rec.get("close_grant")):
        errors.append("closing a PR is the owner's decision: close is a recommendation unless close_grant quotes the yes")
    if disposition == "modernize":
        if not isinstance(rec.get("merges_in_range"), int):
            errors.append("merges_in_range: count the merge commits in merge_base..old_head before replaying")
        elif rec["merges_in_range"] > 0:
            errors.append("the range holds merge commits: a plain replay drops what they changed and range-diff never "
                          "shows it; rework instead")
        if not _text(rec.get("new_branch")) or rec.get("new_branch") == rec.get("branch"):
            errors.append("new_branch: replay onto a new branch, so the original stays as it was")
        pairs = (rec.get("range_diff") or {}).get("pairs") if isinstance(rec.get("range_diff"), dict) else None
        if not isinstance(pairs, list) or not pairs or not re.fullmatch(r"[0-9a-f]{64}",
                                                                        str(rec["range_diff"].get("sha256", ""))):
            errors.append("range_diff: the saved range-diff's sha256 and its parsed pairs prove what moved")
        else:
            explained = rec.get("explained") if isinstance(rec.get("explained"), dict) else {}
            for p in pairs:
                if p.get("status") in ("changed", "dropped"):
                    key = str(p.get("old"))
                    if not _text(explained.get(key)):
                        errors.append(f"old patch {key} ({p.get('subject', '')}) is {p['status']}: explain it "
                                      "(a conflict resolution, a renamed symbol, already upstream)")
        tests = rec.get("tests_after")
        if not (isinstance(tests, dict) and _text(tests.get("command")) and isinstance(tests.get("exit"), int)):
            errors.append("tests_after: the command and exit code of the tests run on the replayed branch")
        elif tests["exit"] != 0 and push:
            errors.append("the replayed branch fails its tests: no push")
    else:
        if push:
            errors.append(f"{disposition} pushes nothing")
        if disposition == "close" and not _text(rec.get("superseded_by")) and not _text(rec.get("decided_against")):
            errors.append("close names what superseded it (a commit or PR) or where the direction was decided against")
        if disposition == "rework" and not _text(rec.get("next_change")):
            errors.append("rework says what the new change would be")
    if push:
        p = push if isinstance(push, dict) else {}
        grant = p.get("grant") if isinstance(p.get("grant"), dict) else {}
        if not _text(grant.get("by")) or not _text(grant.get("said")) or grant.get("branch") != p.get("branch"):
            errors.append("push: a grant with who and their words, naming the branch pushed")
        command = str(p.get("command", ""))
        lease = f"--force-with-lease={p.get('branch')}:{rec.get('old_head')}"
        if re.search(r"(?<![\w-])(--force|-f)(?![\w-])", command) or lease not in command:
            errors.append(f"push: force-push only with {lease} (the head read before replaying), never --force")
    return errors


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        if len(argv) == 2 and argv[0] == "rangediff":
            print(json.dumps(parse_rangediff(Path(argv[1]).read_text(encoding="utf-8")), indent=2))
            return 0
        if len(argv) == 2 and argv[0] == "check":
            errors = check(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
            print(json.dumps({"status": "valid" if not errors else "invalid", "errors": errors}, indent=2))
            return 0 if not errors else 1
        raise ValueError("usage: modernize.py rangediff <range-diff.txt> | check <modernize.json>")
    except (OSError, ValueError) as exc:
        print(f"modernize.py: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    sys.exit(main())
