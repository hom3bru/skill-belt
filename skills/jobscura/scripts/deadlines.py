#!/usr/bin/env python3
"""Deterministic deadline countdowns, reminder windows and status-check plan.

Reads a read-only tracker export (JSON/CSV/TSV) and computes, in the user's
explicit IANA timezone and for an explicit "as of" moment:

- calendar days to each stated date and, with an exact cutoff, hours remaining;
- which reminder window (default 14/7/3/1/0 days) is newly due, deduplicated
  against reminders actually recorded as sent;
- which roles need a status check (dated roles daily, undated every other day by
  default) and long-open / no-deadline flags;
- the morning digest: every active role closing within the horizon.

Never guesses: ambiguous dates (03/04/2026), unknown timezones and missing
deadlines stay unresolved. Never edits the tracker or sends anything.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, time, timedelta, timezone
import io
from pathlib import Path
import re

import jobscura_common as common
from jobscura_common import ToolError, require

VERSION = "1.0.0"
FIELDS = {
    "record_id": ("record id", "record_id", "tracker id", "id"),
    "employer": ("employer", "company", "organization", "organisation", "company name"),
    "title": ("role", "title", "job title", "position"),
    "requisition_id": ("requisition id", "requisition_id", "requisition", "req id", "job id"),
    "deadline": ("deadline", "closing date", "close date", "application deadline", "closes", "deadline date", "closing"),
    "deadline_time": ("deadline time", "cutoff time", "closing time", "cutoff"),
    "deadline_tz": ("deadline timezone", "deadline tz", "cutoff timezone", "closing timezone"),
    "deadline_type": ("deadline type", "deadline_type", "close type"),
    "status": ("status", "application status", "stage"),
    "posting_status": ("posting status", "public status", "vacancy status"),
    "last_checked": ("last checked", "last attempted check", "last_checked", "checked"),
    "last_verified": ("last verified", "verified", "last_verified", "last successful check"),
    "posted": ("posted", "date posted", "posted date", "first published", "published"),
    "discovered": ("discovered", "date found", "found", "added", "date added"),
    "sent_reminders": ("reminders sent", "sent reminders", "reminder receipts", "sent_reminders"),
    "url": ("application url", "url", "job url", "link", "source url", "posting url"),
}
DEADLINE_TYPES = {"hard_cutoff", "date_only", "anticipated", "first_review", "minimum_open", "rolling", "unknown"}
SOFT_TYPES = {"anticipated", "first_review", "minimum_open"}
INACTIVE = re.compile(r"\b(applied|submitted|rejected|declined|withdrawn|withdrew|closed|filled|hired|offer|archived|"
                      r"not applying|skip(?:ped)?|parked|cancel+ed)\b", re.I)
NEGATED = re.compile(r"\b(?:not|never|yet to|hasn'?t|haven'?t|didn'?t)\s+(?:yet\s+|been\s+)?$", re.I)
CLOSED_POSTING = re.compile(r"\b(closed|expired|filled|removed|cancel+ed)\b", re.I)
MONTH_NAMES = {m: i for i, names in enumerate([("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
                                                ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
                                                ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
                                                ("dec", "december")], 1) for m in names}


def zone(name):
    require(isinstance(name, str) and name.strip(), "an explicit IANA timezone is required (--timezone or context)")
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError as exc:
        raise ToolError("zoneinfo is unavailable in this Python; timezone-dependent dates cannot be computed") from exc
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ToolError("timezone is not available in this host's timezone database; install tzdata or "
                        "choose a valid IANA name, never a guessed offset") from exc


def parse_date(value):
    """ISO dates/datetimes and month-name dates only; numeric day/month orders are ambiguous."""
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text), None
        except ValueError:
            return None, "invalid_date"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ][\d:.]+(?:Z|[+-]\d{2}:?\d{2})?", text):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed, None
        except ValueError:
            return None, "invalid_date"
    found = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", text) or None
    if found:
        day, month, year = int(found.group(1)), MONTH_NAMES.get(found.group(2).casefold()), int(found.group(3))
    else:
        found = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", text)
        if found:
            month, day, year = MONTH_NAMES.get(found.group(1).casefold()), int(found.group(2)), int(found.group(3))
    if found and month:
        try:
            return date(year, month, day), None
        except ValueError:
            return None, "invalid_date"
    if re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", text):
        return None, "ambiguous_numeric_date"
    return None, "unparsed_date"


def parse_time(value):
    if not value or not str(value).strip():
        return None
    found = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?", str(value).strip())
    require(found, "deadline time must look like 17:00 or 5:00 PM")
    hour, minute = int(found.group(1)), int(found.group(2))
    if found.group(4):
        require(1 <= hour <= 12, "12-hour time must use hours 1-12")
        hour = hour % 12 + (12 if found.group(4).casefold() == "pm" else 0)
    require(hour < 24 and minute < 60, "invalid deadline time")
    return time(hour, minute, int(found.group(3) or 0))


def load_rows(path, overrides):
    p = Path(path)
    suffix = p.suffix.casefold()
    if suffix == ".json":
        data = common.read_json(p)
        data = data.get("records") if isinstance(data, dict) else data
        require(isinstance(data, list) and all(isinstance(r, dict) for r in data), "tracker JSON must be a list of objects")
        raw = data
    elif suffix in {".csv", ".tsv"}:
        text = common.read_input(p).decode("utf-8-sig")
        raw = list(csv.DictReader(io.StringIO(text), delimiter="\t" if suffix == ".tsv" else ","))
    else:
        raise ToolError("tracker export must be .json, .csv or .tsv (export the canonical tracker read-only)")
    rows = []
    for index, row in enumerate(raw, 1):
        mapped = {str(k).strip().casefold(): v for k, v in row.items() if k is not None}
        record = {"_row": index, "_raw": {str(k).strip(): v for k, v in row.items() if k is not None}}
        for field, aliases in FIELDS.items():
            names = (overrides[field],) if field in overrides else aliases
            value = next((mapped[n] for n in names if n in mapped and mapped[n] not in (None, "")), None)
            record[field] = value if not isinstance(value, str) else value.strip()
        rows.append(record)
    require(rows, "tracker export has no rows")
    return rows


def receipts(value):
    if value is None:
        return set()
    items = value if isinstance(value, list) else re.split(r"[;,|\s]+", str(value))
    keys = set()
    for item in items:
        found = re.fullmatch(r"(\d{1,3})\s*d?(?:ays?)?", str(item).strip(), re.I)
        if found:
            keys.add(int(found.group(1)))
    return keys


def plan(tracker, timezone_name, as_of=None, conventions=None, overrides=None):
    tz = zone(timezone_name)
    moment = common.parse_timestamp(as_of, "as_of") if as_of else common.now()
    local_now = moment.astimezone(tz)
    today = local_now.date()
    rules = conventions or {}
    windows = sorted(set(rules.get("reminder_windows_days", [14, 7, 3, 1, 0])), reverse=True)
    horizon = rules.get("closing_horizon_days", 14)
    dated_every, undated_every = rules.get("dated_check_days", 1), rules.get("undated_check_days", 2)
    urgency, long_open = rules.get("urgency_open_days", 14), rules.get("long_open_days", 60)
    records, digest = [], {"closing_within_horizon": [], "reminders_due": [], "checks_due": [], "unresolved": []}
    for row in load_rows(tracker, overrides or {}):
        label = {k: row.get(k) for k in ("record_id", "employer", "title", "requisition_id", "url")}
        label["row"] = row["_row"]
        status_text = str(row.get("status") or "")
        # "Not applied" / "not yet submitted" are still active; "Not applying" is matched as its own phrase.
        inactive = any(not NEGATED.search(status_text[:m.start()]) for m in INACTIVE.finditer(status_text))
        posting_closed = bool(CLOSED_POSTING.search(str(row.get("posting_status") or "")))
        kind = str(row.get("deadline_type") or "").strip().casefold().replace(" ", "_").replace("-", "_") or None
        if kind and kind not in DEADLINE_TYPES:
            digest["unresolved"].append({**label, "issue": "unknown_deadline_type", "value": row.get("deadline_type")})
            kind = "unknown"
        entry = {**label, "active": not inactive and not posting_closed, "deadline_type": kind, "notes": []}
        deadline, problem = parse_date(row.get("deadline"))
        if problem:
            digest["unresolved"].append({**label, "issue": problem, "value": row.get("deadline")})
            entry["notes"].append(problem + ": not guessed")
        cutoff = None
        cutoff_zone, cutoff_time = None, None
        try:
            cutoff_zone = zone(row["deadline_tz"]) if row.get("deadline_tz") else None
            cutoff_time = parse_time(row.get("deadline_time"))
        except ToolError as exc:
            digest["unresolved"].append({**label, "issue": "unusable_cutoff", "detail": str(exc)})
            entry["notes"].append("cutoff time/timezone unusable: treated as date only")
            cutoff_zone = cutoff_time = None
        if isinstance(deadline, datetime):
            cutoff = deadline if deadline.tzinfo else (deadline.replace(tzinfo=cutoff_zone) if cutoff_zone else None)
            if cutoff is None:
                entry["notes"].append("cutoff time has no timezone: treated as date only")
            deadline = deadline.date() if cutoff is None else cutoff.astimezone(tz).date()
        elif deadline and cutoff_time:
            if cutoff_zone:
                cutoff = datetime.combine(deadline, cutoff_time, cutoff_zone)
                deadline = cutoff.astimezone(tz).date()
            else:
                entry["notes"].append("cutoff time has no timezone: treated as date only")
        if kind == "rolling":
            deadline, cutoff = None, None
            entry["notes"].append("rolling: no countdown")
        if deadline:
            days = (deadline - today).days
            entry.update(deadline=deadline.isoformat(), days_remaining=days,
                         measures=("exact local cutoff" if cutoff else
                                   f"{kind.replace('_', ' ')} date (not a hard close)" if kind in SOFT_TYPES else
                                   "stated date; exact cutoff unknown, do not assume midnight"))
            if cutoff:
                entry["cutoff_local"] = cutoff.astimezone(tz).isoformat()
                entry["hours_remaining"] = round((cutoff - moment).total_seconds() / 3600, 1)
            if days < 0:
                entry["notes"].append("date passed: verify status; not proof of closure or of a missed application"
                                      if kind not in SOFT_TYPES else "soft date passed: role may still be open")
            if entry["active"] and 0 <= days <= horizon:
                digest["closing_within_horizon"].append({**label, "deadline": entry["deadline"], "days_remaining": days,
                                                         "measures": entry["measures"]})
            entered = [w for w in windows if days <= w]
            sent = receipts(row.get("sent_reminders"))
            if entry["active"] and days >= 0 and entered:
                window = min(entered)
                entry["window"] = window
                if window not in sent and not (sent and min(sent) <= window):
                    reminder = {**label, "window_days": window, "days_remaining": days, "deadline": entry["deadline"],
                                "dedupe_key": "|".join(str(x or "") for x in (row.get("employer"), row.get("requisition_id")
                                                                              or row.get("record_id"), entry["deadline"], window))}
                    if cutoff:
                        reminder["cutoff_local"] = entry["cutoff_local"]
                    digest["reminders_due"].append(reminder)
        else:
            entry.update(deadline=None, days_remaining=None)
        opened, _ = parse_date(row.get("posted") or row.get("discovered"))
        if isinstance(opened, datetime):
            opened = opened.date()
        if opened:
            entry["days_open"] = (today - opened).days
            if not deadline and not problem and kind != "rolling" and entry["days_open"] > urgency:
                entry["notes"].append(f"no stated deadline and open over {urgency} days: act or verify soon")
            if entry["days_open"] > long_open:
                entry["notes"].append(f"open over {long_open} days: possible evergreen or stale listing, verify")
        if entry["active"]:
            every = dated_every if deadline else undated_every
            last, _ = parse_date(row.get("last_checked"))
            if isinstance(last, datetime):
                last = last.astimezone(tz).date() if last.tzinfo else last.date()
            due = last + timedelta(days=every) if last else today
            entry["next_check"] = due.isoformat()
            if due <= today:
                digest["checks_due"].append({**label, "cadence_days": every, "last_checked": last.isoformat() if last else None})
            verified, _ = parse_date(row.get("last_verified"))
            if last and verified and (verified.date() if isinstance(verified, datetime) else verified) < last:
                entry["notes"].append("last check did not verify: earlier evidence was not refreshed")
        records.append(entry)
    def urgency_key(e):
        d = e.get("days_remaining")
        return (not e["active"], d is None, d if d is not None else 0, str(e.get("employer") or ""))
    records.sort(key=urgency_key)
    digest["closing_within_horizon"].sort(key=lambda e: e["days_remaining"])
    digest["reminders_due"].sort(key=lambda e: e["days_remaining"])
    return {"schema_version": 1, "tool": "deadlines", "tool_version": VERSION, "status": "plan_only_nothing_sent",
            "as_of": common.iso(moment), "local_date": today.isoformat(), "timezone": timezone_name,
            "conventions": {"reminder_windows_days": windows, "closing_horizon_days": horizon,
                            "dated_check_days": dated_every, "undated_check_days": undated_every,
                            "urgency_open_days": urgency, "long_open_days": long_open},
            "digest": digest, "records": records,
            "limits": "Computed from the supplied export only. A reminder is due until an actual send is recorded in the "
                      "tracker; this plan sends nothing, schedules nothing and does not verify vacancies."}


# ------------------------------------------------------------------ calendar export (RFC 5545)
ALARM_TIME = time(9, 0)  # reminders fire at 09:00 local on the window's day


def ics_escape(value):
    """RFC 5545 TEXT escaping: backslash, semicolon, comma and newline."""
    return (str(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def ics_fold(line):
    """Fold content lines at 75 octets without splitting a UTF-8 character."""
    data, out, chunk = line.encode("utf-8"), [], b""
    limit = 75
    for char in line:
        encoded = char.encode("utf-8")
        if len(chunk) + len(encoded) > limit:
            out.append(chunk.decode("utf-8"))
            chunk, limit = b"", 74  # continuation lines start with one space
        chunk += encoded
    out.append(chunk.decode("utf-8"))
    return "\r\n ".join(out) if len(data) > 75 else line


def ics_utc(moment):
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def calendar(result, timezone_name, skipped=None):
    """Events for active dated roles with alarms at each future reminder window.

    The user imports the file into their own calendar; Jobscura schedules and sends nothing.
    UIDs are stable per employer/requisition/deadline, so a re-import updates the same events.
    """
    tz = zone(timezone_name)
    as_of = common.parse_timestamp(result["as_of"], "as_of")
    windows = result["conventions"]["reminder_windows_days"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Skill Belt//Jobscura deadlines " + VERSION + "//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Job application deadlines"]
    events, uids = 0, set()
    for record in result["records"]:
        if not record["active"] or not record.get("deadline") or record.get("days_remaining") is None \
                or record["days_remaining"] < 0:
            continue
        deadline = date.fromisoformat(record["deadline"])
        cutoff = datetime.fromisoformat(record["cutoff_local"]) if record.get("cutoff_local") else None
        if record.get("record_id") or record.get("requisition_id"):
            # Preserve published UIDs for identified rows, including the empty fields.
            identity = "|".join(str(record.get(k) or "") for k in ("employer", "requisition_id", "record_id")) + "|" + record["deadline"]
        elif record.get("url"):
            link = common.normalized_link(record["url"])
            require(link, "calendar URL must be an HTTP(S) URL for a stable identity")
            identity = "|".join((str(record.get("employer") or ""), link, record["deadline"]))
        else:
            if skipped is not None:
                skipped.append({k: record.get(k) for k in ("row", "employer", "title")} |
                               {"reason": "no record ID, requisition ID or URL for a stable calendar identity"})
            continue
        uid = "jobscura-" + common.sha256(identity.encode("utf-8"))[:32] + "@jobscura.invalid"
        require(uid not in uids, "duplicate calendar UID; resolve duplicate role identities before exporting")
        uids.add(uid)
        role = " - ".join(x for x in (record.get("title"), record.get("employer")) if x) or str(record.get("record_id") or "role")
        prefix = "Closes" if cutoff or record.get("deadline_type") not in SOFT_TYPES else \
            record["deadline_type"].replace("_", " ").capitalize()
        lines += ["BEGIN:VEVENT", "UID:" + uid, "DTSTAMP:" + ics_utc(as_of)]
        if cutoff:
            lines += ["DTSTART:" + ics_utc(cutoff - timedelta(hours=1)), "DTEND:" + ics_utc(cutoff)]
        else:
            lines += ["DTSTART;VALUE=DATE:" + deadline.strftime("%Y%m%d"),
                      "DTEND;VALUE=DATE:" + (deadline + timedelta(days=1)).strftime("%Y%m%d")]
        lines.append("SUMMARY:" + ics_escape(f"{prefix}: {role}"))
        description = [record.get("measures") or "", "Link: " + record["url"] if record.get("url") else "",
                       "From Jobscura deadlines.py as of " + result["as_of"] + ". Verify the live posting before acting."]
        lines.append("DESCRIPTION:" + ics_escape("\n".join(x for x in description if x)))
        if record.get("url") and re.match(r"https?://\S+$", str(record["url"])):
            lines.append("URL:" + str(record["url"]))
        for window in windows:
            local_day = deadline - timedelta(days=window)
            alarm = datetime.combine(local_day, ALARM_TIME, tz)
            if cutoff and window == 0 and alarm >= cutoff:
                alarm = cutoff - timedelta(hours=2)  # early-morning cutoff: warn before it passes
            if alarm <= as_of:
                continue  # never fire a reminder for a window that has already opened
            label = "today" if window == 0 else f"in {window} day{'s' if window != 1 else ''}"
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER;VALUE=DATE-TIME:" + ics_utc(alarm),
                      "DESCRIPTION:" + ics_escape(f"{prefix} {label}: {role}"), "END:VALARM"]
        lines.append("END:VEVENT")
        events += 1
    lines.append("END:VCALENDAR")
    return "".join(ics_fold(line) + "\r\n" for line in lines), events


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--tracker", required=True, help="read-only JSON/CSV/TSV export of the canonical tracker")
    parser.add_argument("--timezone", help="IANA timezone, e.g. America/Chicago (or supply --context)")
    parser.add_argument("--context", help="absolute path to validated private context (timezone and monitoring)")
    parser.add_argument("--as-of", help="ISO-8601 moment with timezone (default now) for reproducible plans")
    parser.add_argument("--map", action="append", default=[], metavar="FIELD=Header",
                        help="map a field to a tracker header, e.g. deadline=Closes On")
    parser.add_argument("--out")
    parser.add_argument("--ics", help="also write an iCalendar file (new file) the user can import for reminders")
    args = parser.parse_args(argv)

    def run():
        overrides = {}
        for item in args.map:
            require("=" in item, "--map needs FIELD=Header")
            field, header = item.split("=", 1)
            require(field.strip() in FIELDS, "unknown --map field: " + field.strip())
            overrides[field.strip()] = header.strip().casefold()
        conventions, tz_name = None, args.timezone
        if args.context:
            import user_context
            try:
                value = user_context.load_context(args.context)
            except user_context.ContextError as exc:
                raise ToolError(str(exc)) from None
            conventions = user_context.monitoring(value)
            tz_name = tz_name or value["preferences"]["timezone"]
        result = plan(args.tracker, tz_name, args.as_of, conventions, overrides)
        if args.ics:
            skipped = []
            text, events = calendar(result, tz_name, skipped)
            with Path(args.ics).open("x", encoding="utf-8", newline="") as handle:
                handle.write(text)
            result["calendar"] = {"file": Path(args.ics).name, "events": events, "skipped": skipped,
                                  "note": "Import into your own calendar; nothing was scheduled or sent."}
        common.emit(result, args.out)
    return common.run_cli(run)


if __name__ == "__main__":
    raise SystemExit(main())
