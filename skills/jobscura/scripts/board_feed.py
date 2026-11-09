#!/usr/bin/env python3
"""Normalise, screen and diff an employer job-board feed that the host already fetched.

Input is the JSON a public board endpoint returned (Greenhouse, Lever, Ashby or
SmartRecruiters; see references/helpers.md), saved to a file by a host tool.
This helper never fetches anything. It produces one record shape, applies the
user's title and location filters, marks postings already in the tracker and
possible reposts of tracked roles, and, given the previous snapshot of the
same board, lists postings that are new and postings that disappeared.

A posting missing from a feed is a reason to verify, not proof of closure: the
board may paginate, filter or fail. Never mark a role closed from this alone.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import re

import jobscura_common as common
from jobscura_common import ToolError, require

VERSION = "1.0.0"
TITLE_MATCH = 0.6     # token Jaccard for "same role, new posting"


def epoch_or_iso(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if not math.isfinite(value):
                raise ValueError("must be finite")
            seconds = value / 1000 if value > 1e11 else value  # Lever and others send epoch milliseconds
            return datetime.fromtimestamp(seconds, timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError) as exc:
            raise ToolError(f"invalid timestamp {value!r}: {exc}") from None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else None


def location_text(*parts):
    seen, out = set(), []
    for part in parts:
        for item in part if isinstance(part, list) else [part]:
            if isinstance(item, dict):
                item = item.get("name") or item.get("location") or ", ".join(
                    str(item[k]) for k in ("city", "region", "country") if item.get(k))
            text = " ".join(str(item or "").split())
            if text and text.casefold() not in seen:
                seen.add(text.casefold())
                out.append(text)
    return " · ".join(out) or None


def greenhouse(data, board):
    for job in data.get("jobs", []):
        yield {"id": str(job.get("id", "")), "title": job.get("title"), "url": job.get("absolute_url"),
               "location": location_text(job.get("location")), "requisition_id": job.get("requisition_id"),
               "posted": epoch_or_iso(job.get("first_published") or job.get("updated_at")), "remote": None}


def lever(data, board):
    for job in data if isinstance(data, list) else []:
        categories = job.get("categories") or {}
        workplace = str(job.get("workplaceType") or "").casefold()
        yield {"id": str(job.get("id", "")), "title": job.get("text"), "url": job.get("hostedUrl"),
               "location": location_text(categories.get("location"), categories.get("allLocations") or []),
               "requisition_id": None, "posted": epoch_or_iso(job.get("createdAt")),
               "remote": True if workplace == "remote" else None}


def ashby(data, board):
    for job in data.get("jobs", []):
        secondary = [x.get("location") if isinstance(x, dict) else x for x in job.get("secondaryLocations") or []]
        workplace = str(job.get("workplaceType") or "").casefold()
        yield {"id": str(job.get("id", "")), "title": job.get("title"), "url": job.get("jobUrl"),
               "location": location_text(job.get("location"), secondary), "requisition_id": None,
               "posted": epoch_or_iso(job.get("publishedAt")),
               "remote": True if job.get("isRemote") is True or workplace == "remote" else None}


def smartrecruiters(data, board):
    for job in data.get("content", []):
        place = job.get("location") or {}
        url = job.get("ref") if str(job.get("ref", "")).startswith("https://jobs.") else None
        if not url and board and job.get("id"):
            url = f"https://jobs.smartrecruiters.com/{board}/{job['id']}"
        yield {"id": str(job.get("id", "")), "title": job.get("name"), "url": url,
               "location": location_text(place), "requisition_id": job.get("refNumber"),
               "posted": epoch_or_iso(job.get("releasedDate")),
               "remote": True if isinstance(place, dict) and place.get("remote") is True else None}


VENDORS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "smartrecruiters": smartrecruiters}


def detect(data):
    if isinstance(data, list) and data and isinstance(data[0], dict) and "hostedUrl" in data[0]:
        return "lever"
    if isinstance(data, dict):
        jobs = data.get("jobs")
        if isinstance(jobs, list) and jobs and isinstance(jobs[0], dict):
            return "greenhouse" if "absolute_url" in jobs[0] else "ashby" if "jobUrl" in jobs[0] else None
        if isinstance(data.get("content"), list):
            return "smartrecruiters"
    return None


def normalize(data, vendor=None, board=None, company=None, *, observed_ids=None):
    vendor = vendor or detect(data)
    require(vendor in VENDORS, "unrecognised feed: pass --vendor greenhouse|lever|ashby|smartrecruiters")
    container = "content" if vendor == "smartrecruiters" else "jobs"
    valid = isinstance(data, list) if vendor == "lever" else (
        isinstance(data, dict) and isinstance(data.get(container), list))
    shape = f"object with keys {sorted(data)}" if isinstance(data, dict) else type(data).__name__
    require(valid, f"{vendor} feed has invalid container: {shape}; expected " +
            ("a list" if vendor == "lever" else f"an object with a list {container!r}"))
    records, skipped = [], 0
    for raw in VENDORS[vendor](data, board):
        # A posting can be present in the feed even if it lacks a usable title.
        if observed_ids is not None and raw["id"]:
            observed_ids.add(" ".join(raw["id"].split()))
        if not raw.get("id") or not raw.get("title"):
            skipped += 1
            continue
        record = {k: (" ".join(v.split()) if isinstance(v, str) else v) for k, v in raw.items()}
        record.update(vendor=vendor, board=board, company=company, key=f"{vendor}:{board or ''}:{record['id']}")
        records.append(record)
    keys = [r["key"] for r in records]
    require(len(keys) == len(set(keys)), "feed repeats a posting id; save the complete, unmodified response")
    return records, skipped


def terms(values):
    out = []
    for value in values or []:
        out += [t.strip().casefold() for t in str(value).split(",") if t.strip()]
    return out


def has_term(text, candidates):
    lowered = str(text or "").casefold()
    return next((t for t in candidates if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", lowered)), None)


def screen(record, include, exclude, locations, remote_ok):
    if exclude and has_term(record["title"], exclude):
        return "excluded: title has '" + has_term(record["title"], exclude) + "'"
    if include and not has_term(record["title"], include):
        return "excluded: title matches no target term"
    if locations:
        if record.get("location") is None:
            return "kept: location not stated"
        if not has_term(record["location"], locations) and not (remote_ok and (record.get("remote") or
                                                                              has_term(record["location"], ["remote"]))):
            return "excluded: location outside targets"
    return "kept"


def tracker_index(path):
    import deadlines
    rows = deadlines.load_rows(path, {})
    return [{"record_id": r.get("record_id"), "employer": common.employer_key(r.get("employer")),
             "title": r.get("title"), "location": common.record_location(r), "url": common.normalized_link(r.get("url")),
             "requisition_id": str(r.get("requisition_id") or "").strip().casefold() or None} for r in rows]


def run(feed, vendor=None, board=None, company=None, previous=None, tracker=None, include=(), exclude=(),
        locations=(), context=None):
    data = common.read_json(feed)
    vendor = vendor or detect(data)
    observed_ids = set()
    records, skipped = normalize(data, vendor, board, company, observed_ids=observed_ids)
    remote_ok = False
    if context:
        import user_context
        try:
            search = user_context.load_context(context)["preferences"].get("search", {})
        except user_context.ContextError as exc:
            raise ToolError(str(exc)) from None
        include = list(include) or search.get("target_roles", [])
        exclude = list(exclude) + search.get("exclusions", [])
        locations = list(locations) or search.get("locations", [])
        remote_ok = "remote" in search.get("work_arrangements", [])
    include, exclude, locations = terms(include), terms(exclude), terms(locations)
    remote_ok = remote_ok or "remote" in locations
    tracked = tracker_index(tracker) if tracker else []
    employer = common.employer_key(company)
    previous_ids, previous_records = set(), {}
    if previous:
        snapshot = common.read_json(previous)
        require(isinstance(snapshot, dict), "previous snapshot field tool differs: expected a board_feed result object")
        identity = {"schema_version": 1, "tool": "board_feed", "vendor": vendor,
                    "board": board.casefold() if board is not None else None, "company": employer}
        for field, expected in identity.items():
            actual = snapshot.get(field)
            if field == "board" and isinstance(actual, str):
                actual = actual.casefold()
            if field == "company":
                actual = common.employer_key(actual)
            require(actual == expected, f"previous snapshot field {field} differs: {actual!r} != {expected!r}")
        # Board identity is already validated case-insensitively. Compare posting
        # IDs within that board while retaining the original public keys.
        previous_records = {r["id"]: r for r in snapshot.get("postings", [])}
        previous_ids = set(previous_records)
    postings = []
    for record in records:
        record["screen"] = screen(record, include, exclude, locations, remote_ok)
        link = common.normalized_link(record.get("url"))
        req = str(record.get("requisition_id") or "").strip().casefold() or None
        same_employer = [t for t in tracked if employer and t["employer"] == employer]
        exact = [t["record_id"] for t in same_employer if (link and t["url"] == link) or (req and t["requisition_id"] == req)]
        record["tracker"] = {"status": "tracked" if exact else "not_tracked", "records": exact}
        if not exact:
            similar, variants = [], []
            for tracked_role in same_employer:
                score, variant = common.location_title_similarity(record, tracked_role)
                candidate = {"record_id": tracked_role["record_id"], "title_similarity": score}
                if variant:
                    variants.append(candidate)
                elif score is not None and score >= TITLE_MATCH:
                    candidate.update(common.title_tail_review(record, tracked_role))
                    similar.append(candidate)
            if similar:
                record["tracker"] = {"status": "possible_repost_of_tracked_role", "records": similar}
            elif variants:
                record["tracker"] = {"status": "location_variant", "records": variants}
            if variants:
                record["tracker"]["location_variants"] = variants
        if previous:
            record["since_previous"] = "unchanged" if record["id"] in previous_ids else "new"
            old = previous_records.get(record["id"])
            if old and any(old.get(k) != record.get(k) for k in ("title", "location", "url")):
                record["since_previous"] = "changed"
        postings.append(record)
    disappeared = [{k: previous_records[posting_id].get(k) for k in ("key", "title", "url", "location")}
                   for posting_id in sorted(previous_ids - observed_ids)]
    kept = [p for p in postings if p["screen"].startswith("kept")]
    return {"schema_version": 1, "tool": "board_feed", "tool_version": VERSION, "vendor": records[0]["vendor"] if records else vendor,
            "board": board, "company": company, "feed_file": Path(feed).name, "feed_sha256": common.sha256(common.read_input(feed)),
            "counts": {"postings": len(postings), "kept": len(kept), "skipped_incomplete": skipped,
                       "new": sum(1 for p in postings if p.get("since_previous") == "new"),
                       "disappeared": len(disappeared), "tracked": sum(1 for p in postings if p["tracker"]["status"] == "tracked"),
                       "possible_reposts": sum(1 for p in postings if p["tracker"]["status"] == "possible_repost_of_tracked_role")},
            "filters": {"include": include, "exclude": exclude, "locations": locations, "remote_ok": remote_ok},
            "postings": postings, "disappeared_since_previous": disappeared,
            "guidance": "New, kept postings go to intake. Disappeared postings need a check of the live posting page before "
                        "any tracker change. Possible reposts are linked candidates for review, never merged automatically.",
            "limits": "Reads one saved feed response; it does not fetch, paginate or verify. Filters are keyword matches."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--feed", required=True, help="saved JSON response from a public board endpoint")
    parser.add_argument("--vendor", choices=sorted(VENDORS), help="default: detected from the JSON shape")
    parser.add_argument("--board", help="board slug (needed to build SmartRecruiters links)")
    parser.add_argument("--company", required=True, help="employer name as written in the tracker")
    parser.add_argument("--previous", help="earlier board_feed result for the same board, for new/disappeared")
    parser.add_argument("--tracker", help="read-only tracker export (JSON/CSV/TSV) to mark tracked roles and reposts")
    parser.add_argument("--include", action="append", default=[], help="title terms, comma separated")
    parser.add_argument("--exclude", action="append", default=[], help="title terms to drop, comma separated")
    parser.add_argument("--location", action="append", default=[], help="location terms, comma separated ('remote' allowed)")
    parser.add_argument("--context", help="validated private context: search preferences supply default filters")
    parser.add_argument("--out", help="write the result (the next run's --previous) to this new file")
    args = parser.parse_args(argv)
    return common.run_cli(lambda: common.emit(run(args.feed, args.vendor, args.board, args.company, args.previous, args.tracker,
                                                  args.include, args.exclude, args.location, args.context), args.out))


if __name__ == "__main__":
    raise SystemExit(main())
