#!/usr/bin/env python3
"""Conservation check between two exports of the canonical tracker (before and after an edit).

Run it before saving or syncing a tracker change. It blocks on lost records,
duplicate record IDs, changed identities (employer, requisition, URL), dropped
columns and application history that moved backwards. It lists cleared values
for review, and flags added rows that look like a repost or duplicate of an
existing role, which should be linked rather than merged. Read-only.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

import jobscura_common as common
from jobscura_common import require

VERSION = "1.0.0"
TITLE_MATCH = 0.6
# Match individual milestones so negation applies to each occurrence independently.
FINAL = re.compile(r"\b(applied|submitted|interview\w*|offer\w*|rejected|declined|withdrawn|hired|accepted)\b", re.I)
NEGATED = re.compile(r"\b(?:not|never|yet to)\s+(?:yet\s+)?$", re.I)
TERMINAL = {"rejected", "declined", "withdrawn", "hired", "accepted"}


def application_state(status):
    text = str(status or "")
    milestones = [m.group().casefold() for m in FINAL.finditer(text)
                  if not NEGATED.search(text[:m.start()])]
    terminals = set(milestones) & TERMINAL
    rank = max((3 if word.startswith("offer") else 2 if word.startswith("interview") else 1
                for word in milestones if word not in TERMINAL), default=0)
    return rank, terminals


def reached_final(status):
    rank, terminals = application_state(status)
    return bool(rank or terminals)


def load(path, overrides):
    import deadlines
    rows = deadlines.load_rows(path, overrides)
    headers = []
    for row in rows:
        for header in row["_raw"]:
            if header not in headers:
                headers.append(header)
    return rows, headers


def identity(row):
    return {"employer": common.employer_key(row.get("employer")),
            "requisition_id": str(row.get("requisition_id") or "").strip().casefold() or None,
            "url": common.normalized_link(row.get("url"))}


def by_id(rows, side, problems):
    index, missing = {}, []
    for row in rows:
        rid = str(row.get("record_id") or "").strip()
        if not rid:
            missing.append(row["_row"])
            continue
        if rid in index:
            problems.append({"kind": "duplicate_record_id", "side": side, "record_id": rid})
        index[rid] = row
    return index, missing


def compare(before_path, after_path, overrides=None):
    overrides = overrides or {}
    before_rows, before_headers = load(before_path, overrides)
    after_rows, after_headers = load(after_path, overrides)
    problems, review = [], []
    before, before_missing = by_id(before_rows, "before", problems)
    after, after_missing = by_id(after_rows, "after", problems)
    require(before or after, "neither export has record IDs; map one with --map record_id=Header")
    dropped = [h for h in before_headers if h not in after_headers]
    if dropped:
        problems.append({"kind": "columns_removed", "columns": dropped})
    if before_missing:
        review.append({"kind": "rows_without_record_id", "side": "before", "rows": before_missing})
    if len(after_missing) < len(before_missing):
        problems.append({"kind": "unidentified_rows_decreased", "before": len(before_missing),
                         "after": len(after_missing),
                         "message": "Add record IDs or compare unidentified rows by hand."})
    if after_missing:
        review.append({"kind": "rows_without_record_id", "side": "after", "rows": after_missing})
    for rid in sorted(set(before) - set(after)):
        problems.append({"kind": "record_removed", "record_id": rid, "employer": before[rid].get("employer"),
                         "title": before[rid].get("title")})
    changed = []
    for rid in sorted(set(before) & set(after)):
        old, new = before[rid], after[rid]
        old_id, new_id = identity(old), identity(new)
        for key in ("employer", "requisition_id", "url"):
            if old_id[key] and old_id[key] != new_id[key]:
                problems.append({"kind": "identity_changed", "record_id": rid, "field": key,
                                 "before": old.get(key), "after": new.get(key)})
        old_rank, old_terminal = application_state(old.get("status"))
        new_rank, new_terminal = application_state(new.get("status"))
        if ((old_rank or old_terminal) and not (new_rank or new_terminal)
                or not old_terminal and not new_terminal and new_rank < old_rank):
            problems.append({"kind": "application_history_regressed", "record_id": rid,
                             "before": old.get("status"), "after": new.get("status")})
        if old_terminal and new_rank and not new_terminal:
            review.append({"kind": "status_reopened", "record_id": rid,
                           "before": old.get("status"), "after": new.get("status")})
        if old_terminal and new_terminal and old_terminal != new_terminal:
            review.append({"kind": "terminal_status_changed", "record_id": rid,
                           "before": old.get("status"), "after": new.get("status")})
        cleared = [h for h, v in old["_raw"].items() if str(v or "").strip() and not str(new["_raw"].get(h) or "").strip()]
        if cleared:
            review.append({"kind": "values_cleared", "record_id": rid, "columns": cleared})
        if old["_raw"] != new["_raw"]:
            changed.append(rid)
    added = sorted(set(after) - set(before))
    candidates, compared = [], set()
    for rid in added:
        row, row_id = after[rid], identity(after[rid])
        for other_id, other in after.items():
            pair = frozenset((rid, other_id))
            if other_id == rid or pair in compared:
                continue
            compared.add(pair)
            other_identity = identity(other)
            if not row_id["employer"] or row_id["employer"] != other_identity["employer"]:
                continue
            same_link = row_id["url"] and row_id["url"] == other_identity["url"]
            same_req = row_id["requisition_id"] and row_id["requisition_id"] == other_identity["requisition_id"]
            similarity, variant = common.location_title_similarity(row, other)
            if same_link or same_req:
                problems.append({"kind": "duplicate_identity", "record_id": rid, "matches": other_id,
                                 "basis": "same URL" if same_link else "same requisition"})
            elif variant:
                review.append({"kind": "location_variant", "record_id": rid, "related_to": other_id,
                               "title_similarity": similarity,
                               "note": "same role in another location; not a repost"})
            elif similarity >= TITLE_MATCH:
                candidates.append({"record_id": rid, "related_to": other_id, "title_similarity": round(similarity, 2),
                                   "note": "different requisition/URL, similar title at the same employer: link as a "
                                           "possible repost; never merge or overwrite the earlier record",
                                   **common.title_tail_review(row, other)})
    status = "blocked" if problems else "review_required" if review or candidates else "conserved"
    return {"schema_version": 1, "tool": "tracker_diff", "tool_version": VERSION, "status": status,
            "before": {"file": Path(before_path).name, "records": len(before),
                       "rows": len(before_rows), "unidentified": len(before_missing),
                       "sha256": common.sha256(common.read_input(before_path))},
            "after": {"file": Path(after_path).name, "records": len(after),
                      "rows": len(after_rows), "unidentified": len(after_missing),
                      "sha256": common.sha256(common.read_input(after_path))},
            "expected_after_records": len(before) + len(added) - len(set(before) - set(after)),
            "added": added, "changed": changed, "problems": problems, "review": review, "repost_candidates": candidates,
            "limits": "Structural comparison of two exports. It cannot see formulas, hidden tabs or edits made outside "
                      "the exported columns, and similarity is a prompt to look, not proof of a repost."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--before", required=True, help="export taken before the edit (JSON/CSV/TSV)")
    parser.add_argument("--after", required=True, help="export of the edited tracker")
    parser.add_argument("--map", action="append", default=[], metavar="FIELD=Header")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    def run():
        import deadlines
        overrides = {}
        for item in args.map:
            require("=" in item, "--map needs FIELD=Header")
            field, header = item.split("=", 1)
            require(field.strip() in deadlines.FIELDS, "unknown --map field: " + field.strip())
            overrides[field.strip()] = header.strip().casefold()
        common.emit(compare(args.before, args.after, overrides), args.out)
    return common.run_cli(run)


if __name__ == "__main__":
    raise SystemExit(main())
