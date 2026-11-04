#!/usr/bin/env python3
"""Offline, read-only intake and fail-closed application packet preparation.

Python 3.10+ standard library; .xlsx input optionally uses installed openpyxl.
Never fetches URLs, executes page content, edits trackers, or submits applications.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import stat
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZipFile, BadZipFile

VERSION = "0.3.0"
KINDS = {"resume", "cover_letter", "writing_sample", "portfolio", "other"}
EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_SOURCE = 10 * 1024 * 1024
MAX_DOCUMENT = 50 * 1024 * 1024
REPARSE_POINT = 0x400          # FILE_ATTRIBUTE_REPARSE_POINT
NAME_SURROGATE = 0x20000000    # reparse tags that redirect a name: symlinks, junctions, mount points


class PacketError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PacketError(message)


def now():
    return datetime.now(timezone.utc)


def timestamp(value):
    require(isinstance(value, str), "timestamp must be an ISO-8601 string with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PacketError("invalid ISO-8601 timestamp") from exc
    require(parsed.tzinfo is not None, "timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def iso(value=None):
    return (value or now()).isoformat().replace("+00:00", "Z")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def is_link(path):
    """True for a symlink or a Windows name-surrogate reparse point (junction/mount point).

    Cloud-sync placeholders and deduplicated files are reparse points too, but they
    are ordinary files, not redirections, so they are not treated as links.
    """
    info = Path(path).lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    if getattr(info, "st_file_attributes", 0) & REPARSE_POINT:
        tag = getattr(info, "st_reparse_tag", None)
        return tag is None or bool(tag & NAME_SURROGATE)
    return False


def link_chain(path, anchor=None):
    """The file plus any directories between it and a trusted anchor directory.

    Links above the anchor (operating-system aliases such as macOS /var, or a
    folder the user deliberately chose) are outside the helper's trust boundary.
    """
    p = Path(path)
    chain = [p]
    if anchor is not None:
        anchor = Path(anchor)
        chain += [x for x in p.parents if x != anchor and x.is_relative_to(anchor)]
    return chain


def read_bytes(path, limit=MAX_DOCUMENT, anchor=None):
    p = Path(path)
    require(p.is_file() and not any(is_link(x) for x in link_chain(p, anchor)),
            f"not a regular non-symlink file (links and junctions are refused): {p.name}")
    require(p.stat().st_size <= limit, f"file exceeds {limit} byte limit: {p.name}")
    data = p.read_bytes()
    require(len(data) <= limit, f"file exceeds {limit} byte limit")
    return data


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_json(path, anchor=None):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON object key")
            result[key] = value
        return result
    try:
        return json.loads(read_bytes(path, MAX_SOURCE, anchor).decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PacketError(f"invalid UTF-8 JSON: {Path(path).name}") from exc


def write_new(path, data):
    p = Path(path)
    with p.open("xb") as handle:
        handle.write(data)


def text_value(value, name):
    require(isinstance(value, str) and bool(value.strip()), f"{name} must be nonblank text")
    return value


def safe_name(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,119}", value),
            "filename/packet name must be a single safe ASCII basename (max 120 characters)")
    require(not value.endswith((".", " ")) and ".." not in value, "unsafe filename/packet name")
    require(value.split(".")[0].rstrip(" .").upper() not in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}, "reserved filename")
    return value


def normalized_employer(value):
    return " ".join(str(value or "").split()).casefold()


def normalized_url(value):
    text_value(value, "source URL")
    parts = urlsplit(value)
    require(parts.scheme.lower() in {"https", "http"} and parts.hostname and not parts.username and not parts.password,
            "source URL must be absolute HTTP(S), without credentials")
    require(not any(c.isspace() for c in value), "source URL contains whitespace")
    # Fragments can identify distinct jobs in hash-routed ATS pages. Preserve them,
    # queries, trailing slashes, path case, and presumed tracking keys.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, parts.fragment))


BLOCK_TAGS = {"p", "div", "li", "section", "article", "header", "footer", "main", "aside", "nav",
              "h1", "h2", "h3", "h4", "h5", "h6", "label", "tr", "ul", "ol", "dl", "dt", "dd",
              "table", "blockquote", "pre", "form", "fieldset", "legend", "figcaption"}


class PostingHTML(HTMLParser):
    """Observe static declarations only; never execute, navigate, or infer semantics."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = []
        self.labels = []
        self.active_label = None
        self.active_select = None
        self.active_option = None
        self.text = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "template"}:
            self.suppressed += 1
        if self.suppressed:
            return
        if tag == "br":
            self.text.append("\n")
        if tag == "label":
            self.active_label = {"for": attrs.get("for"), "text": [], "fields": []}
        if tag in {"input", "select", "textarea"}:
            kind = (attrs.get("type") or "text").casefold() if tag == "input" else tag
            if kind in {"hidden", "submit", "button", "reset", "image"}:
                return
            f = {"index": len(self.fields), "tag": tag, "type": kind,
                 "id": attrs.get("id"), "name": attrs.get("name"), "label": None,
                 "attributes": {k: v for k, v in attrs.items() if k in {
                     "required", "accept", "multiple", "maxlength", "minlength", "pattern",
                     "min", "max", "step", "disabled", "aria-required", "aria-label", "aria-describedby"}},
                 "raw_start_tag": self.get_starttag_text(), "options": []}
            self.fields.append(f)
            if self.active_label is not None:
                self.active_label["fields"].append(f["index"])
            if tag == "select":
                self.active_select = f
        if tag == "option" and self.active_select is not None:
            self.active_option = {"value": attrs.get("value"), "text": "", "disabled": "disabled" in attrs}
            self.active_select["options"].append(self.active_option)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"} and self.suppressed:
            self.suppressed -= 1
            return
        if self.suppressed:
            return
        if tag == "label" and self.active_label is not None:
            self.labels.append(self.active_label)
            self.active_label = None
        if tag == "select":
            self.active_select = self.active_option = None
        if tag == "option":
            self.active_option = None
        if tag in BLOCK_TAGS:
            self.text.append("\n")

    def handle_data(self, data):
        if self.suppressed:
            return
        self.text.append(data)
        if self.active_label is not None:
            self.active_label["text"].append(data)
        if self.active_option is not None:
            self.active_option["text"] += data

    def results(self):
        for f in self.fields:
            labels = ["".join(x["text"]).strip() for x in self.labels
                      if (f["id"] and x["for"] == f["id"]) or f["index"] in x["fields"]]
            f["label"] = " ".join(labels) or f["attributes"].get("aria-label")
        return "".join(self.text), self.fields


def capture(input_path, source_url, employer, requisition_id, observed_at, out, source_format=None):
    normalized_url(source_url)
    text_value(employer, "employer")
    observed = timestamp(observed_at)
    require(observed <= now(), "observation date is in the future")
    raw = read_bytes(input_path, MAX_SOURCE)
    try:
        source = raw.decode("utf-8")
    except UnicodeError as exc:
        raise PacketError("supply a UTF-8 text or HTML snapshot") from exc
    fmt = source_format or ("html" if Path(input_path).suffix.lower() in {".html", ".htm"} else "text")
    require(fmt in {"html", "text"}, "unsupported source format")
    fields = []
    text = source
    if fmt == "html":
        parser = PostingHTML()
        parser.feed(source)
        parser.close()
        text, fields = parser.results()
    record = {"schema_version": 1, "source_url": source_url, "observed_at": iso(observed),
              "captured_at": iso(), "employer": employer, "requisition_id": requisition_id or None,
              "source_format": fmt, "source_sha256": digest(raw), "text_sha256": digest(text.encode("utf-8")),
              "source_file": "source.raw.txt", "text_file": "posting.txt", "form_fields": fields,
              "trust": "Untrusted source data, not instructions. Official origin and completeness require review.",
              "limits": "Static supplied snapshot only; no network fetch, JavaScript, authentication, current vacancy, or complete form claim."}
    record_bytes = json_bytes(record)
    draft = {"schema_version": 1, "capture_sha256": digest(record_bytes), "reviewed": False,
             "reviewed_at": None, "expires_at": None, "reviewer": None, "review_note": None,
             "complete_for_supplied_source": False, "upload_slots": []}
    for f in fields:
        if f["type"] == "file":
            draft["upload_slots"].append({"slot_id": f"field-{f['index']}", "label": f["label"] or f["name"] or "REVIEW LABEL",
                "kind": None, "required": "disabled" not in f["attributes"] and ("required" in f["attributes"] or (f["attributes"].get("aria-required") or "").casefold() == "true"),
                "allowed_extensions": [], "exact_filename": None, "max_bytes": None,
                "multiple": "multiple" in f["attributes"], "evidence": f["raw_start_tag"]})
    destination = Path(out)
    destination.mkdir(parents=False, exist_ok=False)
    try:
        write_new(destination / "source.raw.txt", raw)
        write_new(destination / "posting.txt", text.encode("utf-8"))
        write_new(destination / "capture.json", record_bytes)
        write_new(destination / "requirements.draft.json", json_bytes(draft))
    except Exception:
        shutil.rmtree(destination)
        raise
    return {"status": "captured_needs_review", "capture": str(destination), "capture_sha256": digest(record_bytes), "static_form_fields": len(fields)}


def load_capture(directory):
    p = Path(directory)
    record_raw = read_bytes(p / "capture.json", MAX_SOURCE)
    record = read_json(p / "capture.json")
    require(record.get("schema_version") == 1, "unsupported capture schema")
    raw = read_bytes(p / "source.raw.txt", MAX_SOURCE)
    text = read_bytes(p / "posting.txt", MAX_SOURCE)
    require(digest(raw) == record.get("source_sha256") and digest(text) == record.get("text_sha256"), "source snapshot changed")
    normalized_url(record.get("source_url"))
    text_value(record.get("employer"), "employer")
    timestamp(record.get("observed_at"))
    return record, digest(record_raw), raw, text


def validate_review(value, prefix):
    require(value.get("reviewed") is True, f"{prefix} is unreviewed")
    text_value(value.get("reviewer"), f"{prefix} reviewer")
    text_value(value.get("review_note"), f"{prefix} review note")
    reviewed = timestamp(value.get("reviewed_at"))
    expiry = timestamp(value.get("expires_at"))
    require(reviewed <= now() < expiry and expiry > reviewed, f"{prefix} review expired or has invalid dates")


def load_requirements(path, capture_hash, raw, text, form_fields=None):
    req = read_json(path)
    require(req.get("schema_version") == 1 and req.get("capture_sha256") == capture_hash, "requirements belong to a different capture")
    validate_review(req, "requirements")
    require(req.get("complete_for_supplied_source") is True, "form requirements are not confirmed complete for supplied source")
    require(isinstance(req.get("upload_slots"), list) and req["upload_slots"], "at least one explicitly reviewed upload slot is required")
    seen = set()
    for slot in req["upload_slots"]:
        require(isinstance(slot, dict), "invalid upload slot")
        sid = text_value(slot.get("slot_id"), "slot ID")
        require(sid not in seen, "duplicate upload slot ID")
        seen.add(sid)
        text_value(slot.get("label"), "slot label")
        require(slot.get("kind") in KINDS, "attachment kind needs explicit review")
        require(type(slot.get("required")) is bool and type(slot.get("multiple", False)) is bool, "slot flags must be booleans")
        require(slot.get("multiple", False) is False, "multiple-file slots need separate reviewed single-file slots; not supported automatically")
        extensions = slot.get("allowed_extensions")
        require(isinstance(extensions, list) and extensions and all(x in EXTENSIONS for x in extensions), "review explicit allowed extensions (.pdf, .docx, .txt only)")
        if slot.get("exact_filename") is not None:
            safe_name(slot["exact_filename"])
            require(Path(slot["exact_filename"]).suffix.lower() in extensions, "required filename conflicts with allowed extensions")
        if slot.get("max_bytes") is not None:
            require(type(slot["max_bytes"]) is int and slot["max_bytes"] > 0, "max_bytes must be a positive integer or null")
        evidence = text_value(slot.get("evidence"), "exact source evidence")
        require(evidence in raw.decode("utf-8") or evidence in text.decode("utf-8"), "slot evidence is not an exact source span")
    slots = {s["slot_id"]: s for s in req["upload_slots"]}
    mime_extensions = {"application/pdf": ".pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx", "text/plain": ".txt"}
    for field in form_fields or []:
        if field["type"] != "file" or "disabled" in field["attributes"]:
            continue
        sid = f"field-{field['index']}"
        required = "required" in field["attributes"] or (field["attributes"].get("aria-required") or "").casefold() == "true"
        require(not required or (sid in slots and slots[sid]["required"]), "captured required upload field omitted or downgraded")
        if sid in slots:
            accept = field["attributes"].get("accept")
            if accept:
                tokens = [x.strip().casefold() for x in accept.split(",") if x.strip()]
                known = {mime_extensions.get(x, x) for x in tokens}
                # An unsupported token must not disable enforcement of the rest.
                # Unknown MIME/wildcard behavior stays blocked rather than guessed.
                require(set(slots[sid]["allowed_extensions"]) <= known, "reviewed extension contradicts captured accept constraint or accept is unresolved")
    return req, digest(read_bytes(path, MAX_SOURCE))


# Header aliases, tried tier by tier. Values within one tier must agree (a conflict
# blocks the tracker). A later tier is consulted only when every earlier tier is
# empty, so adding common real-world headers cannot change how an existing tracker
# that uses the original headers is read.
ALIAS_TIERS = {
    "employer": (("employer", "company"),
                 ("company name", "employer name", "organization", "organisation", "hiring organization")),
    "record_id": (("record id", "record_id"), ("tracker id", "tracker_id")),
    "requisition_id": (("requisition id", "requisition_id", "requisition", "req id"),
                       ("requisition number", "requisition #", "req #", "req no", "req number")),
}
# Secondary employer job identifiers: an equal value can match, but a different value
# is not treated as a requisition conflict (an ATS job ID and a requisition can differ).
ALT_ID_HEADERS = ("job id", "job_id", "job number", "posting id", "vacancy id", "job requisition id")
URL_HEADERS = ("application url", "source url", "source_url", "url", "job url", "job_url", "posting url",
               "job posting url", "job link", "link", "apply url", "apply link", "listing url")
ALIASES = {key: [name for tier in tiers for name in tier] for key, tiers in ALIAS_TIERS.items()}
ALIASES["urls"] = list(URL_HEADERS)
HYPERLINK = re.compile(r'^=\s*HYPERLINK\(\s*"((?:[^"]|"")*)"', re.I)


def normalized_id(value):
    """Requisition comparison ignores case and whitespace runs, never punctuation."""
    return " ".join(str(value).split()).casefold()


def cell_url(value):
    """A spreadsheet HYPERLINK formula stores its target as the first quoted argument."""
    text = str(value).strip()
    found = HYPERLINK.match(text)
    return found.group(1).replace('""', '"') if found else text


def normalized_row(row, location):
    pairs = [(str(k).strip().casefold(), v) for k, v in row.items() if k is not None and str(k).strip()]
    require(len({k for k, _ in pairs}) == len(pairs), "duplicate normalized tracker headers")
    mapped = dict(pairs)
    def present(names):
        return [str(mapped[k]).strip() for k in names if mapped.get(k) is not None and str(mapped[k]).strip()]
    def first(key):
        for tier in ALIAS_TIERS[key]:
            values = present(tier)
            distinct = {normalized_employer(x) if key == "employer" else normalized_id(x) if key == "requisition_id" else x
                        for x in values}
            require(len(distinct) <= 1, f"conflicting tracker aliases for {key}")
            if values:
                return values[0]
        return None
    return {"employer": first("employer"), "record_id": first("record_id"), "requisition_id": first("requisition_id"),
            "alt_ids": present(ALT_ID_HEADERS),
            "urls": [cell_url(x) for x in present(URL_HEADERS)], "location": location}


def tracker_rows(path):
    path = Path(path)
    before = digest(read_bytes(path))
    rows = []
    if path.suffix.lower() == ".json":
        data = read_json(path)
        data = data.get("records") if isinstance(data, dict) else data
        require(isinstance(data, list) and all(isinstance(r, dict) for r in data), "tracker JSON must be a list of record objects")
        rows = [normalized_row(r, {"row": i + 1}) for i, r in enumerate(data)]
    elif path.suffix.lower() in {".csv", ".tsv"}:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t" if path.suffix.lower() == ".tsv" else ",")
            require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), "tracker headers missing or duplicated")
            rows = [normalized_row(r, {"row": i + 2}) for i, r in enumerate(reader)]
    elif path.suffix.lower() == ".xlsx":
        try:
            import openpyxl
        except ImportError as exc:
            raise PacketError(".xlsx reading needs already-installed openpyxl; use a read-only CSV/JSON export instead") from exc
        try:
            workbook = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_links=False)
        except Exception as exc:  # openpyxl raises its own and zipfile errors for corrupt workbooks
            raise PacketError(".xlsx tracker could not be read; export it read-only to CSV/JSON") from exc
        try:
            for sheet in workbook:
                headers = None
                for i, values in enumerate(sheet.iter_rows(values_only=True), 1):
                    if headers is None:
                        if i > 25:
                            break
                        names = [str(x).strip().casefold() if x is not None else "" for x in values]
                        if any(x in names for x in ALIASES["employer"]) and any(x in names for x in ALIASES["record_id"]):
                            nonempty = [x for x in names if x]
                            require(len(set(nonempty)) == len(nonempty), "duplicate tracker headers")
                            headers = names
                        continue
                    if any(x is not None for x in values):
                        rows.append(normalized_row(dict(zip(headers, values)), {"sheet": sheet.title, "row": i}))
        finally:
            workbook.close()
    else:
        raise PacketError("tracker format must be JSON, CSV, TSV, or XLSX")
    require(digest(read_bytes(path)) == before, "tracker changed while reading; retry from current source")
    require(rows, "no tracker records found with supported headers")
    return rows, before


def match_record(capture_directory, tracker):
    record, capture_hash, _, _ = load_capture(capture_directory)
    rows, tracker_hash = tracker_rows(tracker)
    candidates = []
    target_req = normalized_id(record["requisition_id"]) if record.get("requisition_id") else None
    url = normalized_url(record["source_url"])
    for row in rows:
        if normalized_employer(row["employer"]) != normalized_employer(record["employer"]):
            continue
        req = normalized_id(row["requisition_id"]) if row["requisition_id"] else None
        # Explicit conflicting requisitions override URL similarity/reuse.
        if req and target_req and req != target_req:
            continue
        valid_urls = []
        for value in row["urls"]:
            try:
                valid_urls.append(normalized_url(value))
            except (PacketError, ValueError):
                pass
        ids = {req} if req else set()
        ids |= {normalized_id(x) for x in row["alt_ids"]}
        basis = "employer_and_requisition" if target_req and target_req in ids else (
            "employer_and_exact_url" if url in valid_urls else None)
        if basis:
            candidates.append({k: row[k] for k in ("record_id", "employer", "requisition_id", "location")} | {"basis": basis})
    status = "ambiguous" if len(candidates) > 1 else "matched" if len(candidates) == 1 and candidates[0]["record_id"] else "pending"
    return {"schema_version": 1, "status": status, "capture_sha256": capture_hash, "tracker_sha256": tracker_hash,
            "matched_at": iso(), "candidates": candidates, "tracker_mutated": False,
            "reason": "Exactly one explicit record identity" if status == "matched" else "No unique identified record; do not merge or create a row automatically"}


def validate_document(data, filename):
    safe_name(filename)
    extension = Path(filename).suffix.lower()
    require(extension in EXTENSIONS, "unsupported attachment extension")
    require(bool(data), "attachment is empty")
    if extension == ".pdf":
        require(data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:], "file is not a recognizable PDF")
    elif extension == ".docx":
        from io import BytesIO
        try:
            with ZipFile(BytesIO(data)) as archive:
                require("word/document.xml" in archive.namelist() and "[Content_Types].xml" in archive.namelist(), "file is not a recognizable DOCX")
        except BadZipFile as exc:
            raise PacketError("file is not a recognizable DOCX") from exc
    else:
        try:
            data.decode("utf-8")
        except UnicodeError as exc:
            raise PacketError("text attachment must be UTF-8") from exc
        require(b"\0" not in data, "text attachment contains NUL bytes")


def review_document(file, kind, filename, capture_directory, requirements, reviewer, review_note, expires_at, confirmed):
    require(confirmed is True, "review-document requires --confirm-reviewed after actual content and layout review")
    require(kind in KINDS, "unsupported document kind")
    record, capture_hash, raw, text = load_capture(capture_directory)
    _, req_hash = load_requirements(requirements, capture_hash, raw, text, record["form_fields"])
    data = read_bytes(file)
    require(Path(file).suffix.lower() == Path(filename).suffix.lower(), "renaming cannot convert document format")
    validate_document(data, filename)
    attestation = {"schema_version": 1, "reviewed": True, "reviewed_at": iso(), "expires_at": expires_at,
                   "reviewer": reviewer, "review_note": review_note, "kind": kind, "filename": filename,
                   "sha256": digest(data), "size_bytes": len(data), "capture_sha256": capture_hash,
                   "requirements_sha256": req_hash,
                   "limits": "Recorded reviewer attestation, not independent factual, editorial, or visual certification."}
    validate_review(attestation, "document")
    return attestation


def check_attachments(plan, req, req_hash, capture_hash, loader):
    require(isinstance(plan, list), "documents plan must be a list")
    slots = {s["slot_id"]: s for s in req["upload_slots"]}
    used, names, verified = set(), set(), []
    for item in plan:
        require(isinstance(item, dict), "invalid document plan entry")
        sid = item.get("slot_id")
        require(sid in slots and sid not in used, "unknown or duplicate upload slot")
        used.add(sid)
        slot = slots[sid]
        data, attestation = loader(item)
        require(isinstance(attestation, dict) and attestation.get("schema_version") == 1, "invalid document review")
        validate_review(attestation, "document")
        require(attestation.get("capture_sha256") == capture_hash and attestation.get("requirements_sha256") == req_hash, "document review is stale for this capture or requirements")
        require(attestation.get("sha256") == digest(data) and attestation.get("size_bytes") == len(data), "document bytes changed after review")
        require(attestation.get("kind") == slot["kind"], f"wrong attachment kind for slot {sid}: expected {slot['kind']}")
        name = safe_name(item.get("filename"))
        require(name == attestation.get("filename"), "filename differs from reviewed output filename")
        require(name.casefold() not in names, "duplicate case-insensitive attachment filename")
        names.add(name.casefold())
        require(slot.get("exact_filename") is None or name == slot["exact_filename"], "filename does not exactly match form requirement")
        require(Path(name).suffix.lower() in slot["allowed_extensions"], "attachment format is not accepted by upload slot")
        require(slot.get("max_bytes") is None or len(data) <= slot["max_bytes"], "attachment exceeds upload slot byte limit")
        validate_document(data, name)
        verified.append((item, data, attestation))
    require(all(not s["required"] or sid in used for sid, s in slots.items()), "required upload slot is missing")
    return verified


def assemble(capture_directory, requirements, tracker, documents, out_root, packet_name):
    packet_name = safe_name(packet_name)
    record, capture_hash, raw, text = load_capture(capture_directory)
    req, req_hash = load_requirements(requirements, capture_hash, raw, text, record["form_fields"])
    match = match_record(capture_directory, tracker)
    require(match["status"] == "matched", f"tracker identity is {match['status']}; packet blocked")
    plan = read_json(documents)
    plan_dir = Path(documents).resolve().parent
    def loader(item):
        require(isinstance(item.get("file"), str) and isinstance(item.get("review"), str),
                "each documents plan entry needs file and review paths")
        # Links inside the plan's own directory tree are refused; the plan cannot redirect inputs.
        return (read_bytes(plan_dir / item["file"], anchor=plan_dir),
                read_json(plan_dir / item["review"], anchor=plan_dir))
    verified = check_attachments(plan, req, req_hash, capture_hash, loader)
    root = Path(out_root)
    require(root.is_dir() and not is_link(root), "output root must be an existing non-symlink directory")
    destination = root / packet_name
    destination.mkdir(exist_ok=False)
    try:
        (destination / "source").mkdir()
        (destination / "attachments").mkdir()
        (destination / "reviews").mkdir()
        files = {"source/source.raw.txt": raw, "source/posting.txt": text,
                 "source/capture.json": read_bytes(Path(capture_directory) / "capture.json", MAX_SOURCE),
                 "requirements.json": read_bytes(requirements, MAX_SOURCE), "tracker-match.json": json_bytes(match)}
        packed_plan = []
        for index, (item, data, attestation) in enumerate(verified):
            file = f"attachments/{item['filename']}"
            review = f"reviews/{index + 1}.json"
            files[file], files[review] = data, json_bytes(attestation)
            packed_plan.append({"slot_id": item["slot_id"], "filename": item["filename"], "file": file, "review": review})
        for relative, data in files.items():
            write_new(destination / relative, data)
        manifest = {"schema_version": 1, "tool_version": VERSION, "packet_name": packet_name, "created_at": iso(),
                    "status": "prepared_not_submitted", "employer": record["employer"], "requisition_id": record["requisition_id"],
                    "source_url": record["source_url"], "observed_at": record["observed_at"],
                    "tracker_record": match["candidates"][0], "tracker_sha256": match["tracker_sha256"],
                    "documents": packed_plan,
                    "files": {p: {"sha256": digest(d), "size_bytes": len(d)} for p, d in files.items()},
                    "limits": "Local packet only. No upload, submission, tracker edit, browser interaction, source-authenticity verification, or independent editorial/layout review."}
        write_new(destination / "manifest.json", json_bytes(manifest))
        validate_packet(destination)
    except Exception:
        shutil.rmtree(destination)
        raise
    return {"status": "prepared_not_submitted", "packet": str(destination), "attachments": len(verified), "tracker_record_id": match["candidates"][0]["record_id"]}


def contained_file(root, relative):
    require(isinstance(relative, str) and "\\" not in relative, "invalid packet-relative path")
    p = Path(relative)
    require(not p.is_absolute() and all(x not in {"..", "."} for x in p.parts), "unsafe packet-relative path")
    candidate = root / p
    require(candidate.resolve().is_relative_to(root.resolve()), "packet path escapes root")
    # Every component inside the packet, plus the packet root, must be a real entry.
    require(not any(is_link(x) for x in [root, *link_chain(candidate, root)]), "packet contains a symlink")
    return candidate


def validate_packet(packet):
    root = Path(packet)
    require(root.is_dir() and not is_link(root), "not a packet directory")
    manifest = read_json(root / "manifest.json")
    require(manifest.get("schema_version") == 1 and manifest.get("status") == "prepared_not_submitted", "invalid packet manifest")
    expected = manifest.get("files")
    require(isinstance(expected, dict), "manifest file hashes missing")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    require(actual == set(expected) | {"manifest.json"}, "packet has missing or unexpected files")
    for relative, properties in expected.items():
        data = read_bytes(contained_file(root, relative))
        require(properties == {"sha256": digest(data), "size_bytes": len(data)}, f"packet artifact changed: {relative}")
    record, capture_hash, raw, text = load_capture(root / "source")
    req, req_hash = load_requirements(root / "requirements.json", capture_hash, raw, text, record["form_fields"])
    match = read_json(root / "tracker-match.json")
    require(match.get("status") == "matched" and match.get("capture_sha256") == capture_hash and len(match.get("candidates", [])) == 1, "packet tracker match is invalid")
    require(manifest.get("tracker_record") == match["candidates"][0] and manifest.get("tracker_sha256") == match.get("tracker_sha256"), "manifest tracker identity differs")
    for key in ("employer", "requisition_id", "source_url", "observed_at"):
        require(manifest.get(key) == record[key], "manifest source identity differs")
    def loader(item):
        require(item.get("file") == "attachments/" + safe_name(item.get("filename")), "attachment path must match exact filename")
        return read_bytes(contained_file(root, item["file"])), read_json(contained_file(root, item["review"]))
    checked = check_attachments(manifest.get("documents"), req, req_hash, capture_hash, loader)
    return {"status": "valid_prepared_packet_not_submitted", "attachments": len(checked),
            "limits": "Validates local bytes and recorded reviews; tracker/live form currentness and actual reviewer judgment are not independently reverified."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("capture", help="capture supplied UTF-8 text/HTML; no network")
    for name in ("input", "url", "employer", "observed-at", "out"):
        c.add_argument("--" + name, required=True)
    c.add_argument("--requisition-id")
    c.add_argument("--format", choices=["text", "html"])
    m = commands.add_parser("match", help="read-only deterministic tracker match")
    m.add_argument("--capture", required=True)
    m.add_argument("--tracker", required=True)
    m.add_argument("--out")
    r = commands.add_parser("review-document", help="record actual review of exact bytes, kind and output filename")
    for name in ("file", "kind", "filename", "capture", "requirements", "reviewer", "review-note", "expires-at", "out"):
        r.add_argument("--" + name, required=True)
    r.add_argument("--confirm-reviewed", action="store_true")
    a = commands.add_parser("assemble", help="assemble into a new directory; never overwrite")
    for name in ("capture", "requirements", "tracker", "documents", "out-root", "packet-name"):
        a.add_argument("--" + name, required=True)
    v = commands.add_parser("validate", help="recheck packet bytes and review expiration")
    v.add_argument("--packet", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            result = capture(args.input, args.url, args.employer, args.requisition_id, args.observed_at, args.out, args.format)
        elif args.command == "match":
            result = match_record(args.capture, args.tracker)
            if args.out:
                write_new(args.out, json_bytes(result))
        elif args.command == "review-document":
            result = review_document(args.file, args.kind, args.filename, args.capture, args.requirements,
                                     args.reviewer, args.review_note, args.expires_at, args.confirm_reviewed)
            write_new(args.out, json_bytes(result))
        elif args.command == "assemble":
            result = assemble(args.capture, args.requirements, args.tracker, args.documents, args.out_root, args.packet_name)
        else:
            result = validate_packet(args.packet)
        utf8_out(sys.stdout, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0
    except (PacketError, OSError, ValueError, TypeError, KeyError, AttributeError, csv.Error, BadZipFile,
            EOFError, RecursionError) as exc:
        utf8_out(sys.stderr, json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False) + "\n")
        return 2


def utf8_out(stream, text):
    """Emit UTF-8 whatever the console code page is (Windows pipes default to cp1252)."""
    raw = getattr(stream, "buffer", None)
    if raw is None:
        stream.write(text)
        return
    stream.flush()
    raw.write(text.encode("utf-8"))
    raw.flush()


if __name__ == "__main__":
    sys.exit(main())
