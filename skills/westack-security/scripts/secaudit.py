"""westack-security audit record checker: validate a findings record, render the report from it, take a scope
receipt of the audited tree, and scrub secrets from a receipt, note or brief before it is written.

  python secaudit.py check FINDINGS ROOT
  python secaudit.py report FINDINGS [--root ROOT] [--out FILE]
  python secaudit.py scope ROOT [--tracked FILE] [--exclude GLOB ...]
  python secaudit.py redact FILE [--out FILE]
  python secaudit.py suppressions ROOT

FINDINGS is JSON: {"format": "westack-security-findings-1", "mode", "scope", "records": [...]}. Each record has an
"id", a "state" and a one-sentence "claim", plus an identity ("rule", a root-control "anchor" with no line number,
and an "instance" key per independently attackable sibling). The states and the fields each one needs:

  confirmed       surface and reach (the class step); the boundary tuple: principal, source, control, sink, path,
                  boundary, resource, result, counterevidence, proof_gaps; impact, demonstrated_impact, likelihood
                  and the severity the table gives them; snippets labelled by role that equal the cited lines
  hardening       a real weakness with no crossed boundary: no severity
  needs-review    missing_fact: the smallest fact that would settle it
  not-assessed    settle: what would settle it (an abstention, never clean)
  not-actionable  positive_evidence: what holds on every shipped path and supported configuration
  not-applicable  the class that removes it: a surface other than shipped, or a self-only or privileged-only reach
  rejected        reason: kept so a later run does not raise the same claim again unchanged
  dismissed       a carried dismissal: a reason that is not a bare label and a basis snippet that still matches

Any record may also carry a "risk" label, {"level", "checks": [{"name", "level"}]}: high, medium, low or unknown,
combined from its independent checks by the worst concrete level (a check that raised counts as high; all unknown stays
unknown; unknown asks, so only needs-review or not-assessed may carry it). A removal claim carries "absence":
{"identifiers", "copies": [{"copy", "probe", "result"}], "secret", "rotated"}: every listed copy probed for an exact
pre-change identifier and found absent, and an exposed secret rotated.

"scope" may list "secret_scans", one receipt per run of a secret scanner: {"tool", "version", "command", "config",
"scope": "dir" or "git", "exit", "log", "result"}. The result must be what the exit code and the log say together
(gitleaks and Betterleaks exit 1 for findings and for a failed or partial scan, so the command passes --exit-code 2);
the command redacts and never validates live (TruffleHog, Kingfisher and detect-secrets validate unless given their off
switch); a gitleaks or Betterleaks command passes --config and --ignore-gitleaks-allow, so the scanned project does not
configure its own scan; the working tree and the history are both scanned or the audit is partial, and a history
receipt records "shallow" and the "refs" scanned (a shallow clone leaves the history partial); and an allow-list entry
in the recorded config that is a literal high-entropy value needs a record anchored at it ("<config>::<entry>"). With a
secret scan recorded, each scanner file and inline allow comment the project itself holds under ROOT needs a record
anchored at it ("<path>", or "<path>::<marker>" for a comment): scope to review, never settled.

`suppressions` lists those: the scanner configs, ignore files and baselines found under ROOT by name, and the inline
allow comments by marker, with path and line and never the line's text. Exit 0 when there are none, 1 when it lists
any, 2 when ROOT or a file cannot be read and nothing was listed.

`redact` reads JSON or key=value / name: value text and prints the scrubbed copy: auth headers keep their scheme,
cookies their names, and values under secret-named keys, matched by whole name parts, become <redacted> (numbers
too). Exit 0 when nothing needed scrubbing, 1 when something did, 2 when FILE cannot be read.

`check` exits 0 clean, 1 with problems, 2 when FINDINGS or ROOT cannot be read. `report` renders Markdown from a
record that passes the same checks (snippets are checked only with --root) and refuses (exit 1) one that does not; with
--out it writes the file whole each time, so a hand edit never survives a regeneration. `scope` hashes every file under
ROOT except .git and the --exclude patterns, so staged and untracked files are in the digest; --tracked takes saved
`git ls-files -z` output to list untracked files apart. Exit 2 when ROOT cannot be read; 64 for usage errors.

Standard library only. It reads files and prints JSON; it runs nothing, opens no network connection and never runs
git. The only file it writes is the one named by --out.
"""
import argparse
import collections
import fnmatch
import hashlib
import json
import math
import os
import pathlib
import re
import sys

try:
    import tomllib
except ImportError:  # Python before 3.11: scanner configs are then reported unreadable, never passed
    tomllib = None

FORMAT = "westack-security-secaudit-1"
RECORD_FORMAT = "westack-security-findings-1"
MODES = ("audit", "intake", "host", "triage", "fix")
STATES = ("confirmed", "hardening", "needs-review", "not-assessed", "not-actionable", "not-applicable", "rejected",
          "dismissed")
IMPACT = ("severe", "high", "moderate", "low", "minimal")
LIKELIHOOD = ("demonstrated", "likely", "possible", "unlikely", "unknown")
SEVERITY = ("critical", "high", "medium", "low")
# Severity is read from this table and never argued afterwards: rows are impact, columns follow LIKELIHOOD.
TABLE = {
    "severe":   ("critical", "critical", "high", "medium", "medium"),
    "high":     ("high", "high", "medium", "low", "low"),
    "moderate": ("medium", "medium", "medium", "low", "low"),
    "low":      ("low", "low", "low", "low", "low"),
    "minimal":  ("low", "low", "low", "low", "low"),
}
CRITICAL_EVIDENCE = ("remote-code-execution", "authentication-bypass", "cross-tenant-access", "credential-theft",
                     "bulk-data-loss")
SURFACES = ("shipped", "test-fixture", "example", "dev-only")
REACH = ("other-users", "self-only", "privileged-only")
CONFIDENCE = ("low", "medium", "high")
ROLES = ("input", "entrypoint", "root-control", "sink", "outcome", "expected-control")
HARNESS_EFFECTS = ("credential-released", "approval-skipped", "decision-skipped", "tool-call-outside-grant",
                   "data-sent")
TUPLE = ("principal", "source", "control", "sink", "path", "boundary", "resource", "result", "counterevidence", "proof_gaps")
COVERAGE = ("complete", "partial", "not-run")
RISK = ("high", "medium", "low", "unknown")
RISK_CHECK = RISK + ("error",)  # "error": the check raised instead of answering
RANK_RISK = {"low": 0, "medium": 1, "high": 2}  # unknown has no rank: it is never ordered against the others
ASKING = ("needs-review", "not-assessed")  # the states that put a question to the user
PROBE_RESULTS = ("absent", "present", "not-run")
SCAN_SCOPES = ("dir", "git")
SCAN_RESULTS = ("findings", "clean", "not-run")
SECRET_SCANNERS = re.compile(r"(?i)\b(?:betterleaks|gitleaks)\b")
# The summary lines gitleaks 8 and Betterleaks log, and the partial-scan wording Betterleaks uses (cmd/root.go:593-608
# as the 2026-10-30 security brief cites it); not re-read from source for this change.
COMPLETION = re.compile(r"(?i)\bno leaks found\b|\bleaks found:\s*\d+")
FOUND = re.compile(r"(?i)(?<!no )\bleaks found:\s*[1-9]")
PARTIAL = re.compile(r"(?i)\bpartial scan\b")
EXIT_TWO = re.compile(r"--exit-code[= ]2(?!\d)")
REDACT_FLAG = re.compile(r"--redact(?:=(\d+))?(?![\w-])")
# SC-38: without --config, Betterleaks 1.9.0 and gitleaks 8.30.1 load the scanned folder's own config, and they honour
# inline allow comments unless told not to (Betterleaks cmd/root.go:38-44, :93; gitleaks cmd/root.go:35-41, :85).
CONFIG_FLAG = re.compile(r"(?<!\S)(?:--config|-c)(?:=|\s+)\S")
INLINE_OFF = re.compile(r"(?<!\S)--ignore-gitleaks-allow(?:=true)?(?!\S)")
# SC-35 amended: these validate found credentials against their services unless given the off switch.
DEFAULT_VALIDATION = {"trufflehog": re.compile(r"(?<!\S)--no-verification(?!\S)"),
                      "kingfisher": re.compile(r"(?<!\S)--no-validate(?!\S)"),
                      "detect-secrets": re.compile(r"(?<!\S)(?:-n|--no-verify)(?!\S)")}
# Files a scanner reads from the project it scans (name, tools, kind, when the tool reads it), as checked at the pins in
# provenance/donors.json; and the inline comments that hide a finding.
TARGET_FILES = (
    (re.compile(r"\.betterleaks\.toml"), "betterleaks", "config", "loaded from the scanned folder unless --config is passed"),
    (re.compile(r"\.gitleaks\.toml"), "betterleaks, gitleaks", "config",
     "loaded from the scanned folder unless --config is passed"),
    (re.compile(r"\.betterleaksignore"), "betterleaks", "ignore", "always loaded from the scanned folder; no flag stops it"),
    (re.compile(r"\.gitleaksignore"), "betterleaks, gitleaks", "ignore",
     "always loaded from the scanned folder; no flag stops it"),
    (re.compile(r"kingfisher\.yaml"), "kingfisher", "config", "loaded only when passed with --config"),
    (re.compile(r"\.secrets\.baseline"), "detect-secrets", "baseline", "read when passed with --baseline"),
    (re.compile(r"\.secretlintignore"), "secretlint", "ignore", "read by default"),
    (re.compile(r"\.secretlintrc(?:\.\w+)?"), "secretlint", "config", "read by default"),
)
MARKERS = (
    (re.compile(rb"(?i)(?:gitleaks|betterleaks):allow"), "betterleaks, gitleaks", "honoured unless --ignore-gitleaks-allow"),
    (re.compile(rb"(?i)trufflehog:ignore"), "trufflehog", "honoured unless --no-ignore-tag"),
    (re.compile(rb"(?i)pragma:[ \t]*allowlist(?:[ \t]+nextline)?[ \t]+secret"), "detect-secrets", "always honoured"),
    (re.compile(rb"(?i)secretlint-disable"), "secretlint", "honoured when its filter-comments rule is configured"),
)
MARKER_CHUNK = 1 << 20
MARKER_OVERLAP = 256  # longer than any marker, so one split across two reads is still seen whole
MARKERS_SHOWN = 500
ALLOWLIST_KEYS = ("regex", "regexes", "stopwords")
REDACTED = "<redacted>"
# Whole name parts that mark a secret-bearing key; "author" and "keyboard" are parts of their own and keep their values.
SECRET_PARTS = {"password", "passwd", "pwd", "passphrase", "secret", "secrets", "token", "tokens", "key", "keys",
                "apikey", "auth", "credential", "credentials", "creds", "private", "privatekey", "signature", "session",
                "sessionid", "sid", "jwt", "bearer", "otp", "accesstoken", "authtoken", "secretkey", "clientsecret"}
NAME_PARTS = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
AUTH_HEADER = re.compile(r"(?i)\b((?:proxy-)?authorization[\"']?\s*[:=]\s*[\"']?)([A-Za-z][\w-]*[ \t]+)?([^\r\n\"']+)")
COOKIE_HEADER = re.compile(r"(?i)\b(set-cookie|cookie)([\"']?\s*[:=]\s*[\"']?)([^\r\n\"']*)")
HEADER_LINE = re.compile(r"(?m)^([ \t]*[\"']?)([A-Za-z_][\w.-]*)([\"']?[ \t]*:[ \t]*)(\S[^\r\n]*)")
PAIR = re.compile(r"(?<![\w.])([A-Za-z_][\w.-]*)([ \t]*=[ \t]*)(\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s&;,\"']+)")
SPECIAL_HEADERS = ("authorization", "proxy-authorization", "cookie", "set-cookie")
MAX_DEPTH = 64
LINE_IN_ANCHOR = re.compile(r":\d+\b|#L\d+|\bline\s*\d+", re.I)
BARE_LABELS = {"false positive", "fp", "not an issue", "not a bug", "wont fix", "won't fix", "wontfix", "by design",
               "ignore", "ignored", "n/a", "na", "accepted", "noise"}
MAX_READ = 5 * 1024 * 1024
RANK_SEVERITY = {v: i for i, v in enumerate(SEVERITY)}
RANK_LIKELIHOOD = {v: i for i, v in enumerate(LIKELIHOOD)}
RANK_IMPACT = {v: i for i, v in enumerate(reversed(IMPACT))}  # minimal 0 ... severe 4

CHECK_CLAIM = ("checks the record's shape, the severity table, the admission tuple, identities, dismissal bases, risk "
               "labels against their checks, absence probes, secret-scan receipts, that each scanner file and allow "
               "comment the project holds has a record, and that each snippet equals its cited lines under ROOT; it does "
               "not show that a finding is real, that the audit read what it lists, that the listed copies are every copy, "
               "that a scan receipt came from a real run, that a reviewed config was reviewed, or that a record with no "
               "findings means a secure system")
SUPPRESSIONS_CLAIM = ("lists the scanner configs, ignore files and baselines under ROOT by the names in its table, and inline "
                      "allow comments by their markers, with path and line and never the line's text; it runs no scanner "
                      "and does not show which of them a given run read, nor a suppression under another name, in an "
                      "environment variable, on a command line or behind a symbolic link")
REDACT_CLAIM = ("removes auth header credentials (keeping the scheme), cookie values (keeping the names) and values under "
                "secret-named keys, matched by whole name parts, in JSON and in key=value or name: value text; it does not "
                "show the output holds no secret: one under an ordinary name, in free prose or in another format passes "
                "through")
REPORT_CLAIM = ("rendered by code from a record that passed the checks; the report is a projection of the record, so "
                "it is no stronger than the record and never says the system is secure")
SCOPE_CLAIM = ("a digest of the bytes under ROOT now, staged and untracked files included, less the excluded patterns; "
               "it does not show which files the audit read, and the revision is read from .git files without "
               "checking that the tree is clean")


class RecordError(ValueError):
    """The input cannot be read as a findings record."""


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _nonempty(value):
    if isinstance(value, list):
        return any(_text(v) for v in value)
    return _text(value)


def _bare(reason):
    words = re.sub(r"[^a-z/' ]+", " ", str(reason or "").lower()).strip()
    return not words or " ".join(words.split()) in BARE_LABELS


def _lines(spec):
    """(start, end), 1-based and inclusive, from [a, b], "a-b" or a single number; None when unusable."""
    if isinstance(spec, bool):
        return None
    if isinstance(spec, int):
        spec = [spec, spec]
    if isinstance(spec, str):
        match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", spec)
        spec = [int(match[1]), int(match[2] or match[1])] if match else None
    if (isinstance(spec, list) and len(spec) == 2 and all(isinstance(n, int) and not isinstance(n, bool) for n in spec)
            and 1 <= spec[0] <= spec[1]):
        return spec[0], spec[1]
    return None


def _inside(root, relative):
    """The file a snippet names, if it is a relative path that stays inside ROOT and is no link; else None."""
    if not _text(relative) or relative.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", relative):
        return None
    parts = re.split(r"[\\/]+", relative)
    if ".." in parts:
        return None
    path = pathlib.Path(root, *parts)
    probe = pathlib.Path(root)
    for part in parts:
        probe = probe / part
        if probe.is_symlink():
            return None
    try:
        if not path.resolve().is_relative_to(pathlib.Path(root).resolve()):
            return None
    except OSError:
        return None
    return path


def _snippet_problem(root, snip):
    """None when the snippet's text equals its cited lines under ROOT, else (code, detail)."""
    span = _lines(snip.get("lines"))
    if span is None or not isinstance(snip.get("text"), str):
        return "snippet-malformed", "needs file, lines [start, end] and text"
    path = _inside(root, snip.get("file"))
    if path is None:
        return "snippet-outside-root", str(snip.get("file"))
    try:
        if path.stat().st_size > MAX_READ:
            return "snippet-unreadable", "larger than the read cap"
        source = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return "snippet-unreadable", str(exc)
    cited = source.replace("\r\n", "\n").split("\n")
    lines_text = "\n".join(cited[span[0] - 1:span[1]])
    expected = snip["text"].replace("\r\n", "\n").rstrip("\n")
    if span[1] > len(cited):
        return "snippet-mismatch", "the file has %d lines" % len(cited)
    if lines_text != expected:
        return "snippet-mismatch", "%s:%d-%d differs from the quoted text" % (snip.get("file"), span[0], span[1])
    return None


def load_record(raw):
    """The findings record from raw bytes (UTF-8 or UTF-16 with a byte-order mark)."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig")
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("format") != RECORD_FORMAT or not isinstance(data.get("records"), list):
        raise RecordError("not a " + RECORD_FORMAT + " record with a records list")
    return data


def _confirmed_problems(rec, root, add):
    surface, reach = rec.get("surface"), rec.get("reach")
    if surface not in SURFACES or reach not in REACH:
        add("bad-class", "surface must be one of %s and reach one of %s" % (", ".join(SURFACES), ", ".join(REACH)))
    if surface != "shipped":
        add("class-not-reportable", "surface %s: file it as not-applicable citing the class" % surface)
    if reach in ("self-only", "privileged-only") and rec.get("gains_privilege") is not True:
        add("reach-drops-out", "a %s path that gains no privilege is not reported" % reach)
    for field in TUPLE:
        if not _nonempty(rec.get(field)):
            add("tuple-missing", field)
    impact, shown, likelihood, severity = (rec.get("impact"), rec.get("demonstrated_impact"), rec.get("likelihood"),
                                           rec.get("severity"))
    if impact not in IMPACT or shown not in IMPACT or likelihood not in LIKELIHOOD or severity not in SEVERITY:
        add("bad-severity-fields", "impact and demonstrated_impact in %s, likelihood in %s, severity in %s"
            % ("/".join(IMPACT), "/".join(LIKELIHOOD), "/".join(SEVERITY)))
    else:
        if severity != TABLE[impact][LIKELIHOOD.index(likelihood)]:
            add("severity-off-table", "%s impact and %s likelihood give %s, not %s"
                % (impact, likelihood, TABLE[impact][LIKELIHOOD.index(likelihood)], severity))
        if RANK_IMPACT[impact] > RANK_IMPACT[shown]:
            add("impact-over-demonstrated", "impact %s exceeds the demonstrated %s" % (impact, shown))
    if severity == "critical" and rec.get("critical_evidence") not in CRITICAL_EVIDENCE:
        add("critical-unsupported", "critical needs critical_evidence, one of " + ", ".join(CRITICAL_EVIDENCE))
    if "confidence" in rec and rec["confidence"] not in CONFIDENCE:
        add("bad-confidence", "confidence is one of " + ", ".join(CONFIDENCE) + " and never sets severity")
    rule = str(rec.get("rule") or "")
    if rule.startswith("prompt-injection") and rec.get("harness_effect") not in HARNESS_EFFECTS:
        add("injection-prose-only", "name what the harness let through (" + ", ".join(HARNESS_EFFECTS)
            + "); text that only changes model prose is a hardening note")
    snippets = rec.get("snippets")
    if not isinstance(snippets, list) or not snippets:
        add("snippets-missing", "a confirmed finding quotes its lines by role")
        return
    for snip in snippets:
        if not isinstance(snip, dict) or snip.get("role") not in ROLES:
            add("snippet-malformed", "role must be one of " + ", ".join(ROLES))
            continue
        if root is not None:
            problem = _snippet_problem(root, snip)
            if problem:
                add(*problem)


REPRO_LABELS = ("static", "reproduced", "repair-tested")
REPAIR_RESULTS = ("fixed", "not-fixed")
MAX_REPAIRS = 3
SHA256 = re.compile(r"[0-9a-f]{64}")


def _run_receipt_missing(run):
    """The fields a container run lacks: image, image_id, command, exit (an integer), log_sha256 (64 hex), network."""
    run = run if isinstance(run, dict) else {}
    missing = [k for k in ("image", "image_id", "command", "network") if not _text(run.get(k))]
    if not isinstance(run.get("exit"), int) or isinstance(run.get("exit"), bool):
        missing.append("exit")
    if not SHA256.fullmatch(str(run.get("log_sha256", ""))):
        missing.append("log_sha256")
    return missing


def _reproduction_problems(rep, add):
    """A label is never more than its evidence: reproduced needs a container receipt and an observation;
    repair-tested also needs one to three repair candidates, each tried in its own container run on a scratch copy."""
    if not isinstance(rep, dict) or rep.get("label") not in REPRO_LABELS:
        add("bad-reproduction", "reproduction.label is one of " + ", ".join(REPRO_LABELS))
        return
    if rep["label"] == "static":
        return
    budget = rep.get("budget") if isinstance(rep.get("budget"), dict) else {}
    if not (isinstance(budget.get("minutes"), (int, float)) and budget["minutes"] > 0
            and isinstance(budget.get("workers"), int) and budget["workers"] > 0):
        add("reproduction-unbudgeted", "a container reproduction states its minutes and workers")
    missing = _run_receipt_missing(rep.get("container"))
    if missing:
        add("reproduced-without-container", "a %s label needs the container receipt: %s" % (rep["label"], ", ".join(missing)))
    elif rep["container"].get("network") != "none" and not _text(rep.get("network_grant")):
        add("reproduction-network-ungranted", "a container with network %s needs network_grant"
            % rep["container"].get("network"))
    if not _text(rep.get("observed")):
        add("reproduced-without-observation", "say what the run showed, against the finding's claim")
    if rep["label"] != "repair-tested":
        return
    repairs = rep.get("repairs")
    if not isinstance(repairs, list) or not repairs:
        add("repair-tested-without-repairs", "repair-tested names each candidate and its run")
        return
    if len(repairs) > MAX_REPAIRS:
        add("too-many-repairs", "at most %d repair candidates per finding" % MAX_REPAIRS)
    for r in repairs:
        r = r if isinstance(r, dict) else {}
        if not _text(r.get("candidate")) or not SHA256.fullmatch(str(r.get("patch_sha256", ""))) \
                or r.get("result") not in REPAIR_RESULTS or r.get("scratch_copy") is not True:
            add("repair-malformed", "each repair has candidate, patch_sha256, result (fixed or not-fixed) and "
                                    "scratch_copy true (never the user's tree)")
        elif _run_receipt_missing(r.get("run")):
            add("repair-untested", "%s needs its own container run receipt: %s"
                % (r["candidate"], ", ".join(_run_receipt_missing(r.get("run")))))


def combine_risk(levels):
    """Independent checks combined: the worst concrete level, a check that raised counting as high; all unknown stays
    unknown, because "could not assess" is never ranked against low or anything else."""
    concrete = ["high" if level == "error" else level for level in levels if level != "unknown"]
    if not concrete:
        return "unknown"
    return max(concrete, key=RANK_RISK.get)


def _risk_problems(rec, state, add):
    risk = rec.get("risk")
    checks = risk.get("checks") if isinstance(risk, dict) else None
    well_formed = (isinstance(risk, dict) and risk.get("level") in RISK and isinstance(checks, list) and bool(checks)
                   and all(isinstance(c, dict) and _text(c.get("name")) and c.get("level") in RISK_CHECK for c in checks))
    if not well_formed:
        add("risk-malformed", "level is one of %s, from named checks each %s" % (", ".join(RISK), ", ".join(RISK_CHECK)))
        return
    combined = combine_risk([c["level"] for c in checks])
    if risk["level"] != combined:
        add("risk-off-combination", "the checks give %s, not %s" % (combined, risk["level"]))
    if risk["level"] == "unknown" and state not in ASKING:
        add("risk-unknown-unasked", "unknown asks: file it as needs-review or not-assessed, never %s" % state)


def _absence_problems(absence, add):
    copies = absence.get("copies") if isinstance(absence, dict) else None
    shaped = (isinstance(absence, dict) and isinstance(absence.get("identifiers"), list) and bool(absence["identifiers"])
              and all(_text(i) for i in absence["identifiers"]) and isinstance(copies, list)
              and all(isinstance(c, dict) and _text(c.get("copy")) and _text(c.get("probe"))
                      and c.get("result") in PROBE_RESULTS for c in copies))
    if not shaped:
        add("absence-malformed", "the exact pre-change identifiers, and copies each {copy, probe, result: %s}"
            % ", ".join(PROBE_RESULTS))
        return
    if not copies or any(c["result"] == "not-run" for c in copies):
        add("absence-unprobed", "a claim of absence needs a probe that ran on every copy")
    for c in copies:
        if not any(i in c["probe"] for i in absence["identifiers"]):
            add("absence-probe-inexact", "%s: the probe names no pre-change identifier" % c["copy"])
        if c["result"] == "present":
            add("absence-survivor", "%s still holds a pre-change identifier: the removal is not done" % c["copy"])
    if absence.get("secret") is True and not _text(absence.get("rotated")):
        add("absence-unrotated", "rotate or revoke an exposed secret before purging history, and say how")


def scan_outcome(scan):
    """findings, clean or not-run, from a secret-scan receipt: the exit code and the log must agree (SC-33)."""
    log = scan.get("log") or ""
    if scan.get("exit") not in (0, 2) or PARTIAL.search(log) or not COMPLETION.search(log):
        return "not-run"
    if scan["exit"] == 2 and FOUND.search(log):
        return "findings"
    if scan["exit"] == 0 and not FOUND.search(log):
        return "clean"
    return "not-run"


def _validation_on(command):
    for match in re.finditer(r"--validation(?:=(\S+))?(?![\w-])", command):
        if (match.group(1) or "true").lower() not in ("false", "0"):
            return True
    return False


def _validates_by_default(tool, command):
    """A tool that validates found credentials unless its off switch is on the command line (SC-35 amended)."""
    return any(re.search(r"(?i)(?<![\w-])%s(?![\w-])" % re.escape(name), str(tool)) and not switch.search(command)
               for name, switch in DEFAULT_VALIDATION.items())


def _literal_secret(text):
    """A plain string (no pattern syntax once anchors are dropped), long, mixing letters and digits, and high in entropy."""
    core = text[1:] if text.startswith("^") else text
    core = core[:-1] if core.endswith("$") else core
    if len(core) < 16 or re.search(r"[\\.*+?()\[\]{}|^$]", core) or not (re.search(r"\d", core) and re.search(r"[A-Za-z]", core)):
        return False
    counts = collections.Counter(core)
    return -sum(n / len(core) * math.log2(n / len(core)) for n in counts.values()) >= 3.0


def allowlist_literals(text):
    """Where a scanner config's allow-lists hold a literal high-entropy value, as dotted paths (never the value)."""
    found = []

    def walk(node, trail, inside, key):
        if isinstance(node, dict):
            for name, value in node.items():
                walk(value, trail + "." + name if trail else name, inside or "allowlist" in name.lower(), name)
        elif isinstance(node, list):
            for n, value in enumerate(node):
                walk(value, "%s[%d]" % (trail, n), inside, key)
        elif inside and key in ALLOWLIST_KEYS and isinstance(node, str) and _literal_secret(node):
            found.append(trail)

    walk(tomllib.loads(text), "", False, None)
    return found


def _scan_problems(scan, root, anchors, add):
    complete_receipt = (isinstance(scan, dict) and all(_text(scan.get(f)) for f in ("tool", "version", "command", "config"))
                        and scan.get("scope") in SCAN_SCOPES and isinstance(scan.get("exit"), int)
                        and not isinstance(scan.get("exit"), bool) and isinstance(scan.get("log"), str)
                        and scan.get("result") in SCAN_RESULTS)
    if not complete_receipt:
        add("scan-malformed", "each secret scan records tool, version, command, config, scope (dir or git), exit, log "
            "and result")
        return
    name, command = "%s %s" % (scan.get("tool"), scan.get("scope")), str(scan.get("command") or "")
    history_fields = isinstance(scan.get("shallow"), bool) and _nonempty(scan.get("refs"))
    if scan.get("scope") == "git" and not history_fields:
        add("scan-malformed", name + ": a history scan records shallow (true or false) and the refs it scanned")
    if SECRET_SCANNERS.search(str(scan.get("tool"))):
        if not EXIT_TWO.search(command):
            add("scan-exit-ambiguous", name + ": pass --exit-code 2; exit 1 also means a failed or partial scan")
        redact = REDACT_FLAG.search(command)
        if not redact or redact.group(1) == "0":
            add("scan-unredacted", name + ": pass --redact, or the log and report print whole secrets")
        if not CONFIG_FLAG.search(command):
            add("scan-target-config", name + ": pass --config with a reviewed file; without it the scanner loads the "
                "scanned project's own config")
        if not INLINE_OFF.search(command):
            add("scan-inline-allow", name + ": pass --ignore-gitleaks-allow; without it the project's inline allow "
                "comments hide findings")
    if _validation_on(command):
        add("scan-validation", name + ": live validation sends the credential to its service; it stays off")
    elif _validates_by_default(scan.get("tool"), command):
        add("scan-validation", name + ": this tool validates by default; pass its off switch")
    outcome = scan_outcome(scan)
    if scan.get("result") != outcome:
        add("scan-misread", "%s: exit %s and the log give %s, not %s" % (name, scan.get("exit"), outcome, scan.get("result")))
    config_path = _inside(root, scan.get("config")) if root is not None else None
    if config_path is not None and config_path.is_file():
        try:
            if tomllib is None:
                raise ValueError("this Python has no TOML reader")
            entries = allowlist_literals(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            add("scan-config-unreadable", "%s: %s" % (scan["config"], exc))
            return
        for entry in entries:
            if "%s::%s" % (scan["config"], entry) not in anchors:
                add("allowlist-literal", "%s: %s is a literal high-entropy value; suppress it by fingerprint or path"
                    % (scan["config"], entry))


def validate(data, root=None):
    """Problems in a findings record. With root None the snippet and dismissal-basis comparisons are not run."""
    problems, counts, seen_ids, seen_keys = [], {state: 0 for state in STATES}, set(), set()
    if data.get("mode") not in MODES:
        problems.append({"id": None, "code": "bad-mode", "detail": "mode is one of " + ", ".join(MODES)})
    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    coverage = scope.get("coverage") if isinstance(scope.get("coverage"), dict) else {}
    if coverage and coverage.get("status") not in COVERAGE:
        problems.append({"id": None, "code": "bad-coverage", "detail": "coverage status is one of " + ", ".join(COVERAGE)})
    if coverage.get("status") == "complete" and not _text(coverage.get("receipt")):
        problems.append({"id": None, "code": "coverage-unreceipted", "detail": "complete coverage names its receipt"})
    for item in scope.get("excluded") or []:
        if not isinstance(item, dict) or not _text(item.get("what")):
            problems.append({"id": None, "code": "exclusion-malformed", "detail": "each exclusion has what and reason"})
            continue
        if not _text(item.get("reason")):
            problems.append({"id": None, "code": "exclusion-unreasoned", "detail": item.get("what")})
    anchors = {rec.get("anchor") for rec in data["records"] if isinstance(rec, dict)}
    for scan in scope.get("secret_scans") or []:
        _scan_problems(scan, root, anchors, lambda code, detail="": problems.append({"id": None, "code": code,
                                                                                      "detail": detail}))
    if scope.get("secret_scans") and root is not None:
        _suppression_problems(root, anchors, problems)
    for rec in data["records"]:
        if not isinstance(rec, dict):
            problems.append({"id": None, "code": "record-malformed", "detail": "each record is an object"})
            continue
        rid = rec.get("id")

        def add(code, detail="", rid=rid):
            problems.append({"id": rid, "code": code, "detail": detail})

        if not _text(rid) or rid in seen_ids:
            add("bad-id", "ids are unique non-empty strings")
        seen_ids.add(rid)
        state = rec.get("state")
        if state not in STATES:
            add("bad-state", "state is one of " + ", ".join(STATES))
            continue
        counts[state] += 1
        if not _text(rec.get("claim")):
            add("claim-missing", "one sentence")
        rule, anchor, instance = rec.get("rule"), rec.get("anchor"), rec.get("instance", "default")
        if state != "not-assessed" or rule or anchor:
            if not _text(rule) or not _text(anchor):
                add("identity-missing", "rule and a root-control anchor")
            elif LINE_IN_ANCHOR.search(anchor):
                add("anchor-has-line", "an anchor names the control, never a line number: " + anchor)
            key = (str(rule), str(anchor), str(instance))
            if key in seen_keys:
                add("duplicate-identity", " / ".join(key))
            seen_keys.add(key)
        if state != "confirmed" and "severity" in rec:
            add("severity-unconfirmed", "only a confirmed finding has a severity")
        if "reproduction" in rec and state != "confirmed":
            add("reproduction-unconfirmed", "only a confirmed finding is reproduced")
        if state == "confirmed":
            _confirmed_problems(rec, root, add)
            if "reproduction" in rec:
                _reproduction_problems(rec["reproduction"], add)
        elif state == "needs-review":
            if not _text(rec.get("missing_fact")):
                add("missing-fact", "name the smallest fact that would settle it")
        elif state == "not-assessed":
            if not _text(rec.get("settle")):
                add("settle-missing", "say what would settle it")
        elif state == "not-actionable":
            if not _nonempty(rec.get("positive_evidence")):
                add("not-actionable-unsupported", "positive evidence for every shipped path and supported configuration")
        elif state == "not-applicable":
            if rec.get("surface") in (None, "shipped") and rec.get("reach") not in ("self-only", "privileged-only"):
                add("not-applicable-unexplained", "cite the class: a surface other than shipped, or the reach")
        elif state == "rejected" and not _text(rec.get("reason")):
            add("rejection-unreasoned", "a rejected record keeps its reason")
        elif state == "dismissed":
            if _bare(rec.get("reason")):
                add("dismissal-bare", "a label is not a reason: %r" % rec.get("reason"))
            basis = rec.get("basis")
            if not isinstance(basis, dict):
                add("dismissal-bare", "a dismissal cites the source that justifies it")
            elif root is not None:
                basis_problem = _snippet_problem(root, basis)
                if basis_problem:
                    add("dismissal-lapsed", "the cited basis no longer holds (%s): the finding returns" % basis_problem[1])
        if "risk" in rec:
            _risk_problems(rec, state, add)
        if "absence" in rec:
            _absence_problems(rec["absence"], add)
    not_checked = [] if root is not None else ["snippets", "dismissal bases", "the project's own scanner files"]
    return {"problems": problems, "counts": counts, "not_checked": not_checked}


def _suppression_problems(root, anchors, problems):
    """SC-38: each scanner file and inline allow comment the scanned project holds is scope to review, never settled."""
    try:
        listing = suppressions(root)
    except OSError as exc:
        listing = {"files": [], "markers": [], "unread": [str(exc)]}
    wanted = {}
    for item in listing["files"]:
        wanted[item["path"]] = "%s: the project's own %s file for %s (%s); review it under a record anchored at it" % (
            item["path"], item["kind"], item["tools"], item["read_by"])
    lines = collections.defaultdict(list)
    for item in listing["markers"]:
        lines[(item["path"], item["marker"], item["tools"])].append(str(item["line"]))
    for (path, marker, tools), numbers in lines.items():
        wanted["%s::%s" % (path, marker)] = ("%s (line %s): an inline %s comment for %s; review it under a record "
                                             "anchored at %s::%s" % (path, ", ".join(numbers), marker, tools, path, marker))
    for anchor, detail in wanted.items():
        if anchor not in anchors:
            problems.append({"id": None, "code": "suppression-unreviewed", "detail": detail})
    if listing["unread"]:
        problems.append({"id": None, "code": "suppressions-unread", "detail": "%d files under ROOT could not be read for "
                         "inline allow comments: %s" % (len(listing["unread"]), ", ".join(listing["unread"][:20]))})


def _rank(rec):
    return (RANK_SEVERITY[rec["severity"]], RANK_LIKELIHOOD[rec["likelihood"]], -RANK_IMPACT[rec["impact"]], rec["id"])


def _status(data, counts, root):
    """The audit status and the reasons it is partial."""
    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    coverage = (scope.get("coverage") or {}).get("status", "not-run")
    paths = scope.get("paths") or ["."]
    scoped = any(p not in (".", "", "./") for p in paths)
    reasons = []
    if coverage != "complete":
        reasons.append("coverage " + coverage)
    if scoped:
        reasons.append("path-scoped run: " + ", ".join(paths))
    if counts["not-assessed"]:
        reasons.append("%d not assessed" % counts["not-assessed"])
    if counts["needs-review"]:
        reasons.append("%d need review" % counts["needs-review"])
    scans = [s for s in scope.get("secret_scans") or [] if isinstance(s, dict)]
    if scans:
        shallow = [s for s in scans if s.get("scope") == "git" and s.get("shallow") is True]
        done = {s.get("scope") for s in scans if scan_outcome(s) != "not-run" and s not in shallow}
        reasons += ["secret scan not-run: %s %s" % (s.get("tool"), s.get("scope")) for s in scans
                    if scan_outcome(s) == "not-run"]
        reasons += ["secret scan: %s git from a shallow clone (refs %s)" % (s.get("tool"), s.get("refs")) for s in shallow]
        if "dir" not in done:
            reasons.append("secret scan: working tree not scanned")
        if "git" not in done:
            reasons.append("secret scan: git history not scanned")
    if root is None:
        reasons.append("snippets not checked")
    return ("partial" if reasons else "complete"), reasons


def _line(rec, *fields):
    return "; ".join("%s: %s" % (f.replace("_", " "), "; ".join(rec[f]) if isinstance(rec[f], list) else rec[f])
                     for f in fields if f in rec)


def render(data, raw_sha, root=None):
    """The report Markdown, or None with the problems when the record does not pass the checks."""
    checked = validate(data, root)
    report_problems = checked["problems"]
    if report_problems:
        return checked, None
    counts = checked["counts"]
    records = data["records"]
    status, reasons = _status(data, counts, root)
    scope = data.get("scope") or {}
    confirmed = sorted((r for r in records if r["state"] == "confirmed"), key=_rank)
    out = ["<!-- generated by secaudit.py report from record sha256 %s; regenerate it, never edit it -->" % raw_sha,
           "# Security %s report" % data["mode"], "",
           "- Target: %s" % scope.get("target", "not stated"),
           "- Scope receipt: %s" % scope.get("receipt", "not recorded"),
           "- Coverage: %s%s" % ((scope.get("coverage") or {}).get("status", "not-run"),
                                 " (%s)" % scope["coverage"]["receipt"] if _text((scope.get("coverage") or {}).get("receipt")) else ""),
           "- Audit status: %s%s" % (status, " (" + "; ".join(reasons) + ")" if reasons else ""),
           "- Highest confirmed severity: %s" % (confirmed[0]["severity"] if confirmed else "none"),
           "- Counts: " + ", ".join("%s %d" % (s, counts[s]) for s in STATES), ""]
    out.append("## Confirmed findings (%d)" % len(confirmed))
    if not confirmed:
        out.append("No confirmed findings in the covered scope. This does not say the system is secure.")
    for n, rec in enumerate(confirmed, 1):
        out.append("%d. [%s] %s: %s" % (n, rec["severity"], rec["id"], rec["claim"]))
        out.append("   - Identity: %s / %s / %s" % (rec["rule"], rec["anchor"], rec.get("instance", "default")))
        out.append("   - Impact %s (demonstrated %s), likelihood %s%s%s" % (
            rec["impact"], rec["demonstrated_impact"], rec["likelihood"],
            ", confidence " + rec["confidence"] if rec.get("confidence") else "",
            ", scanner severity " + str(rec["scanner_severity"]) + " (verbatim, not used to rank)" if rec.get("scanner_severity") else ""))
        out.append("   - " + _line(rec, "principal", "source", "control", "sink", "path", "boundary", "resource", "result"))
        out.append("   - " + _line(rec, "counterevidence", "proof_gaps"))
        rep = rec.get("reproduction")
        if rep:
            run = rep.get("container") or {}
            out.append("   - Reproduction: %s%s%s" % (
                rep["label"], " in %s (exit %s, network %s): %s" % (run.get("image"), run.get("exit"), run.get("network"),
                                                                    rep.get("observed")) if rep["label"] != "static" else "",
                "; repairs: " + ", ".join("%s %s" % (r["candidate"], r["result"]) for r in rep.get("repairs", []))
                if rep.get("repairs") else ""))
        for snip in rec["snippets"]:
            out.append("   - %s: %s:%s" % (snip["role"], snip["file"], "-".join(str(n) for n in _lines(snip["lines"]))))
    sections = (("hardening", "Hardening notes", ()), ("needs-review", "Needs review", ("missing_fact",)),
                ("not-assessed", "Not assessed (abstentions)", ("settle",)),
                ("not-actionable", "Not actionable", ("positive_evidence",)),
                ("not-applicable", "Not applicable", ("surface", "reach")),
                ("dismissed", "Dismissed", ("reason",)), ("rejected", "Rejected (kept)", ("reason",)))
    for state, title, fields in sections:
        chosen = [r for r in records if r["state"] == state]
        if not chosen:
            continue
        out += ["", "## %s (%d)" % (title, len(chosen))]
        for rec in sorted(chosen, key=lambda r: r["id"]):
            extra = _line(rec, *fields)
            out.append("- %s: %s%s" % (rec["id"], rec["claim"], " (" + extra + ")" if extra else ""))
    labels = sorted((r for r in records if "risk" in r), key=lambda r: r["id"])
    if labels:
        out += ["", "## Risk labels (%d)" % len(labels)]
        out += ["- %s: %s (%s)" % (r["id"], r["risk"]["level"], "; ".join("%s: %s" % (c["name"], c["level"])
                                                                         for c in r["risk"]["checks"])) for r in labels]
    removals = sorted((r for r in records if "absence" in r), key=lambda r: r["id"])
    if removals:
        out += ["", "## Absence probes (%d)" % len(removals)]
        for rec in removals:
            absence = rec["absence"]
            out.append("- %s: %s probed on %s%s" % (
                rec["id"], ", ".join(absence["identifiers"]),
                ", ".join("%s (%s)" % (c["copy"], c["result"]) for c in absence["copies"]),
                "; rotated: " + absence["rotated"] if _text(absence.get("rotated")) else ""))
    scans = scope.get("secret_scans") or []
    if scans:
        out += ["", "## Secret scans (%d)" % len(scans)]
        out += ["- %s %s, %s: %s (exit %d; config %s)" % (s["tool"], s["version"], s["scope"], s["result"], s["exit"],
                                                         s["config"]) for s in scans]
    excluded = scope.get("excluded") or []
    if excluded:
        out += ["", "## Considered and excluded (%d, counted as unchecked)" % len(excluded)]
        out += ["- %s: %s" % (item["what"], item["reason"]) for item in excluded]
    return checked, "\n".join(out) + "\n"


def _secret_name(name):
    parts = [part.lower() for part in NAME_PARTS.findall(str(name))]
    return any(part in SECRET_PARTS for part in parts)


def _hide(name, value, tally):
    """A value under a secret-named key becomes <redacted>, numbers and containers too; a null stays null."""
    if value is None:
        return value
    if value != REDACTED:
        tally["count"] += 1
        tally["names"].add(str(name))
    return REDACTED


def _auth_value(name, value, tally):
    """An auth header keeps its scheme and loses its credential."""
    match = re.match(r"([A-Za-z][\w-]*[ \t]+)(\S.*)$", value, re.S)
    if not match:
        return _hide(name, value, tally)
    if match.group(2) != REDACTED:
        tally["count"] += 1
        tally["names"].add(str(name))
    return match.group(1) + REDACTED


def _cookie_value(name, value, tally):
    """A Cookie header keeps every name; Set-Cookie keeps its name and attributes. Values go."""
    out = []
    for n, pair in enumerate(value.split(";")):
        key, equals, rest = pair.partition("=")
        if equals and (str(name).lower() == "cookie" or n == 0) and rest.strip() and rest.strip() != REDACTED:
            tally["count"] += 1
            tally["names"].add(str(name))
            pair = key + "=" + REDACTED
        out.append(pair)
    return ";".join(out)


def _scrub_text(text, tally):
    def auth(match):
        return match.group(1) + (match.group(2) or "") + _hide("Authorization", match.group(3), tally)

    def cookie(match):
        return match.group(1) + match.group(2) + _cookie_value(match.group(1), match.group(3), tally)

    def header(match):
        if match.group(2).lower() in SPECIAL_HEADERS or not _secret_name(match.group(2)):
            return match.group(0)
        return match.group(1) + match.group(2) + match.group(3) + _hide(match.group(2), match.group(4), tally)

    def pair(match):
        if match.group(1).lower() in SPECIAL_HEADERS or not _secret_name(match.group(1)):
            return match.group(0)
        return match.group(1) + match.group(2) + _hide(match.group(1), match.group(3), tally)

    for pattern, swap in ((AUTH_HEADER, auth), (COOKIE_HEADER, cookie), (HEADER_LINE, header), (PAIR, pair)):
        text = pattern.sub(swap, text)
    return text


def _scrub_json(node, tally, depth=0):
    if depth > MAX_DEPTH:
        return _hide("(nested deeper than %d levels)" % MAX_DEPTH, node, tally)
    if isinstance(node, dict):
        out = {}
        for name, value in node.items():
            low = str(name).lower()
            if low in ("authorization", "proxy-authorization") and isinstance(value, str):
                out[name] = _auth_value(name, value, tally)
            elif low in ("cookie", "set-cookie") and isinstance(value, str):
                out[name] = _cookie_value(name, value, tally)
            elif _secret_name(name):
                out[name] = _hide(name, value, tally)
            else:
                out[name] = _scrub_json(value, tally, depth + 1)
        return out
    if isinstance(node, list):
        return [_scrub_json(value, tally, depth + 1) for value in node]
    if isinstance(node, str):
        return _scrub_text(node, tally)
    return node


def redact_text(text):
    """(scrubbed text, {"kind", "redactions", "names"}): JSON is walked by key, anything else is read as text."""
    tally = {"count": 0, "names": set()}
    data = None
    if text.strip()[:1] in ("{", "["):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
    if isinstance(data, (dict, list)):
        out, kind = json.dumps(_scrub_json(data, tally), indent=2, ensure_ascii=False) + "\n", "json"
    else:
        out, kind = _scrub_text(text, tally), "text"
    return out, {"kind": kind, "redactions": tally["count"], "names": sorted(tally["names"])}


def _write_out(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def _git_dir(root):
    dot = pathlib.Path(root) / ".git"
    if dot.is_dir():
        return dot
    try:
        text = dot.read_text(encoding="utf-8") if dot.is_file() else ""
    except OSError:
        return None
    match = re.match(r"gitdir:\s*(.+)", text)
    if match:
        target = pathlib.Path(match[1].strip())
        target = target if target.is_absolute() else (pathlib.Path(root) / target)
        return target if target.is_dir() else None
    return None


def _revision(root):
    """HEAD's commit read from .git files (never .git/config, never git itself); None when it cannot be read."""
    git = _git_dir(root)
    if git is None:
        return None
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head):
            return head
        match = re.fullmatch(r"ref:\s*(refs/[A-Za-z0-9._/-]+)", head)
        if not match or ".." in match[1]:
            return None
        common = git
        if (git / "commondir").is_file():
            common = (git / (git / "commondir").read_text(encoding="utf-8").strip()).resolve()
        for base in (git, common):
            loose = base / match[1]
            if loose.is_file():
                value = loose.read_text(encoding="utf-8").strip()
                return value if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) else None
        packed = common / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1] == match[1]:
                    return parts[0]
    except OSError:
        return None
    return None


def scope(root, tracked=None, excludes=()):
    """A content digest of ROOT: every file but .git and the excluded patterns, untracked ones included."""
    root = pathlib.Path(root)
    if not root.is_dir():
        raise OSError("not a directory: %s" % root)
    walked, matched = {}, {pattern: 0 for pattern in excludes}
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(files):
            if name == ".git":
                continue
            path = pathlib.Path(folder) / name
            rel = path.relative_to(root).as_posix()
            hit = next((p for p in excludes if fnmatch.fnmatchcase(rel, p)), None)
            if hit is not None:
                matched[hit] += 1
                continue
            if path.is_symlink():
                walked[rel] = hashlib.sha256(b"link:" + os.readlink(path).encode("utf-8", "surrogateescape")).hexdigest()
            else:
                walked[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name in list(dirs):
            if (pathlib.Path(folder) / name).is_symlink():
                rel = (pathlib.Path(folder) / name).relative_to(root).as_posix()
                walked[rel] = hashlib.sha256(b"link:" + os.readlink(pathlib.Path(folder) / name).encode(
                    "utf-8", "surrogateescape")).hexdigest()
                dirs.remove(name)
    hashed = walked
    digest = hashlib.sha256("".join("%s\0%s\n" % (rel, hashed[rel]) for rel in sorted(hashed)).encode("utf-8")).hexdigest()
    report = {"format": FORMAT, "mode": "scope", "status": "ok", "root": str(root), "revision": _revision(root),
              "revision_source": "read from .git files; the tree was not checked clean", "files": len(hashed),
              "content_sha256": digest, "excluded": [{"pattern": p, "files": n} for p, n in matched.items()],
              "untracked": None, "untracked_count": None, "claim": SCOPE_CLAIM}
    if tracked is not None:
        untracked = sorted(set(walked) - set(tracked))
        report.update(untracked=untracked[:200], untracked_count=len(untracked),
                      tracked_missing=len(set(tracked) - set(walked)))
    return report


def _file_markers(path):
    """(line, marker, tools, when) for each inline allow comment in a file, read in chunks that overlap."""
    found, carry, newlines = [], b"", 0
    with open(path, "rb") as stream:
        while True:
            block = stream.read(MARKER_CHUNK)
            if not block:
                return sorted(found)
            data = carry + block
            for pattern, tools, when in MARKERS:
                for match in pattern.finditer(data):
                    if match.end() > len(carry):  # one wholly inside the carried tail was found on the last read
                        marker = " ".join(match.group(0).decode("ascii").lower().split())
                        found.append((newlines + data.count(b"\n", 0, match.start()) + 1, marker, tools, when))
            carry = data[-MARKER_OVERLAP:]
            newlines += data.count(b"\n", 0, len(data) - len(carry))


def suppressions(root):
    """The scanned project's own scanner files and inline allow comments under ROOT (SC-38); .git and links are not read."""
    root = pathlib.Path(root)
    if not root.is_dir():
        raise OSError("not a directory: %s" % root)
    files, markers, unread, links = [], [], [], []
    for folder, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in sorted(dirs) if d != ".git"]
        links += [(pathlib.Path(folder) / d).relative_to(root).as_posix() for d in dirs
                  if (pathlib.Path(folder) / d).is_symlink()]
        for name in sorted(names):
            if name == ".git":
                continue
            path = pathlib.Path(folder) / name
            rel = path.relative_to(root).as_posix()
            for pattern, tools, kind, when in TARGET_FILES:
                if pattern.fullmatch(name):
                    files.append({"path": rel, "kind": kind, "tools": tools, "read_by": when})
            if path.is_symlink():
                links.append(rel)
                continue
            try:
                found = _file_markers(path)
            except OSError:
                unread.append(rel)
                continue
            markers += [{"path": rel, "line": line, "marker": marker, "tools": tools, "read_by": when}
                        for line, marker, tools, when in found]
    return {"files": files, "markers": markers, "unread": unread, "links_not_followed": links}


def _read_tracked(path):
    raw = pathlib.Path(path).read_bytes()
    text = raw.decode("utf-8")
    parts = text.split("\0") if "\0" in text else text.splitlines()
    return {p.strip().replace("\\", "/") for p in parts if p.strip()}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("secaudit.py: " + message + "\n")
        sys.exit(64)


def _emit(report):
    sys.stdout.write(json.dumps(report, indent=2) + "\n")


def main(argv=None):
    parser = _Parser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    c = sub.add_parser("check")
    c.add_argument("findings")
    c.add_argument("root")
    r = sub.add_parser("report")
    r.add_argument("findings")
    r.add_argument("--root")
    r.add_argument("--out")
    s = sub.add_parser("scope")
    s.add_argument("root")
    s.add_argument("--tracked")
    s.add_argument("--exclude", action="append", default=[])
    d = sub.add_parser("redact")
    d.add_argument("file")
    d.add_argument("--out")
    p = sub.add_parser("suppressions")
    p.add_argument("root")
    args = parser.parse_args(argv)
    if args.mode == "suppressions":
        try:
            listing = suppressions(args.root)
        except OSError as exc:
            _emit({"format": FORMAT, "mode": "suppressions", "status": "unreadable", "error": str(exc),
                   "claim": SUPPRESSIONS_CLAIM})
            return 2
        listed = bool(listing["files"] or listing["markers"])
        status = "findings" if listed else ("partial" if listing["unread"] else "clean")
        _emit({"format": FORMAT, "mode": "suppressions", "status": status, "root": args.root,
               "counts": {key: len(value) for key, value in listing.items()},
               **dict(listing, markers=listing["markers"][:MARKERS_SHOWN]), "claim": SUPPRESSIONS_CLAIM})
        return 1 if listed else (2 if status == "partial" else 0)
    if args.mode == "redact":
        try:
            raw = pathlib.Path(args.file).read_bytes()
            text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            _emit({"format": FORMAT, "mode": "redact", "status": "unreadable", "error": str(exc), "claim": REDACT_CLAIM})
            return 2
        scrubbed, info = redact_text(text)
        if args.out:
            _write_out(args.out, scrubbed)
        _emit({"format": FORMAT, "mode": "redact", "status": "redacted" if info["redactions"] else "clean", **info,
               "out": args.out, "text": scrubbed, "claim": REDACT_CLAIM})
        return 1 if info["redactions"] else 0
    if args.mode == "scope":
        try:
            tracked = _read_tracked(args.tracked) if args.tracked else None
            _emit(scope(args.root, tracked, tuple(args.exclude)))
            return 0
        except (OSError, UnicodeDecodeError) as exc:
            _emit({"format": FORMAT, "mode": "scope", "status": "unreadable", "error": str(exc), "claim": SCOPE_CLAIM})
            return 2
    root = args.root
    try:
        with open(args.findings, "rb") as stream:
            raw = stream.read()
        data = load_record(raw)
        if root is not None and not os.path.isdir(root):
            raise OSError("ROOT is not a directory: %s" % root)
    except (OSError, ValueError) as exc:
        _emit({"format": FORMAT, "mode": args.mode, "status": "unreadable", "error": str(exc),
               "claim": CHECK_CLAIM if args.mode == "check" else REPORT_CLAIM})
        return 2
    raw_sha = hashlib.sha256(raw).hexdigest()
    if args.mode == "check":
        checked = validate(data, root)
        report = {"format": FORMAT, "mode": "check", "status": "findings" if checked["problems"] else "clean",
                  "record_sha256": raw_sha, "root": root, **checked, "claim": CHECK_CLAIM}
        _emit(report)
        return 1 if checked["problems"] else 0
    checked, markdown = render(data, raw_sha, root)
    if markdown is None:
        _emit({"format": FORMAT, "mode": "report", "status": "refused", "record_sha256": raw_sha, **checked,
               "claim": REPORT_CLAIM})
        return 1
    if args.out:
        _write_out(args.out, markdown)
    _emit({"format": FORMAT, "mode": "report", "status": "rendered", "record_sha256": raw_sha,
           "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(), "out": args.out,
           "not_checked": checked["not_checked"], "markdown": markdown, "claim": REPORT_CLAIM})
    return 0


if __name__ == "__main__":
    sys.exit(main())
