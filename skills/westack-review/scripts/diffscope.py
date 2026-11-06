"""westack-review diff scope: read a unified diff the agent saved, summarise what changed, and check
that every finding sits on a changed line or names the changed line that introduced it.

  python diffscope.py summary DIFF [--base SHA] [--head SHA]
  python diffscope.py check DIFF FINDINGS
  python diffscope.py findings FILE
  python diffscope.py coverage DIFF LEDGER
  python diffscope.py snippets DIFF FINDINGS [--root DIR]
  python diffscope.py resolve LEDGER

DIFF is the saved output of, for example, `git diff --no-color --no-ext-diff --no-textconv <merge-base> HEAD` or
`gh pr diff N`.
Default a/ and b/ prefixes are expected; quoted paths, renames, binary files, CRLF and UTF-16 files are
handled. FINDINGS is JSON: a list (or {"findings": [...]}) of {"id", "file", "line", "side": "new"|"old",
"introduced_at": {"file", "line", "side"}}; "side" defaults to "new".

Verdicts per finding:
  in-diff             the location is an added (new side) or removed (old side) line;
  affected-elsewhere  the location is not changed, but introduced_at is a changed line;
  not-introduced      the location (or introduced_at) is in a changed file but on an unchanged line:
                      park it as pre-existing unless the change is shown to make it reachable;
  not-located         the file is not in the diff, or the finding has no usable file and line.

Exit 0 when every finding is in-diff or affected-elsewhere (summary: parsed), 1 when any finding needs
provenance, 2 when the input cannot be read as a diff or as findings (an empty diff included: check the
base), 64 for usage errors. Standard library only. It reads two files and prints JSON; it runs nothing,
calls no network and never runs git.

`findings` checks a reviewer's output against a small schema (SS-06): a list, or {"verdict", "scope",
"findings": [...]}, of records with a "state" of needs-validation, confirmed, dropped or not-validated.
Each state allows only its own fields; nothing has a severity, fix, rationale, validation or adjudication
before it is confirmed; a confirmed P0 or P1 needs a trigger and the evidence for it. The verdict is
blocking, none-found or not-assessed, never an approval, and none-found is refused while any record is
confirmed, unconfirmed or not validated, or when it names no scope. Exit 0 valid, 1 invalid, 2 unreadable;
the report carries the SHA-256 of the raw bytes so the raw text can be kept. Malformed output fails the
review; a valid file is a shape check only, not an approval.

The RV items (2026-10-30) add to the same schema. A record may carry `snippets` (RV-3: quotes labelled input,
entrypoint, control, sink or outcome, each with its file, line and text), `vendor` and `vendor_severity` (RV-8: the
outside reviewer that raised it and its own label, kept verbatim; a label needs the vendor's name, and a missing label
is unknown, never low) and `identity` (RV-10: a rule family, a root-control anchor that names no line number, and an
instance key for each independently attackable sibling; two open records with one identity are an unmerged
duplicate). A vendor's record is confirmed only with a westack `validation` (RV-17), and the report counts each
vendor's candidates, confirmed and dropped records. A confirmed P0 or P1 makes not-assessed invalid (RV-11): it is
blocking whatever else is missing; a not-assessed verdict may name an `evidence_plan` of one to three actions, each
with what it would settle.

`snippets` compares each quoted snippet with the lines it cites (RV-3): new-side quotes against the diff's added and
context lines, or against the file under --root (a checkout of the reviewed head) when the line is not in the diff;
old-side quotes against the diff's removed and context lines only. Lines are compared one by one with surrounding
whitespace and line endings ignored, so a re-indented quote matches and a paraphrase differs. Verdicts: matches,
differs, not-found (no such file or line, or a path that leaves the root) and not-checkable (outside the diff with no
root, or an old-side line outside the diff). Exit 0 when every snippet matches, 1 when any differs or is not found, 2
when something could not be checked, no snippet was given, or an input is unreadable.

`coverage` checks the agent's per-file ledger against the diff (RT-1): a list (or {"files": [...]}) of
{"file", "state": "reviewed"|"skipped", "reason", "change"}. Every file of the diff, added, deleted, renamed and
binary ones included, needs exactly one entry; a skip needs a concrete reason (an empty or vacuous one such as "n/a"
leaves the file unmarked); an entry for a file not in the diff, a second entry for one file, or a change that
disagrees with the diff's is a problem. The report gives the total, reviewed, skipped and unmarked counts and names
every unmarked file: a file with neither mark is a coverage failure, never clean. Exit 0 complete, 1 incomplete,
2 unreadable. It checks marks only; it does not show that a reviewed file was read well.

`resolve` checks a resolve-mode session's ledger (DS-1, DS-2; no diff is read): a JSON object of `comments`
({"id", "author", "bot", "run", "answers"}: the gathered comments, a bot being flagged or a login ending in [bot], its
run the id of the review run that left it, `answers` the texts already in its thread), `rounds` (the runs already
addressed per reviewer, from an earlier session or from this command's own report) and `replies` ({"id", "in_reply_to",
"text"}). An automated reviewer gets at most `cap` rounds (default 3), a round being one distinct run, never one
comment: the comments of a run past the cap are `bot-round-cap`, a bot comment with no run id is `bot-run-unknown`.
A reply must name the gathered comment it answers (`in_reply_to`); a top-level comment or summary is
`reply-not-in-thread`, and one that says word for word (case and punctuation aside) what the thread or an earlier reply
says is `reply-repeats`. The report carries the runs addressed so far, to hand to the next session. Exit 0 clean, 1
findings, 2 unreadable. It does not show that a comment was judged well or that a reworded repeat is new.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

FORMAT = "westack-review-diffscope-1"
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


class DiffError(ValueError):
    """The input cannot be read as a unified diff or as findings."""


def decode(data):
    """Text from saved diff bytes: UTF-16 with a byte-order mark (Windows PowerShell 5 redirection) or UTF-8."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    return data.decode("utf-8-sig", errors="replace")


def _unquote(token):
    """A git path token: C-quoted ("a/caf\\303\\251") or bare. Octal escapes are UTF-8 bytes."""
    if not (len(token) >= 2 and token[0] == '"' and token[-1] == '"'):
        return token
    out, i, body = bytearray(), 0, token[1:-1]
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in "01234567" and re.fullmatch(r"[0-7]{3}", body[i + 1:i + 4] or ""):
                out.append(int(body[i + 1:i + 4], 8))
                i += 4
                continue
            out.append(ESCAPES.get(nxt, ord(nxt)))
            i += 2
            continue
        out.extend(ch.encode("utf-8"))
        i += 1
    return out.decode("utf-8", errors="replace")


def _path(raw):
    """The repository path from a ---/+++ value: tab-separated timestamp dropped, quotes and prefix removed."""
    value = _unquote(raw.split("\t")[0].strip())
    if value == "/dev/null":
        return None
    return value[2:] if value[:2] in ("a/", "b/") else value


def _git_header_paths(rest):
    """(old, new) from the text after 'diff --git ', for blocks with no ---/+++ lines (renames, binaries)."""
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|\S+', rest)
    if len(tokens) == 2:
        return _path(tokens[0]), _path(tokens[1])
    half = rest.split(" b/")  # unquoted paths with spaces: split on the b/ prefix
    if len(half) == 2:
        return _path(half[0]), _path("b/" + half[1])
    return None, None


def _new_file(old=None, new=None):
    return {"old_path": old, "new_path": new, "status": "modified", "hunks": [], "added": [], "removed": [],
            "context_new": [], "context_old": [], "text_new": {}, "text_old": {}, "_flags": set()}


def _finish(f):
    flags = f.pop("_flags")
    if "binary" in flags:
        f["status"] = "binary"
    elif f["old_path"] is None or "new" in flags:
        f["status"] = "added"
        f["old_path"] = None
    elif f["new_path"] is None or "deleted" in flags:
        f["status"] = "deleted"
        f["new_path"] = None
    elif f["old_path"] != f["new_path"] or "renamed" in flags:
        f["status"] = "renamed"
    return f


def parse(text):
    """The files of a unified diff, each with its hunks and changed line numbers. Raises DiffError."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    files, current, i = [], None, 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            if current:
                files.append(_finish(current))
            current = _new_file(*_git_header_paths(line[len("diff --git "):]))
        elif line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            old, new = _path(line[4:]), _path(lines[i + 1][4:])
            if current is None or current["hunks"]:
                if current:
                    files.append(_finish(current))
                current = _new_file(old, new)
            else:
                current["old_path"], current["new_path"] = old, new
            i += 1
        elif current is not None and line.startswith(("new file mode", "deleted file mode", "rename from ",
                                                        "rename to ", "Binary files ", "GIT binary patch")):
            if line.startswith("new file mode"):
                current["_flags"].add("new")
            elif line.startswith("deleted file mode"):
                current["_flags"].add("deleted")
            elif line.startswith("rename from "):
                current["_flags"].add("renamed")
                current["old_path"] = _unquote(line[len("rename from "):])
            elif line.startswith("rename to "):
                current["_flags"].add("renamed")
                current["new_path"] = _unquote(line[len("rename to "):])
            else:
                current["_flags"].add("binary")
        elif line.startswith("@@"):
            match = HUNK.match(line)
            if not match or current is None:
                raise DiffError("line %d: hunk header outside a file or unreadable: %r" % (i + 1, line[:80]))
            old_start, new_start = int(match[1]), int(match[3])
            old_len = int(match[2]) if match[2] is not None else 1
            new_len = int(match[4]) if match[4] is not None else 1
            current["hunks"].append({"old_start": old_start, "old_len": old_len,
                                     "new_start": new_start, "new_len": new_len})
            old_no, new_no, old_left, new_left = old_start, new_start, old_len, new_len
            while old_left > 0 or new_left > 0:
                i += 1
                if i >= len(lines):
                    raise DiffError("truncated hunk in %s: %d old and %d new lines missing"
                                    % (current["new_path"] or current["old_path"], old_left, new_left))
                body = lines[i]
                kind = body[:1]
                if kind == "\\":  # "\ No newline at end of file"
                    continue
                if kind == "+" and new_left > 0:
                    current["added"].append(new_no)
                    current["text_new"][new_no] = body[1:]
                    new_no, new_left = new_no + 1, new_left - 1
                elif kind == "-" and old_left > 0:
                    current["removed"].append(old_no)
                    current["text_old"][old_no] = body[1:]
                    old_no, old_left = old_no + 1, old_left - 1
                elif kind in (" ", "") and old_left > 0 and new_left > 0:  # editors may strip a blank's space
                    current["context_old"].append(old_no)
                    current["context_new"].append(new_no)
                    current["text_old"][old_no] = current["text_new"][new_no] = body[1:]
                    old_no, new_no, old_left, new_left = old_no + 1, new_no + 1, old_left - 1, new_left - 1
                else:
                    raise DiffError("hunk in %s does not match its header near line %d"
                                    % (current["new_path"] or current["old_path"], i + 1))
            while i + 1 < len(lines) and lines[i + 1].startswith("\\"):
                i += 1
        i += 1
    if current:
        files.append(_finish(current))
    if not files:
        raise DiffError("no file headers found: save the full diff (git diff --no-color --no-ext-diff --no-textconv "
                        "BASE HEAD), not --stat; "
                        "an empty diff usually means the wrong base or uncommitted work left out")
    return files


def _norm(path):
    path = str(path).replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _find(files, path, side):
    path = _norm(path)
    key = "new_path" if side == "new" else "old_path"
    for candidate in (path, path[2:] if path[:2] in ("a/", "b/") else None):
        if candidate is None:
            continue
        for f in files:
            if f[key] == candidate:
                return f
        for f in files:  # a path on the other side still places the file in the diff
            if f["new_path"] == candidate or f["old_path"] == candidate:
                return f
    return None


def locate(files, path, line, side="new"):
    """added, removed, context, unchanged, binary or file-not-in-diff for one file:line on one side."""
    f = _find(files, path, side)
    if f is None:
        return "file-not-in-diff"
    if f["status"] == "binary":
        return "binary"
    if side == "old":
        return "removed" if line in f["removed"] else "context" if line in f["context_old"] else "unchanged"
    return "added" if line in f["added"] else "context" if line in f["context_new"] else "unchanged"


def _site(entry):
    """(file, line, side) from a finding or introduced_at block, or None when unusable."""
    if not isinstance(entry, dict):
        return None
    path, line, side = entry.get("file"), entry.get("line"), entry.get("side", "new")
    if not isinstance(path, str) or not path.strip() or isinstance(line, bool) or not isinstance(line, int) \
            or line < 1 or side not in ("new", "old"):
        return None
    return path, line, side


def check(files, findings):
    """Each finding's verdict and the overall status: located or needs-provenance."""
    if isinstance(findings, dict):
        findings = findings.get("findings")
    if not isinstance(findings, list):
        raise DiffError("findings must be a JSON list or an object with a findings list")
    ids, results = set(), []
    for index, finding in enumerate(findings, 1):
        fid = finding.get("id") if isinstance(finding, dict) else None
        fid = str(fid) if fid not in (None, "") else "#%d" % index
        if fid in ids:
            raise DiffError("duplicate finding id: " + fid)
        ids.add(fid)
        site = _site(finding)
        where = locate(files, *site) if site else "unusable"
        intro = _site(finding.get("introduced_at")) if isinstance(finding, dict) else None
        intro_where = locate(files, *intro) if intro else None
        if where in ("added", "removed"):
            verdict = "in-diff"
        elif intro_where in ("added", "removed"):
            verdict = "affected-elsewhere"
        elif where in ("context", "unchanged", "binary") or intro_where in ("context", "unchanged", "binary"):
            verdict = "not-introduced"
        else:
            verdict = "not-located"
        results.append({"id": fid, "location": where, "introduced_at": intro_where, "verdict": verdict})
    counts = {k: sum(r["verdict"] == k for r in results)
              for k in ("in-diff", "affected-elsewhere", "not-introduced", "not-located")}
    status = "located" if counts["not-introduced"] + counts["not-located"] == 0 else "needs-provenance"
    return {"format": FORMAT, "mode": "check", "status": status, "counts": counts, "findings": results}


STATES = ("needs-validation", "confirmed", "dropped", "not-validated")
VERDICTS = ("blocking", "none-found", "not-assessed")
SEVERITIES = ("P0", "P1", "P2", "P3")
INTRODUCED = ("patch", "affected-elsewhere", "pre-existing", "unknown")
UNCONFIRMED_FORBIDDEN = ("severity", "fix", "rationale", "validation", "adjudication")
TRIGGER_REQUIRED = ("P0", "P1")
NO_ALL_CLEAR_WITH = ("needs-validation", "not-validated", "confirmed")
ONLY_IN_STATES = {"stage": ("dropped",), "reason": ("dropped", "not-validated")}
KNOWN_FIELDS = {"id", "state", "claim", "file", "line", "side", "heading", "introduced", "introduced_at", "trigger",
                "consequence", "evidence", "severity", "fix", "rationale", "validation", "adjudication", "stage",
                "reason", "snippets", "vendor", "vendor_severity", "identity"}
FINDINGS_CLAIM = ("checks the shape of reviewer output only; a valid file is not an approval and does not move "
                  "any test status")
SNIPPET_ROLES = ("input", "entrypoint", "control", "sink", "outcome")  # RV-3
SNIPPET_FIELDS = {"role", "file", "line", "side", "text"}
VENDOR_CONFIRMED_NEEDS = ("confirmed",)  # RV-17: states in which a vendor's record needs a westack validation
LINE_IN_ANCHOR = re.compile(r"(:\d+\b|#L\d+|\bline\s*\d+)", re.I)  # RV-10: an anchor never names a line
IDENTITY_UNIQUE_AMONG = ("needs-validation", "confirmed", "not-validated")  # a drop may repeat an identity it merged
HELD_ONLY_WITHOUT = ("P0", "P1")  # RV-11: a confirmed one of these makes not-assessed invalid
EVIDENCE_PLAN_MAX = 3
EVIDENCE_PLAN_VERDICTS = ("not-assessed",)
VENDOR_STATES = ("confirmed", "dropped", "needs-validation", "not-validated")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _snippet_errors(items):
    """RV-3: (field, problem) pairs for a record's snippets: each has a role, a place and the quoted text."""
    if not isinstance(items, list) or not items:
        return [("snippets", "must be a non-empty list of {role, file, line, text}")]
    errors = []
    for number, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(("snippets", "snippet %d must be an object" % number))
            continue
        unknown = sorted(set(item) - SNIPPET_FIELDS)
        if unknown:
            errors.append(("snippets", "snippet %d: unknown field %s" % (number, ", ".join(unknown))))
        if item.get("role") not in SNIPPET_ROLES:
            errors.append(("snippets", "snippet %d: role must be one of %s" % (number, ", ".join(SNIPPET_ROLES))))
        if _site(item) is None:
            errors.append(("snippets", "snippet %d needs a file, a line of 1 or more and a side of new or old" % number))
        if not _text(item.get("text")):
            errors.append(("snippets", "snippet %d needs the quoted text, as it stands at the cited lines" % number))
    return errors


def _identity_key(rec):
    """RV-10: (family, anchor, instance) for a record with a usable identity, else None."""
    identity = rec.get("identity")
    if not isinstance(identity, dict) or not _text(identity.get("family")) or not _text(identity.get("anchor")):
        return None
    instance = identity.get("instance")
    return identity["family"].strip(), identity["anchor"].strip(), instance.strip() if _text(instance) else ""


def _record_errors(rec, state):
    """(field, problem) pairs for one record of a known state."""
    errors = []
    for field in sorted(rec):
        if field not in KNOWN_FIELDS:
            errors.append((field, "unknown field"))
        elif state != "confirmed" and field in UNCONFIRMED_FORBIDDEN:
            errors.append((field, "not allowed before the finding is confirmed"))
        elif field in ONLY_IN_STATES and state not in ONLY_IN_STATES[field]:
            errors.append((field, "not allowed on a %s record" % state))
    if not _text(rec.get("claim")):
        errors.append(("claim", "required, one sentence"))
    line = rec.get("line")
    if "line" in rec and (isinstance(line, bool) or not isinstance(line, int) or line < 1):
        errors.append(("line", "must be an integer of 1 or more"))
    if "side" in rec and rec["side"] not in ("new", "old"):
        errors.append(("side", "must be new or old"))
    if "introduced" in rec and rec["introduced"] not in INTRODUCED:
        errors.append(("introduced", "must be one of " + ", ".join(INTRODUCED)))
    if "introduced_at" in rec and _site(rec["introduced_at"]) is None:
        errors.append(("introduced_at", "needs a file and a line"))
    placed = (_text(rec.get("file")) and isinstance(line, int) and not isinstance(line, bool) and line >= 1) \
        or _text(rec.get("heading"))
    if state in ("needs-validation", "confirmed") and not placed:
        errors.append(("location", "needs file and line, or a heading"))
    if state == "confirmed":
        severity = rec.get("severity")
        if severity not in SEVERITIES:
            errors.append(("severity", "required, one of " + ", ".join(SEVERITIES)))
        if not _text(rec.get("consequence")):
            errors.append(("consequence", "required: what breaks, for whom"))
        if severity in TRIGGER_REQUIRED:
            for field in ("trigger", "evidence"):
                if not _text(rec.get(field)):
                    errors.append((field, "required for %s: a demonstrated trigger and its evidence" % severity))
    if state == "dropped":
        for field in ("reason", "evidence"):
            if not _text(rec.get(field)):
                errors.append((field, "required: a drop keeps its reason and deciding evidence"))
    if state == "not-validated" and not _text(rec.get("reason")):
        errors.append(("reason", "required: why the validator did not run"))
    for field in ("vendor", "vendor_severity"):  # RV-8: the vendor's own words, or left out (unknown, never low)
        if field in rec and not _text(rec[field]):
            errors.append((field, "the vendor's own text; leave it out when there is none (unknown, never low)"))
    if "vendor_severity" in rec and not _text(rec.get("vendor")):
        errors.append(("vendor_severity", "a vendor's label needs the vendor's name beside it"))
    if state in VENDOR_CONFIRMED_NEEDS and "vendor" in rec and not _text(rec.get("validation")):
        errors.append(("validation", "required for a vendor's finding: a westack validator confirms it, never the "
                                     "vendor's own verdict"))
    if "snippets" in rec:
        errors += _snippet_errors(rec["snippets"])
    if "identity" in rec:
        identity = rec["identity"]
        if _identity_key(rec) is None or set(identity) - {"family", "anchor", "instance"} \
                or ("instance" in identity and not _text(identity["instance"])):
            errors.append(("identity", "needs a rule family and a root-control anchor, plus an instance key as text "
                                       "for each independently attackable sibling"))
        elif LINE_IN_ANCHOR.search(identity["anchor"]):
            errors.append(("identity", "the anchor names the control or symbol, never a line number"))
    return errors


def _plan_errors(plan, verdict):
    """RV-11: a held verdict names one to EVIDENCE_PLAN_MAX actions, each with what it would settle."""
    problems = []
    if verdict not in EVIDENCE_PLAN_VERDICTS:
        problems.append("only a not-assessed verdict names the evidence that would settle it")
    if not isinstance(plan, list):
        return problems + ["a list of one to %d actions" % EVIDENCE_PLAN_MAX]
    if not 1 <= len(plan) <= EVIDENCE_PLAN_MAX:
        problems.append("one to %d actions, not %d" % (EVIDENCE_PLAN_MAX, len(plan)))
    for number, step in enumerate(plan, 1):
        if not isinstance(step, dict) or set(step) - {"action", "settles"} or not _text(step.get("action")) \
                or not _text(step.get("settles")):
            problems.append("action %d needs the action and what its result would settle" % number)
    return problems


def _vendor_counts(records):
    """RV-17: per vendor, its candidates by state and the share dropped at validation."""
    out = {}
    for rec in records:
        if isinstance(rec, dict) and _text(rec.get("vendor")) and rec.get("state") in VENDOR_STATES:
            row = out.setdefault(rec["vendor"].strip(), dict({state: 0 for state in VENDOR_STATES}, candidates=0))
            row["candidates"] += 1
            row[rec["state"]] += 1
    for row in out.values():
        row["dropped_share"] = round(row["dropped"] / row["candidates"], 3)
    return out


def check_findings(data):
    """Check reviewer output against the schema; never raises on content and never approves."""
    errors, counts, seen, records, identities = [], {state: 0 for state in STATES}, set(), [], {}
    verdict = scope = None
    if isinstance(data, dict):
        verdict, scope = data.get("verdict"), data.get("scope")
        for key in sorted(set(data) - {"verdict", "scope", "findings", "evidence_plan"}):
            errors.append({"id": None, "field": key, "problem": "unknown field"})
        records = data.get("findings")
        if not isinstance(records, list):
            errors.append({"id": None, "field": "findings", "problem": "must be a list"})
            records = []
    elif isinstance(data, list):
        records = data
    else:
        errors.append({"id": None, "field": "findings", "problem": "must be a JSON list or an object with a "
                                                                      "findings list"})
    states = []
    for index, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            errors.append({"id": "#%d" % index, "field": "record", "problem": "must be an object"})
            continue
        fid = rec.get("id") if _text(rec.get("id")) else None
        label = fid or "#%d" % index
        if fid is None:
            errors.append({"id": label, "field": "id", "problem": "required"})
        elif fid in seen:
            errors.append({"id": label, "field": "id", "problem": "duplicate id"})
        seen.add(fid)
        state = rec.get("state")
        if state not in STATES:
            errors.append({"id": label, "field": "state", "problem": "must be one of " + ", ".join(STATES)})
            continue
        counts[state] += 1
        states.append((state, rec.get("severity")))
        errors += [{"id": label, "field": f, "problem": p} for f, p in _record_errors(rec, state)]
        key = _identity_key(rec)
        if key and state in IDENTITY_UNIQUE_AMONG:  # RV-10: one identity, one open record
            if key in identities:
                errors.append({"id": label, "field": "identity", "problem": "same identity as %s: merge them, keeping "
                                                                            "every site" % identities[key]})
            else:
                identities[key] = label
    if verdict is not None or (isinstance(data, dict) and "verdict" in data):
        if verdict not in VERDICTS:
            errors.append({"id": None, "field": "verdict", "problem": "must be one of " + ", ".join(VERDICTS)
                           + "; a review never emits an approval"})
        elif verdict == "blocking" and not any(s == "confirmed" and v in TRIGGER_REQUIRED for s, v in states):
            errors.append({"id": None, "field": "verdict", "problem": "blocking needs a confirmed P0 or P1"})
        elif verdict == "none-found":
            if not _text(scope):
                errors.append({"id": None, "field": "scope", "problem": "none-found names the scope assessed"})
            open_states = sorted({s for s, _ in states if s in NO_ALL_CLEAR_WITH})
            if open_states:
                errors.append({"id": None, "field": "verdict", "problem": "none-found is not allowed with %s records"
                               % ", ".join(open_states)})
        elif verdict == "not-assessed" and any(s == "confirmed" and v in HELD_ONLY_WITHOUT for s, v in states):
            errors.append({"id": None, "field": "verdict", "problem": "a confirmed P0 or P1 is blocking whatever "
                                                                      "else is missing"})
    if isinstance(data, dict) and "evidence_plan" in data:
        errors += [{"id": None, "field": "evidence_plan", "problem": p} for p in _plan_errors(data["evidence_plan"], verdict)]
    return {"format": FORMAT, "mode": "findings", "status": "invalid" if errors else "valid", "verdict": verdict,
            "counts": counts, "vendors": _vendor_counts(records), "errors": errors, "claim": FINDINGS_CLAIM}


MARKS = ("reviewed", "skipped")
VACUOUS_REASONS = ("", "n/a", "na", "none", "skip", "skipped", "ignored", "irrelevant", "not relevant", "tbd", "todo", "-")
COVERAGE_CLAIM = ("checks that every file of the saved diff carries one mark and every skip a reason; it does not show "
                  "that a reviewed file was read well, and a complete ledger is not an approval")


def coverage(files, ledger):
    """RT-1: whether every file of the diff carries exactly one mark, reviewed or skipped with a concrete reason."""
    entries = ledger.get("files") if isinstance(ledger, dict) else ledger
    if not isinstance(entries, list):
        raise DiffError("the ledger must be a JSON list or an object with a files list")
    names = [f["new_path"] or f["old_path"] for f in files]
    place = {id(f): number for number, f in enumerate(files)}
    marked, extra, problems = {}, [], []
    for index, entry in enumerate(entries, 1):
        name = entry.get("file") if isinstance(entry, dict) else None
        if not _text(name):
            problems.append({"entry": "#%d" % index, "problem": "needs a file path"})
            continue
        diff_file = _find(files, name, "new")
        if diff_file is None:
            extra.append(_norm(name))
            continue
        position = place[id(diff_file)]
        label = names[position]
        if position in marked:
            problems.append({"entry": label, "problem": "duplicate entry: one mark per file"})
            continue
        state, reason, change = entry.get("state"), entry.get("reason"), entry.get("change")
        if state not in MARKS:
            problems.append({"entry": label, "problem": "state must be reviewed or skipped"})
            continue
        if change and change != diff_file["status"]:
            problems.append({"entry": label, "problem": "change %s does not match the diff's %s"
                             % (change, diff_file["status"])})
        if state == "skipped" and (not _text(reason) or reason.strip().lower().rstrip(".") in VACUOUS_REASONS):
            problems.append({"entry": label, "problem": "a skip needs a concrete reason"})
            continue
        marked[position] = {"file": label, "state": state, "reason": reason.strip() if state == "skipped" else None}
    unmarked = [name for position, name in enumerate(names) if position not in marked]
    skipped = [{"file": m["file"], "reason": m["reason"]} for _, m in sorted(marked.items()) if m["state"] == "skipped"]
    reviewed = sum(m["state"] == "reviewed" for m in marked.values())
    status = "incomplete" if unmarked or problems or extra else "complete"
    return {"format": FORMAT, "mode": "coverage", "status": status,
            "totals": {"files": len(files), "reviewed": reviewed, "skipped": len(skipped), "unmarked": len(unmarked)},
            "unmarked": unmarked, "skipped": skipped, "extra": extra, "problems": problems, "claim": COVERAGE_CLAIM}


SNIPPET_CLAIM = ("compares each quoted snippet with the lines it cites; a match shows the quote is real, not that the "
                 "path it describes is reachable or that the finding is right")


def _same(quoted, cited):
    return quoted.strip() == cited.strip()


def _lines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _snippet_verdict(files, root, item):
    """RV-3: (verdict, reason) for one snippet: matches, differs, not-found or not-checkable."""
    path, line, side = _site(item)
    quoted = _lines(item["text"])
    span = range(line, line + len(quoted))
    diff_file = _find(files, path, side)
    table = diff_file["text_new" if side == "new" else "text_old"] if diff_file else {}
    if diff_file is not None and diff_file["status"] != "binary" and all(n in table for n in span):
        cited = [table[n] for n in span]
    elif side == "old":
        return "not-checkable", "an old-side line outside the diff: only the diff holds the old text"
    elif root is None:
        return "not-checkable", "outside the diff: pass --root with a checkout of the reviewed head"
    else:
        target = (root / _norm(path)).resolve()
        if root != target and root not in target.parents:
            return "not-found", "the path leaves the root"
        try:
            whole = _lines(decode(target.read_bytes()))
        except OSError:
            return "not-found", "no such file under the root"
        if line - 1 + len(quoted) > len(whole):
            return "not-found", "the file has fewer lines than the quote cites"
        cited = whole[line - 1:line - 1 + len(quoted)]
    for offset, (quote, source) in enumerate(zip(quoted, cited)):
        if not _same(quote, source):
            return "differs", "line %d does not match the quote" % (line + offset)
    return "matches", None


def snippets(files, findings, root=None):
    """RV-3: whether each finding's quoted snippets equal the lines they cite. Never raises on content."""
    if isinstance(findings, dict):
        findings = findings.get("findings")
    if not isinstance(findings, list):
        raise DiffError("findings must be a JSON list or an object with a findings list")
    if root is not None:
        root = pathlib.Path(root).resolve()
        if not root.is_dir():
            raise DiffError("--root is not a directory: %s" % root)
    results = []
    for index, finding in enumerate(findings, 1):
        if not isinstance(finding, dict) or "snippets" not in finding:
            continue
        fid = str(finding["id"]) if _text(finding.get("id")) else "#%d" % index
        items = finding["snippets"] if isinstance(finding["snippets"], list) else [None]
        for number, item in enumerate(items, 1):
            if not isinstance(item, dict) or _site(item) is None or not _text(item.get("text")):
                verdict, reason = "not-found", "the snippet has no usable file, line and quoted text"
            else:
                verdict, reason = _snippet_verdict(files, root, item)
            results.append({"id": fid, "snippet": number, "role": item.get("role") if isinstance(item, dict) else None,
                            "verdict": verdict, "reason": reason})
    counts = {k: sum(r["verdict"] == k for r in results) for k in ("matches", "differs", "not-found", "not-checkable")}
    if not results:
        status = "not-run"
    elif counts["differs"] or counts["not-found"]:
        status = "mismatch"
    elif counts["not-checkable"]:
        status = "inconclusive"
    else:
        status = "verified"
    return {"format": FORMAT, "mode": "snippets", "status": status, "counts": counts, "snippets": results,
            "claim": SNIPPET_CLAIM}


ROUND_CAP = 3  # automated review rounds per reviewer (DS-1); three is the default, basis taste
RESOLVE_CLAIM = ("counts each automated reviewer's distinct runs and checks that every reply sits in its comment's "
                 "thread and does not repeat an earlier answer word for word; it does not show that a comment was "
                 "judged well, that a reply is true or that a reworded repeat is new")


def _bot(comment):
    return comment.get("bot") is True or str(comment.get("author") or "").endswith("[bot]")


def _answer_key(value):
    return " ".join(re.findall(r"\w+", str(value or "").casefold()))


def _answers(value):
    """The normalised texts of the answers already in a thread: strings, or objects with a text."""
    return [_answer_key(item.get("text") if isinstance(item, dict) else item) for item in
            (value if isinstance(value, list) else [])]


def _runs(value):
    """The run ids already addressed for one reviewer: a list, or the report's {runs, count}."""
    value = value.get("runs") if isinstance(value, dict) else value
    return [run for run in value if _text(run)] if isinstance(value, list) else []


def resolve(ledger):
    """DS-1 and DS-2: a resolve session's ledger. `comments` are the gathered comments ({id, author, run, bot,
    answers}); `rounds` the runs already addressed per reviewer; `replies` the drafted replies ({id, in_reply_to,
    text}). Never raises on content it can report; raises DiffError on a ledger it cannot read."""
    if not isinstance(ledger, dict):
        raise DiffError("the ledger must be a JSON object with comments and replies")
    cap = ledger.get("cap", ROUND_CAP)
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise DiffError("cap must be a whole number of 1 or more")
    comments, replies, rounds = ledger.get("comments", []), ledger.get("replies", []), ledger.get("rounds", {})
    if not isinstance(comments, list) or not isinstance(replies, list) or not isinstance(rounds, dict):
        raise DiffError("comments and replies are lists; rounds maps a reviewer to the run ids already addressed")
    known = {str(name): _runs(value) for name, value in rounds.items()}
    findings, thread = [], {}

    def flag(code, item, detail):
        findings.append({"code": code, "id": item, "detail": detail})

    for index, item in enumerate(comments, 1):
        if not isinstance(item, dict) or not _text(item.get("id")):
            raise DiffError("comment %d needs an id" % index)
        thread[item["id"]] = _answers(item.get("answers"))
        if not _bot(item):
            continue
        name = item["author"].strip() if _text(item.get("author")) else "(unnamed bot)"
        runs, run = known.setdefault(name, []), item.get("run")
        if not _text(run):
            flag("bot-run-unknown", item["id"], "%s: a bot comment without its run id cannot be counted; read the run id "
                 "from the review record before judging it" % name)
        elif run in runs:
            continue  # one run is one round, however many comments it left
        elif len(runs) >= cap:
            flag("bot-round-cap", item["id"], "%s: run %s would be round %d, over the cap of %d: report it, do not "
                 "address it" % (name, run, len(runs) + 1, cap))
        else:
            runs.append(run)
    for index, item in enumerate(replies, 1):
        if not isinstance(item, dict):
            raise DiffError("reply %d must be an object" % index)
        rid, target = item["id"] if _text(item.get("id")) else "#%d" % index, item.get("in_reply_to")
        if not _text(target) or target not in thread:
            flag("reply-not-in-thread", rid, "a reply answers one gathered comment inside that comment's own thread; a "
                 "top-level comment or a summary table is not a reply")
            continue
        key = _answer_key(item.get("text"))
        if key and key in thread.get(target, []):
            flag("reply-repeats", rid, "the thread of %s already says this: read the thread first and do not repeat an "
                 "answer" % target)
        thread.setdefault(target, []).append(key)
    notes = [] if cap == ROUND_CAP else ["cap is %d, not the default %d: only the user's word raises it" % (cap, ROUND_CAP)]
    return {"format": FORMAT, "mode": "resolve", "status": "findings" if findings else "clean", "cap": cap,
            "rounds": {name: {"runs": runs, "count": len(runs)} for name, runs in sorted(known.items()) if runs},
            "totals": {"comments": len(comments), "replies": len(replies)}, "findings": findings, "notes": notes,
            "claim": RESOLVE_CLAIM}


def _ranges(numbers):
    out = []
    for n in sorted(set(numbers)):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return out


def summarise(files, data, base=None, head=None):
    """What changed, per file, bound to the diff bytes it was read from."""
    entries = [{"old_path": f["old_path"], "new_path": f["new_path"], "status": f["status"],
                "added": len(f["added"]), "removed": len(f["removed"]), "hunks": f["hunks"],
                "added_ranges": _ranges(f["added"]), "removed_ranges": _ranges(f["removed"])} for f in files]
    return {"format": FORMAT, "mode": "summary", "status": "parsed",
            "diff_sha256": hashlib.sha256(data).hexdigest(), "base": base, "head": head,
            "totals": {"files": len(files), "added": sum(len(f["added"]) for f in files),
                       "removed": sum(len(f["removed"]) for f in files)},
            "files": entries,
            "removed_behaviour_sites": [{"file": f["old_path"], "old_lines": _ranges(f["removed"])}
                                        for f in files if f["removed"]],
            "claim": "parsed from the saved diff only; the diff's own correctness and base are the agent's receipt"}


def _findings_main(path):
    """Exit 0 valid, 1 invalid, 2 unreadable; the raw bytes are bound by their SHA-256 so the text can be kept."""
    raw = None
    try:
        with open(path, "rb") as stream:
            raw = stream.read()
        report = check_findings(json.loads(decode(raw)))
    except (OSError, ValueError) as exc:
        report = {"format": FORMAT, "mode": "findings", "status": "unreadable", "error": str(exc),
                  "claim": FINDINGS_CLAIM + "; unreadable output fails the review, keep the raw text"}
    if raw is not None:
        report["raw_sha256"] = hashlib.sha256(raw).hexdigest()
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return {"valid": 0, "invalid": 1}.get(report["status"], 2)


def _resolve_main(path):
    """Exit 0 clean, 1 findings, 2 unreadable."""
    try:
        with open(path, "rb") as stream:
            raw = stream.read()
        report = resolve(json.loads(decode(raw)))
        report["ledger_sha256"] = hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError) as exc:
        report = {"format": FORMAT, "mode": "resolve", "status": "unreadable", "error": str(exc)}
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return {"clean": 0, "findings": 1}.get(report["status"], 2)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("diffscope.py: " + message + "\n")
        sys.exit(64)


def main(argv=None):
    parser = _Parser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("summary")
    s.add_argument("diff")
    s.add_argument("--base")
    s.add_argument("--head")
    c = sub.add_parser("check")
    c.add_argument("diff")
    c.add_argument("findings")
    f = sub.add_parser("findings")
    f.add_argument("file")
    v = sub.add_parser("coverage")
    v.add_argument("diff")
    v.add_argument("ledger")
    q = sub.add_parser("snippets")
    q.add_argument("diff")
    q.add_argument("findings")
    q.add_argument("--root")
    r = sub.add_parser("resolve")
    r.add_argument("ledger")
    args = parser.parse_args(argv)
    if args.mode == "findings":
        return _findings_main(args.file)
    if args.mode == "resolve":
        return _resolve_main(args.ledger)
    try:
        with open(args.diff, "rb") as stream:
            data = stream.read()
        files = parse(decode(data))
        if args.mode == "summary":
            report = summarise(files, data, args.base, args.head)
        else:
            with open(args.ledger if args.mode == "coverage" else args.findings, "rb") as stream:
                loaded = json.loads(decode(stream.read()))
            if args.mode == "snippets":
                report = snippets(files, loaded, args.root)
            else:
                report = (check if args.mode == "check" else coverage)(files, loaded)
            report["diff_sha256"] = hashlib.sha256(data).hexdigest()
    except (OSError, ValueError) as exc:  # DiffError and JSON errors are ValueErrors
        sys.stdout.write(json.dumps({"format": FORMAT, "mode": args.mode, "status": "unreadable",
                                     "error": str(exc)}, indent=2) + "\n")
        return 2
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    if report["status"] in ("inconclusive", "not-run"):
        return 2
    return 0 if report["status"] in ("parsed", "located", "complete", "verified") else 1


if __name__ == "__main__":
    sys.exit(main())
