"""Local evidence/record tools. No network, dependency installation or donor execution.

Checks identity and process structure, NOT semantic truth or host output interception.
Python 3.10+, standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

AXES = ("algorithms", "error_handling", "data_structures", "security_compliance", "performance")
RESULTS = {"ADOPT", "ADAPT", "ADAPT-with-prerequisite", "DISCARD", "ALREADY-COVERED", "OPPORTUNITY", "INCONCLUSIVE"}
STATES = {
    "QUEUED": {"RESEARCHING", "UNPROCESSED", "CANCELLED"},
    "RESEARCHING": {"READY", "BLOCKED", "CANCELLED", "UNPROCESSED"},
    "BLOCKED": {"RESEARCHING", "CANCELLED", "UNPROCESSED"},
    "UNPROCESSED": {"RESEARCHING", "CANCELLED"},
    "CANCELLED": {"RESEARCHING"},
    "READY": {"RESEARCHING"},
}
TRANSFER_KEYS = ("behavior", "donor_closure", "recipient_seam", "semantics", "alternatives", "effects_retry", "composition", "rollback", "authorization")
CONFIDENCE_LABELS = {"stated", "documented", "observed", "inferred", "speculated"}
LEGAL_FLAGS = {"GREEN", "YELLOW", "RED", "UNKNOWN"}
LEGAL_ROUTES = {"permissive-alternative", "idea-only", "license-subset", "public-api", "author-license", "clean-room", "discard", "n/a-open-permissive", "statutory-interop"}
FLAG_CODES = {"LEGAL-RED", "LEGAL-UNKNOWN", "LEGAL-YELLOW", "PAID-ELEMENT", "HARD-BLOCK", "PERIMETER-LOCKED", "PROHIBITED-BEHAVIOR", "ANTI-DETECT", "WRAP-REQUIRED", "PII-GATE", "DB-BYPASS", "NEW-PII-STORE", "PLATFORM-BLOCK", "SURFACE-MISMATCH", "PROFILE-CAPTURE", "HOOK-CONFLICT", "INJECTION-RISK", "SUPPLY-CHAIN-RISK", "OPAQUE-CODE", "TOS-CONFLICT", "DATA-BROKER-RISK", "NEW-DEP", "FOOTPRINT"}
# R5: donor-risk classes (references/due-diligence.md), RE ladder (references/re-verification.md), hook intake (references/hook-intake.md).
RISK_CODES = {"FAIL-OPEN-GUARD", "RUNNER-MISCOUNT", "NO-ASSERT-VERIFIED", "SILENT-SKIP-PASS", "HARDCODED-CLAIM", "HOOK-AUTO-ANSWER", "HOOK-APPROVAL-UNLOGGED", "ENV-LEAK", "UNPINNED-SESSION-INSTALL", "INSTRUCTION-TRUNCATION", "OVERRIDE-FILE", "COMMENT-SUPPRESSION", "CLIENT-CONFIG-WRITE", "UNBOUNDED-STOP-HOOK", "TAG-PINNED-ACTIONS", "HAND-PATH-FILTERS", "PUBLISH-NO-HASH", "NO-TEST-TIMEOUT", "WARN-ONLY-LINT", "MISSING-HOOK-PASSES", "PERMISSIVE-DEFAULT",
              # R5.1: checker-honesty.md
              "AUTO-EXEC", "INSTRUCTION-TAMPER", "AGENT-ADDRESSED-TEXT", "DONOR-STEERED-MAP", "ERROR-BODY-SUCCESS", "SELF-ATTESTED-EVIDENCE", "CONTINUE-ON-ERROR", "UNRUN-SUITE", "ABSENT-METRIC-PASS", "RATCHET-LOWERED",
              # R5.2: group3 P7.3-P7.4
              "REVIEW-MARKED-ON-FAILURE", "DROPPED-FILES-MARKED", "LAST-COMMIT-ONLY", "BASE-URL-EXFIL", "MATCHER-MATCH-ALL", "UNQUOTED-PATH-SUBST", "FORCED-MANAGED-HOOK", "HOOK-CONFIG-WARN-ONLY", "HOOK-RUN-UNRECORDED", "CONFIG-HASH-ONLY-TRUST"}
ORACLE_KINDS = {"exact", "behavioral", "differential", "hardware", "independent-decode", "tolerance", "statistical", "fallback", "self-roundtrip", "recompile-only", "cross-impl"}
WEAK_ORACLES = {"self-roundtrip", "recompile-only", "fallback"}
AGENT_SOURCE_KINDS = {"skill", "hook", "mcp", "agent-config", "plugin"}
RE_STATUSES = {"pass", "fail", "mismatch", "unknown", "unsupported", "not-run"}
RE_SCOPES = {"unit", "bounded", "campaign"}
RE_LABELS = {"observed", "derived", "inferred"}
RE_METHOD_CHECKS = {
    "matching-decompilation": {"target_toolchain", "original_bytes", "link_targets"},
    "functional-reconstruction": {"reference_behavior", "differential_cases", "edge_cases"},
    "static-recompilation": {"instruction_semantics", "runtime_dependencies", "platform_behavior"},
    "engine-reimplementation": {"content_compatibility", "runtime_behavior", "save_script_compatibility"},
    "recovered-source-port": {"recovered_baseline", "platform_semantics", "end_to_end_regression"},
    "other": {"scoped_acceptance"},
}
RE_BEHAVIOR_ORACLES = {"exact", "behavioral", "differential", "hardware", "tolerance", "statistical", "cross-impl"}
HOOK_APPROVERS = {"user", "session-flag"}
FLAG_CODES |= RISK_CODES
SHA256 = re.compile(r"[0-9a-f]{64}")


def check_donor_risks(ledger, source):
    risks = ledger.get("donor_risks")
    if risks is None:
        require(source["kind"] not in AGENT_SOURCE_KINDS, "agent-surface donor requires ledger.donor_risks audit")
        return []
    require(isinstance(risks, list), "donor_risks must be a list")
    seen = set()
    for r in risks:
        strings(r, ("code", "evidence", "status", "scope"), "donor_risk")
        require(r["code"] in RISK_CODES, f"unknown donor risk code: {r['code']}")
        require(r["code"] not in seen, "duplicate donor risk code")
        seen.add(r["code"])
        require(r["status"] in {"present", "absent", "unknown"}, "donor_risk status must be present/absent/unknown")
        require(r["scope"] in {"whole", "mechanism", "both"}, "donor_risk scope invalid")
        require(re.search(r":\d", r["evidence"]) or "://" in r["evidence"], "donor_risk evidence must cite file:line or a fetched URL")
    return [r for r in risks if r["status"] == "present"]


def check_re_claims(ledger, executions=None):
    claims = ledger.get("re_claims", [])
    require(isinstance(claims, list), "re_claims must be a list")
    seen = set()
    for c in claims:
        strings(c, ("id", "claim", "status", "scope", "legal_posture"), "re_claim")
        require(c["id"] not in seen, "duplicate RE claim id")
        seen.add(c["id"])
        require(c["status"] in RE_STATUSES, "re_claim status must come from the RE ladder")
        require(c["scope"] in RE_SCOPES, "re_claim scope must be unit/bounded/campaign")
        if c.get("reported_as") == "campaign-pass":
            require(c["scope"] == "campaign" and c["status"] == "pass", "bounded run cannot be reported as a campaign pass")
        prov = c.get("provenance")
        strings(prov, ("tool", "version", "sha256", "options", "label"), "re_claim.provenance")
        require(SHA256.fullmatch(prov["sha256"]), "re_claim provenance sha256 must be 64 lowercase hex")
        require(prov["label"] in RE_LABELS, "re_claim provenance label must be observed/derived/inferred")
        if prov.get("decompiler") is True:
            require(prov["label"] == "inferred", "decompiler output must be labelled inferred")
        a, n = c.get("assertions"), c.get("negative_controls")
        require(type(a) is int and type(n) is int and a >= 0 and n >= 0, "re_claim needs integer assertions and negative_controls")
        require(type(c.get("verified")) is bool, "re_claim.verified must be boolean")
        if c["verified"]:
            require(a >= 1 and n >= 1, "verified requires at least one assertion and one negative control")
            require(c["status"] == "pass", "verified requires status pass")
        if c["status"] == "pass":
            require(a >= 1, "pass requires at least one assertion")
        # R5.1: oracle kind (photocraft corpus.rs:24-31; Decompile-Diverge 2609.05370) and run counts (ghidra-mcp tests.yml:129-171)
        kind = c.get("oracle_kind")
        if kind is not None or c["verified"]:
            require(kind in ORACLE_KINDS, "re_claim.oracle_kind required for verified claims and must be a known kind")
            if c["verified"]:
                require(kind not in WEAK_ORACLES, "recompile-only/self-roundtrip/fallback oracle cannot make a claim verified")
        counts = c.get("run_counts")
        if counts is not None:
            require(isinstance(counts, dict) and all(type(counts.get(k)) is int and counts[k] >= 0 for k in ("total", "skipped", "failed")), "run_counts needs integer total/skipped/failed")
            require(counts["skipped"] + counts["failed"] <= counts["total"], "run_counts inconsistent")
            if c["status"] == "pass":
                require(counts["total"] > 0, "zero tests run cannot be a pass")
                require(counts["failed"] == 0, "failed tests cannot be a pass")
                if counts["skipped"]:
                    require(isinstance(c.get("skip_allowlist"), list) and len(c["skip_allowlist"]) == counts["skipped"] and all(nonempty(x) for x in c["skip_allowlist"]), "skipped tests in a pass need one allow-listed reason each")
        check_re_method(c)
        if executions is not None and (c["status"] == "pass" or c["verified"]):
            receipt = bound_execution(c, executions, "passing RE claim")
            require(receipt["run_counts"] == c["run_counts"] and receipt["assertions"] == a and receipt["negative_controls"] == n, "RE counts differ from captured execution checks")
            require(receipt["tool"]["sha256"] == prov["sha256"], "RE tool hash differs from captured execution tool")


def execution_verifier():
    spec = importlib.util.spec_from_file_location("aa_execution", Path(__file__).with_name("execution.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_evidence


def bound_execution(claim, executions, label):
    ident = claim.get("execution")
    require(isinstance(ident, str) and ident in executions, f"{label} requires captured execution evidence; keep unexecuted work unvalidated/not-run")
    receipt = executions[ident]
    require(receipt.get("_read_scope") != "unread", f"{label} cites unread execution evidence")
    require(receipt["eligible"] is True, f"{label} execution is not eligible: {receipt['reason']}")
    return receipt


def check_subsystems(coverage, evidence, executions, source):
    rows = coverage.get("subsystems")
    if rows is None:
        return
    subsystems = identifiers(rows, "coverage.subsystems")
    require(subsystems, "subsystem coverage cannot be empty; omit it for legacy selected-file records")
    for row in subsystems.values():
        strings(row, ("scope", "mapped", "inspected", "exercised", "limitations"), "subsystem")
        for key in ("mapped", "inspected", "exercised"):
            require(row[key] in {"complete", "partial", "unknown", "not-run", "not-applicable"}, f"subsystem.{key} has unknown state")
        support = refs(row.get("evidence"), evidence, "subsystem.evidence", row["inspected"] in {"complete", "partial"})
        require(all(e["subject"] == source["id"] and e["read_scope"] != "unread" for e in support), "subsystem evidence wrong source or unread")
        runs = refs(row.get("execution", []), executions, "subsystem execution evidence", row["exercised"] in {"complete", "partial"})
        require(all(r["subject"] == source["id"] for r in runs), "subsystem execution evidence belongs to another source")
        require(all(r.get("_read_scope") != "unread" for r in runs), "subsystem cites unread execution evidence")
        if row["exercised"] == "complete":
            require(any(r["run_counts"]["total"] > r["run_counts"]["skipped"] for r in runs), "complete exercised coverage needs executed positive checks")


def check_re_method(claim):
    """Check declared method and evidence shape, never certify their semantic truth."""
    method = claim.get("method")
    require(isinstance(method, str) and method in RE_METHOD_CHECKS, "RE claim requires a recognised method; split hybrid work into separate claims")
    strings(claim, ("output", "baseline", "contribution", "distribution"), "re_claim method contract")
    if method == "other":
        strings(claim, ("method_reason",), "re_claim other method")
    if "skip_allowlist" in claim:
        require(isinstance(claim["skip_allowlist"], list) and all(nonempty(x) for x in claim["skip_allowlist"]), "skip_allowlist must be a list of nonempty reasons")
    checks = claim.get("method_checks")
    require(isinstance(checks, dict) and set(checks) == RE_METHOD_CHECKS[method], f"{method} needs method_checks: {', '.join(sorted(RE_METHOD_CHECKS[method]))}")
    for name, check in checks.items():
        strings(check, ("status", "evidence"), f"method_checks.{name}")
        require(check["status"] in RE_STATUSES, "method check status must come from the RE ladder")
        if claim["status"] == "pass" or claim["verified"]:
            require(check["status"] == "pass", "passing RE claim requires every method check to pass; keep incomplete work unknown/mismatch/not-run")
    if claim["status"] == "pass":
        require(claim["negative_controls"] >= 1, "pass requires a negative control")
        require(claim.get("oracle_kind") in ORACLE_KINDS - WEAK_ORACLES, "pass requires a discriminating oracle_kind")
        require(isinstance(claim.get("run_counts"), dict), "passing RE claim requires run_counts")
        counts = claim["run_counts"]
        require(counts["total"] > counts["skipped"], "all-skipped RE run cannot pass")
        if method == "matching-decompilation":
            require(claim["oracle_kind"] == "exact", "matching decompilation requires an exact original-byte oracle")
        elif method != "other":
            require(claim["oracle_kind"] in RE_BEHAVIOR_ORACLES, "this reconstruction method requires a behavioral oracle; independent byte decoding alone is insufficient")
    progress = claim.get("progress")
    if progress is not None:
        strings(progress, ("unit", "basis"), "re_claim.progress")
        n, d = progress.get("numerator"), progress.get("denominator")
        require(type(n) is int and type(d) is int and 0 <= n <= d and d > 0, "progress needs integer 0 <= numerator <= denominator and denominator > 0")
        require(isinstance(progress.get("exclusions"), list) and all(nonempty(x) for x in progress["exclusions"]), "progress needs an explicit exclusions list")


def check_hooks(ledger):
    hooks = ledger.get("hooks", [])
    require(isinstance(hooks, list), "hooks must be a list")
    for h in hooks:
        strings(h, ("id", "content_sha256", "approved_sha256", "approved_by", "output_schema", "env", "approval_log", "on_error"), "hook")
        require(SHA256.fullmatch(h["content_sha256"]) and SHA256.fullmatch(h["approved_sha256"]), "hook hashes must be 64 lowercase hex")
        require(h["content_sha256"] == h["approved_sha256"], f"hook {h['id']} edited: approval revoked")
        # R5.2: Codex hashes config only (discovery.rs:768-794); adopt-adapt also hashes the script and every file it loads.
        files, approved = h.get("files"), h.get("approved_files")
        require(isinstance(files, list) and files, "hook must hash its script and every file it loads (config-only hash is not enough)")
        require(isinstance(approved, dict), "hook needs approved_files {path: sha256}")
        for f in files:
            strings(f, ("path", "sha256"), "hook file")
            require(SHA256.fullmatch(f["sha256"]), "hook file sha256 must be 64 lowercase hex")
            require(approved.get(f["path"]) == f["sha256"], f"hook file {f['path']} changed or unapproved: approval revoked")
        require(set(approved) == {f["path"] for f in files}, "approved hook files differ from hashed files")
        if "matcher" in h:
            try:
                re.compile(h["matcher"])
            except re.error:
                raise Invalid("invalid hook matcher must be an error, never match-all")
        require(h.get("decision_log") == "durable", "hook runs and decisions need a durable per-session record")
        require(h["approved_by"] in HOOK_APPROVERS, "hook approval must come from user or session flag, never project config")
        require(h["output_schema"] == "strict", "hook output schema must be strict (reject unknown fields, block needs reason)")
        require(h["env"] == "allowlist", "hook env must be an allowlist")
        require(h["approval_log"] == "visible-named", "hook approvals must be logged visibly naming the hook")
        require(h["on_error"] in {"ask", "deny"}, "hook must not fail open")
        require(h.get("auto_answer") is not True, "hook may not auto-answer user questions")
        if h.get("event") == "Stop":
            require(type(h.get("max_iterations")) is int and h["max_iterations"] > 0, "stop hook needs a positive iteration cap")


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    """Atomic local write; never follow an existing output symlink."""
    path = Path(path)
    require(not path.is_symlink(), f"output is a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".aa-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def contained(root, relative):
    require(nonempty(relative), "missing relative artifact path")
    rel = Path(relative)
    require(not rel.is_absolute() and ".." not in rel.parts and ":" not in relative, "artifact path must stay inside its root")
    root = Path(root).resolve()
    current = root
    for part in rel.parts:
        current = current / part
        require(not current.is_symlink() and not (hasattr(current, "is_junction") and current.is_junction()), "linked artifact paths are not allowed")
    require(current.resolve().is_relative_to(root), "artifact escapes root")
    return current


def identifiers(items, label):
    require(isinstance(items, list), f"{label} must be a list")
    result = {}
    for item in items:
        require(isinstance(item, dict), f"{label} entry must be an object")
        ident = item.get("id")
        require(isinstance(ident, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", ident), f"invalid {label} id")
        require(ident not in result, f"duplicate {label} id: {ident}")
        result[ident] = item
    return result


def strings(obj, keys, label):
    require(isinstance(obj, dict), f"{label} must be an object")
    for key in keys:
        require(nonempty(obj.get(key)), f"{label}.{key} needs nonempty text")


def refs(value, pool, label, required=True):
    require(isinstance(value, list) and (bool(value) or not required), f"{label} needs {'nonempty ' if required else ''}references")
    require(all(isinstance(x, str) and x in pool for x in value), f"{label} contains unknown references")
    require(len(value) == len(set(value)), f"{label} repeats references")
    return [pool[x] for x in value]


def score(rubric, components, penalty):
    require(rubric in RUBRICS, "unknown rubric")
    limits = [3, 2, 3, 2] if rubric in {"tooling", "coding-workflow"} else [3, 3, 2, 2]
    require(isinstance(components, list) and len(components) == 4, "score needs four components")
    require(all(type(v) is int and 0 <= v <= cap for v, cap in zip(components, limits)), "score component outside rubric")
    require(type(penalty) is int and penalty in {-2, -1, 0}, "penalty must be -2, -1 or 0")
    return sum(components) + penalty


# R3: profile names follow references/profiles/; legacy v2 aliases stay valid.
PROFILES = {"generic", "eddie", "radar", "rss-radar", "maginot", "coding-workflow", "tooling", "self", "unspecified"}
RUBRICS = {"generic", "eddie", "radar", "maginot", "coding-workflow", "tooling", "self"}
CONFIDENCE = {"high", "medium", "low"}


def check_routing(record):
    """R3: routing autodetection record (references/routing.md)."""
    recipients = record["recipients"]
    routing = record.get("routing")
    if routing is None:
        require(not any(r.get("profile") == "self" for r in recipients), "self profile requires a routing entry with explicit intent")
        return
    require(isinstance(routing, list) and routing, "routing must be a nonempty list")
    seen = {}
    for row in routing:
        require(isinstance(row, dict) and set(row) == {"profile", "confidence", "evidence", "explicit"}, "routing row needs profile/confidence/evidence/explicit")
        require(row["profile"] in PROFILES - {"unspecified"}, "unknown routing profile")
        require(row["profile"] not in seen, "duplicate routing profile")
        require(row["confidence"] in CONFIDENCE, "routing confidence must be high/medium/low")
        require(isinstance(row["evidence"], list) and row["evidence"] and all(isinstance(x, str) and x.strip() for x in row["evidence"]), "routing row needs evidence strings")
        require(type(row["explicit"]) is bool, "routing explicit must be boolean")
        if row["profile"] == "self":
            require(row["explicit"] is True, "never route to self without explicit user intent")
        seen[row["profile"]] = row
    for r in recipients:
        if r.get("profile") not in {"generic", "unspecified"}:
            require(r["profile"] in seen, f"recipient {r.get('id')} profile {r.get('profile')} not justified in routing")


def check_multi_recipient(record):
    """R3: one shared donor ledger per source; no recipient-claim bleed."""
    by_source = {}
    for item in record["items"]:
        if item.get("state") != "READY":
            continue
        by_source.setdefault(item["source"], []).append(item)
        for cid in item["decision"].get("recipient_claims", []):
            claim = next((c for c in record["claims"] if c["id"] == cid), None)
            require(claim is not None and claim["subject"] == item["recipient"], f"{item['id']}: recipient claim {cid} belongs to another recipient (profile bleed)")
    for source, items in by_source.items():
        primaries = {tuple(sorted(x["ledger"]["primary"])) for x in items}
        require(len(primaries) == 1, f"source {source}: recipients must share one donor evidence ledger (primary receipts differ)")


def doubt_depth(verdict, value=None, live=False, consequential=False, uncertain=False):
    return "full" if verdict == "ADOPT" or live or consequential or uncertain or (value is not None and 5 <= value <= 7) else "light"


def git_head(root):
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def snapshot(root, paths):
    root = Path(root).resolve()
    require(root.is_dir(), "recipient root missing")
    require(paths and len(paths) == len(set(paths)), "snapshot requires unique explicit paths")
    files = {}
    for name in sorted(paths):
        p = contained(root, name)
        require(not p.exists() or p.is_file(), f"snapshot path is not a file: {name}")
        files[name] = digest(p.read_bytes()) if p.exists() else None
    try:
        head = git_head(root)
    except FileNotFoundError:
        head = None
    identity = {"root": str(root), "head": head, "files": files}
    return {**identity, "id": digest(canonical(identity)), "captured_at": now(), "scope": "Explicit listed files only; undiscovered configuration is not covered."}


def check_snapshot(value, live=True):
    strings(value, ("root", "id", "captured_at", "scope"), "snapshot")
    require(isinstance(value.get("files"), dict) and value["files"], "snapshot needs selected files")
    identity = {k: value[k] for k in ("root", "head", "files")}
    require(value["id"] == digest(canonical(identity)), "snapshot identity mismatch")
    if live:
        require(snapshot(value["root"], list(value["files"]))["id"] == value["id"], "recipient snapshot is stale or changed worktree/configuration")


def capture(run_dir, path, subject, revision):
    require(nonempty(subject) and nonempty(revision), "capture requires subject and revision")
    root = Path(run_dir).resolve()
    require(not Path(path).is_symlink(), "capture source must not be a symlink")
    data = Path(path).read_bytes()
    sha = digest(data)
    relative = f"artifacts/{sha}.bin"
    target = contained(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        require(target.read_bytes() == data, "existing capture content conflict")
    else:
        target.write_bytes(data)
    # This is a local byte receipt, not authentication of remote acquisition or semantic truth.
    return {"id": "e" + digest(canonical([subject, revision, sha]))[:20], "subject": subject, "revision": revision, "path": relative, "sha256": sha, "bytes": len(data), "origin": str(Path(path).resolve()), "captured_at": now(), "read_scope": "unread", "limitations": "Local bytes captured; remote provenance and claim entailment require review."}


def init_run(root, sources, recipients):
    root = Path(root)
    require(not (root / "run.json").exists(), "run already exists")
    source_rows = [{"id": f"s{i+1}", "locator": url, "revision": "unresolved", "kind": "unresolved"} for i, url in enumerate(sources)]
    recipient_rows = [{"id": rid, "profile": "generic", "revision": "unresolved", "snapshot": None} for rid in recipients]
    identifiers(recipient_rows, "recipients")
    pairs = [{"id": f"q{i+1}", "source": s["id"], "recipient": r["id"], "state": "QUEUED", "transitions": ["QUEUED"], "reason": "Not yet researched"} for i, (s, r) in enumerate((s, r) for s in source_rows for r in recipient_rows)]
    record = {"schema_version": 1, "request": "Record the user's requested outcome", "host": {"name": "unknown", "renderer_rejects_incomplete_record": True, "host_prevents_freeform_final": "unavailable", "host_detects_violation": "exported-report-only"}, "sources": source_rows, "recipients": recipient_rows, "evidence": [], "claims": [], "items": pairs}
    save(root / "run.json", record)
    save(root / "inputs.json", {"sources": source_rows, "pairs": [{k: x[k] for k in ("id", "source", "recipient")} for x in pairs]})
    return record


def validate(record, root, live=True):
    """Fail with actionable error, including on malformed producer input."""
    try:
        _validate(record, Path(root), live)
        check_multi_recipient(record)
        return []
    except (Invalid, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        return [str(error) or type(error).__name__]


def _validate(record, root, live):
    require(isinstance(record, dict), "record must be an object")
    require(set(record) - {"routing"} == {"schema_version", "request", "host", "sources", "recipients", "evidence", "claims", "items"}, "unexpected or missing record fields")
    require(type(record["schema_version"]) is int and record["schema_version"] == 1, "unsupported schema_version")
    strings(record, ("request",), "record")
    host = record["host"]
    strings(host, ("name", "host_prevents_freeform_final", "host_detects_violation"), "host")
    require(host.get("renderer_rejects_incomplete_record") is True, "renderer contract must be explicit")
    require(host["host_prevents_freeform_final"] == "unavailable", "this bundle does not implement host interception")
    require(host["host_detects_violation"] == "exported-report-only", "this bundle checks exported reports only")
    sources = identifiers(record["sources"], "sources")
    recipients = identifiers(record["recipients"], "recipients")
    require(sources and recipients and not (sources.keys() & recipients.keys()), "need distinct source and recipient IDs")
    subjects = {**sources, **recipients}
    for s in sources.values():
        strings(s, ("locator", "revision", "kind"), "source")
    for r in recipients.values():
        strings(r, ("profile", "revision"), "recipient")
        require(r["profile"] in PROFILES, "unknown recipient profile")
        if r.get("snapshot") is not None:
            check_snapshot(r["snapshot"], live)
            require(r["revision"] == r["snapshot"]["id"], "recipient revision must equal snapshot identity")
    check_routing(record)
    ev = identifiers(record["evidence"], "evidence")
    executions = {}
    for e in ev.values():
        strings(e, ("subject", "revision", "path", "sha256", "origin", "captured_at", "read_scope", "limitations"), "evidence")
        require(e["subject"] in subjects and e["revision"] == subjects[e["subject"]]["revision"], "evidence subject/revision mismatch")
        data = contained(root, e["path"]).read_bytes()
        require(type(e.get("bytes")) is int and e["bytes"] == len(data) and e["sha256"] == digest(data), "evidence byte/hash mismatch")
        require(e.get("artifact_kind", "source") in {"source", "execution"}, "unknown evidence artifact_kind")
        if e.get("artifact_kind") == "execution":
            executions[e["id"]] = {**execution_verifier()(e, root, live=live), "_read_scope": e["read_scope"]}
    claims = identifiers(record["claims"], "claims")
    for c in claims.values():
        strings(c, ("subject", "text", "kind", "status", "scope", "limitations"), "claim")
        require(c["subject"] in subjects, "claim subject missing")
        require(c["kind"] in {"source_observation", "mechanism", "recipient_opportunity", "experiment", "verified_outcome"}, "invalid claim kind")
        require(c["status"] in {"supported", "inferred", "unvalidated", "refuted", "stale"}, "invalid claim status")
        if c["status"] == "inferred":
            require(c.get("confidence") in CONFIDENCE_LABELS, "inferred claim needs confidence label")
        evidence = refs(c.get("evidence"), ev, "claim.evidence", c["status"] == "supported")
        require(all(e["subject"] == c["subject"] for e in evidence), "claim cites another subject's evidence")
        if c["status"] == "supported":
            strings(c, ("review",), "supported claim")
            require(all(e["read_scope"] != "unread" for e in evidence), "supported claim cites unread evidence")
            if c["kind"] == "verified_outcome":
                receipt = bound_execution(c, executions, "supported verified_outcome")
                require(receipt["subject"] == c["subject"], "outcome execution evidence belongs to another subject")
                require(c["execution"] in c["evidence"], "verified_outcome must cite its execution evidence in claim.evidence")
        # Opposing observations may remain; a final decision must explain their resolution.
        refs(c.get("contradictions", []), claims, "claim.contradictions", False)
    items = identifiers(record["items"], "items")
    expected = {(s, r) for s in sources for r in recipients}
    pairs = [(x.get("source"), x.get("recipient")) for x in items.values()]
    require(len(pairs) == len(set(pairs)) and set(pairs) == expected, "queue lost/duplicated a source-recipient pair")
    manifest = load(contained(root, "inputs.json"))
    require([(x["id"], x["locator"]) for x in manifest["sources"]] == [(x["id"], x["locator"]) for x in sources.values()], "source manifest changed")
    require(manifest["pairs"] == [{k: x[k] for k in ("id", "source", "recipient")} for x in items.values()], "queue manifest changed")
    for item in items.values():
        state = item.get("state")
        require(state in STATES, "invalid queue state")
        transitions = item.get("transitions")
        require(isinstance(transitions, list) and transitions and transitions[0] == "QUEUED" and transitions[-1] == state, "invalid state history")
        require(all(a in STATES and isinstance(b, str) and b in STATES[a] for a, b in zip(transitions, transitions[1:])), "invalid state transition")
        if state != "READY":
            strings(item, ("reason",), "incomplete item")
            require("decision" not in item, "incomplete item cannot carry a verdict")
            continue
        source = sources[item["source"]]
        recipient = recipients[item["recipient"]]
        require(source["revision"] != "unresolved" and source["kind"] != "unresolved", "READY source is unresolved")
        ledger = item.get("ledger")
        require(isinstance(ledger, dict), "READY requires a process ledger")
        primary = refs(ledger.get("primary"), ev, "ledger.primary")
        require(all(e["subject"] == source["id"] and e["read_scope"] != "unread" for e in primary), "primary evidence wrong source or unread")
        mapping = ledger.get("map")
        strings(mapping, ("provider", "content", "limitations"), "map")
        require(mapping["provider"] in {"codewiki", "deepwiki", "self-synthesized", "not-applicable"}, "map missing or incomplete; source must stay BLOCKED")
        require(source["kind"] != "repo" or mapping["provider"] != "not-applicable", "repo requires an architecture map")
        refs(mapping.get("evidence"), ev, "map.evidence", mapping["provider"] != "not-applicable")
        cov = ledger.get("coverage")
        require(isinstance(cov, dict) and cov.get("adequate") is True, "coverage is incomplete")
        for key in ("examined", "refutation_targets", "blind_spots"):
            require(isinstance(cov.get(key), list) and (cov[key] or key == "blind_spots") and all(nonempty(x) for x in cov[key]), f"coverage.{key} missing")
        require(cov.get("total") is None or (type(cov["total"]) is int and cov["total"] >= len(cov["examined"])), "invalid coverage total")
        overlaps = refs(cov.get("overlap_claims", []), claims, "coverage.overlap_claims", False)
        require(all(c["subject"] == recipient["id"] for c in overlaps), "overlap claim belongs to another recipient or donor")
        check_subsystems(cov, ev, executions, source)
        hunt = ledger.get("salvage")
        require(isinstance(hunt, dict) and set(hunt) == set(AXES), "all five salvage axes required")
        for axis, row in hunt.items():
            strings(row, ("result", "note"), axis)
            require(row["result"] in {"found", "none", "not-applicable"}, "unknown salvage requires incomplete state")
            es = refs(row.get("evidence"), ev, axis)
            require(all(e["subject"] == source["id"] and e["read_scope"] != "unread" for e in es), "salvage evidence wrong source or unread")
        gates = ledger.get("gates")
        strings(gates, ("integrity", "policy", "paid_policy"), "gates")
        require(gates["paid_policy"] in {"preserved", "user-replaced"}, "paid policy missing")
        if gates["paid_policy"] == "user-replaced":
            strings(gates, ("authorization",), "paid policy replacement")
        require(isinstance(gates.get("flags"), list), "gate flags must be a list")
        for flag in gates["flags"]:
            strings(flag, ("code", "scope", "status", "resolution"), "flag")
            require(flag["code"] in FLAG_CODES and flag["scope"] in {"whole", "mechanism", "both"} and flag["status"] in {"unresolved", "resolved", "blocked"}, "invalid gate flag")
        legal = ledger.get("legal")
        require(isinstance(legal, dict), "READY requires ledger.legal")
        strings(legal, ("flag", "route", "advice_notice"), "legal")
        require(legal["flag"] in LEGAL_FLAGS, "invalid legal flag")
        require(legal["route"] in LEGAL_ROUTES, "invalid legal route")
        require(isinstance(legal.get("ladder_steps_tried"), list) and all(nonempty(x) for x in legal["ladder_steps_tried"]), "legal.ladder_steps_tried required")
        require(isinstance(legal.get("escalate_to_lawyer"), bool), "legal.escalate_to_lawyer must be bool")
        require(isinstance(legal.get("sources"), list) and legal["sources"], "legal.sources required")
        for src in legal["sources"]:
            strings(src, ("title", "url", "accessed"), "legal source")
        present_risks = check_donor_risks(ledger, source)
        source_executions = {k: v for k, v in executions.items() if v["subject"] == source["id"]}
        check_re_claims(ledger, source_executions)
        check_hooks(ledger)
        decision = item.get("decision")
        strings(decision, ("whole_tool", "result", "summary", "confidence", "mechanism_value", "next_step"), "decision")
        require(decision["result"] in RESULTS and decision["whole_tool"] in RESULTS, "unknown disposition")
        support = refs(decision.get("claims"), claims, "decision.claims")
        require(all(c["status"] in {"supported", "inferred"} and c["subject"] in {source["id"], recipient["id"]} for c in support), "decision rests on unsupported/stale/wrong-scope claim")
        require(any(c["subject"] == source["id"] and c["status"] == "supported" for c in support), "decision needs supported source facts")
        if any(c.get("contradictions") for c in support):
            strings(decision, ("contradiction_resolution",), "decision")
        target_claims = refs(decision.get("recipient_claims", []), claims, "decision.recipient_claims", False)
        require(all(c["subject"] == recipient["id"] and c["status"] == "supported" for c in target_claims), "recipient decision needs supported recipient facts")
        live_transfer = decision["result"] in {"ADOPT", "ADAPT", "ADAPT-with-prerequisite"}
        if live_transfer and legal["flag"] in {"RED", "UNKNOWN"}:
            raise Invalid("legal RED/UNKNOWN blocks transfer plan")
        if live_transfer and legal["flag"] == "YELLOW":
            require(decision["result"] == "ADAPT-with-prerequisite", "YELLOW legal flag requires ADAPT-with-prerequisite")
        if live_transfer or decision["result"] == "ALREADY-COVERED":
            require(target_claims and recipient.get("snapshot") is not None, "target-specific result needs live snapshot and recipient support")
            inventory = decision.get("inventory")
            require(isinstance(inventory, dict) and set(inventory) == {"implemented", "wired", "tested", "observed"}, "inventory needs four separate dimensions")
            for dimension in inventory.values():
                strings(dimension, ("state", "scope"), "inventory dimension")
                require(dimension["state"] in {"present", "absent", "unknown"}, "invalid inventory state")
            if decision["result"] == "ALREADY-COVERED":
                require(inventory["implemented"]["state"] == "present" and inventory["wired"]["state"] == "present", "unwired helper does not close capability gap")
        total = None
        if decision.get("score") is not None:
            s = decision["score"]
            require(isinstance(s, dict), "score must be an object or null")
            total = score(s.get("rubric"), s.get("components"), s.get("penalty"))
            require(type(s.get("total")) is int and s["total"] == total, "score total mismatch")
            strings(s, ("rationale",), "score")
        else:
            strings(decision, ("score_reason",), "unscored decision")
        if recipient["profile"] == "unspecified":
            require(decision["result"] in {"OPPORTUNITY", "INCONCLUSIVE", "DISCARD"} and total is None, "unspecified recipient cannot have target fit")
        for flag in gates["flags"]:
            if flag["code"] == "PAID-ELEMENT" and gates["paid_policy"] == "preserved":
                if flag["scope"] in {"whole", "both"}:
                    require(decision["whole_tool"] == "DISCARD", "paid whole integration must be discarded")
                if flag["scope"] in {"mechanism", "both"}:
                    require(not live_transfer, "paid mechanism cannot have a transfer plan")
            if flag["scope"] in {"whole", "both"} and flag["status"] != "resolved":
                require(decision["whole_tool"] != "ADOPT", "unresolved whole-tool gate forbids ADOPT")
            if flag["scope"] in {"mechanism", "both"} and flag["status"] != "resolved" and live_transfer:
                require(flag["code"] in {"PLATFORM-BLOCK", "SURFACE-MISMATCH", "SUPPLY-CHAIN-RISK", "NEW-DEP", "FOOTPRINT", "TOS-CONFLICT"} and decision["result"] == "ADAPT-with-prerequisite", "unresolved mechanism gate blocks transfer")
        if present_risks and live_transfer:
            require(decision["result"] == "ADAPT-with-prerequisite", "present donor risk requires ADAPT-with-prerequisite naming the fix")
        if any(r["scope"] in {"whole", "both"} for r in present_risks):
            require(decision["whole_tool"] != "ADOPT", "present donor risk forbids whole-tool ADOPT")
        if decision["result"] == "ADOPT":
            require(decision["whole_tool"] == "ADOPT", "ADOPT result must describe whole adoption")
        if live_transfer:
            transfer = decision.get("transfer")
            strings(transfer, TRANSFER_KEYS, "transfer")
            verification = transfer.get("verification")
            strings(verification, ("donor_parity", "domain_correctness", "recipient_regression", "entry_integration"), "transfer.verification")
            if decision["result"] == "ADAPT-with-prerequisite":
                strings(transfer, ("prerequisite",), "transfer")
        doubt = ledger.get("doubt")
        strings(doubt, ("depth", "against", "for", "environment", "resolution"), "doubt")
        require(type(doubt.get("consequential")) is bool and type(doubt.get("decision_uncertainty")) is bool, "doubt routing inputs must be booleans")
        depth = doubt_depth(decision["result"], total, live_transfer or any(x["result"] == "found" for x in hunt.values()), doubt["consequential"], doubt["decision_uncertainty"])
        require(doubt["depth"] == depth, f"doubt route must be {depth}")
        doubt_evidence = refs(doubt.get("evidence"), ev, "doubt.evidence")
        # Other queued donors may support a comparison; recipient facts stay local.
        require(all(e["subject"] in sources or e["subject"] == recipient["id"] for e in doubt_evidence), "doubt evidence belongs to another recipient")
        require(isinstance(doubt.get("unknowns"), list) and all(nonempty(x) for x in doubt["unknowns"]), "doubt.unknowns must be text list")


def text(value):
    # Source-controlled text cannot inject report markers/HTML/table rows.
    return html.escape(str(value)).replace("\r", " ").replace("\n", " ").replace("|", "&#124;")


def record_status(record, root, live=True):
    errors = validate(record, root, live)
    require(not errors, "; ".join(errors))
    ready = sum(item["state"] == "READY" for item in record["items"])
    if ready == len(record["items"]):
        scope = "ready-records"
    elif ready:
        scope = "mixed-records"
    else:
        scope = "inputs-only" if all(item["state"] == "QUEUED" for item in record["items"]) else "incomplete-records"
    return {"scope": scope, "ready_pairs": ready, "total_pairs": len(record["items"]), "pairs": [{k: item[k] for k in ("id", "source", "recipient", "state")} for item in record["items"]], "semantic_truth_certified": False, "narrative_outside_record_checked": False}


def render_re_claim(claim):
    lines = [f"- RE {text(claim['id'])}: {text(claim['status'])} / {text(claim['scope'])} | method {text(claim['method'])} | {text(claim['provenance']['tool'])} {text(claim['provenance']['version'])} {text(claim['provenance']['label'])} | assertions {claim['assertions']}, negative controls {claim['negative_controls']} | {text(claim['claim'])}"]
    lines.append(f"  - Oracle: {text(claim.get('oracle_kind', 'not-run'))}; verified: {claim['verified']}; tool/artifact SHA-256: {text(claim['provenance']['sha256'])}; options: {text(claim['provenance']['options'])}")
    if claim.get("run_counts") is not None:
        counts = claim["run_counts"]
        lines.append(f"  - Runs: total {counts['total']}, skipped {counts['skipped']}, failed {counts['failed']}; skip reasons: {text('; '.join(claim.get('skip_allowlist', [])) or 'none declared')}")
    else:
        lines.append("  - Runs: not supplied; no executed pass established")
    for key in ("method_reason", "output", "baseline", "contribution", "distribution"):
        if key in claim:
            lines.append(f"  - {key}: {text(claim[key])}")
    for name, check in claim["method_checks"].items():
        lines.append(f"  - {text(name)}: {text(check['status'])} — {text(check['evidence'])}")
    if claim.get("progress") is not None:
        p = claim["progress"]
        lines.append(f"  - Progress: {p['numerator']}/{p['denominator']} {text(p['unit'])}; basis: {text(p['basis'])}; exclusions: {text('; '.join(p['exclusions']) or 'none declared')}")
    lines.append(f"  - Execution receipt: {text(claim.get('execution', 'not supplied; declared evidence only'))}")
    return "\n".join(lines)


def render_subsystems(coverage):
    if "subsystems" not in coverage:
        return ["- Subsystem coverage: not recorded; selected-file coverage only."]
    return [f"- Subsystem {text(r['id'])}: {text(r['scope'])}; mapped={text(r['mapped'])}, inspected={text(r['inspected'])}, exercised={text(r['exercised'])}; evidence: {text(', '.join(r['evidence']) or 'none')}; execution: {text(', '.join(r.get('execution', [])) or 'not supplied')}; limits: {text(r['limitations'])}" for r in coverage["subsystems"]]


REVIEW_FIELDS = ("gates", "legal", "donor_risks", "re_claims", "hooks", "doubt")


def render_review_fields(ledger, fields):
    lines = []
    if "gates" in fields:
        gates = ledger["gates"]
        lines.extend([f"- Integrity: {text(gates['integrity'])}; policy: {text(gates['policy'])}", f"- Paid policy: {text(gates['paid_policy'])}; authorization: {text(gates.get('authorization', 'no replacement'))}"])
        for flag in gates["flags"]:
            lines.append(f"- GATE {text(flag['code'])}: {text(flag['status'])} ({text(flag['scope'])}) — {text(flag['resolution'])}")
    if "legal" in fields:
        legal = ledger["legal"]
        lines.extend([f"- LEGAL: {text(legal['flag'])} | route {text(legal['route'])} | escalate={legal['escalate_to_lawyer']} | ladder: {text(', '.join(legal['ladder_steps_tried']))}", f"- LEGAL notice: {text(legal['advice_notice'])}"])
        for source in legal["sources"]:
            lines.append(f"- LEGAL source: {text(source['title'])}; {text(source['url'])}; accessed {text(source['accessed'])}")
        for key in sorted(set(legal) - {"flag", "route", "escalate_to_lawyer", "ladder_steps_tried", "advice_notice", "sources"}):
            lines.append(f"- LEGAL {text(key)}: {text(json.dumps(legal[key], ensure_ascii=False))}")
    if "donor_risks" in fields:
        lines.extend(f"- DONOR RISK {text(r['code'])}: {text(r['status'])} ({text(r['scope'])}) — {text(r['evidence'])}" for r in ledger.get("donor_risks", []))
    if "re_claims" in fields:
        lines.extend(render_re_claim(c) for c in ledger.get("re_claims", []))
    if "hooks" in fields:
        lines.extend(f"- HOOK {text(h['id'])}: sha256 {text(h['content_sha256'])} approved by {text(h['approved_by'])}" for h in ledger.get("hooks", []))
    if "doubt" in fields:
        doubt = ledger["doubt"]
        lines.extend([f"- Doubt environment: {text(doubt['environment'])}; evidence: {text(', '.join(doubt['evidence']))}", f"- Doubt ({text(doubt['depth'])}): against — {text(doubt['against'])}; upgrade — {text(doubt['for'])}; resolution — {text(doubt['resolution'])}", f"- Unknowns: {text('; '.join(doubt['unknowns']) or 'none declared')}"])
    return lines


def render_shared_donor(source, items, identity, common):
    """Deduplicate exact donor facts; preserve distinct per-pair coverage variants."""
    lines = ["", f"<!-- aa:donor:{source} -->", f"## Shared donor evidence — {source}", ""]
    lines.append(f"- Source: {text(identity.get('resolved_locator', identity['locator']))}@{text(identity['revision'])}")
    fields = ("primary", "map", "coverage", "salvage")
    for field in fields:
        variants = {}
        for item in items:
            value = item["ledger"][field]
            if field == "coverage":
                value = {k: v for k, v in value.items() if k != "overlap_claims"}
            key = canonical(value)
            variants.setdefault(key, {"value": value, "items": []})["items"].append(item["id"])
        for variant in variants.values():
            value = variant["value"]
            if len(variants) > 1:
                lines.append(f"- {field} scope: {', '.join(variant['items'])}")
            if field == "primary":
                lines.append(f"- Primary receipts: {text(', '.join(value))}")
            elif field == "map":
                lines.append(f"- Forest: {text(value['provider'])} — {text(value['content'])}")
                lines.append(f"- Map receipts: {text(', '.join(value['evidence']) or 'not applicable')}; limits: {text(value['limitations'])}")
            elif field == "coverage":
                lines.append(f"- Coverage: {text('; '.join(value['examined']))}; refutation targets: {text('; '.join(value['refutation_targets']))}")
                lines.append(f"- Blind spots: {text('; '.join(value['blind_spots']) or 'none declared')}")
                lines.extend(render_subsystems(value))
            else:
                for axis, row in value.items():
                    lines.append(f"- {axis}: {text(row['result'])} — {text(row['note'])} [{text(', '.join(row['evidence']))}]")
    if common:
        lines.append(f"- Exact common review for pairs {', '.join(x['id'] for x in items)}: {', '.join(common)}. Each pair below explicitly references this basis.")
        lines.extend(render_review_fields(items[0]["ledger"], common))
    return lines


def render(record, root, live=True):
    errors = validate(record, root, live)
    require(not errors, "; ".join(errors))
    lines = ["# Adopt / adapt", "", f"Request: {text(record['request'])}", "", "Record checks establish bytes and structure; semantic review remains necessary.", "Host free-form output prevention: unavailable.", ""]
    if record.get("routing"):
        lines.extend(["## Routing", ""])
        for row in record["routing"]:
            lines.append(f"- {text(row['profile'])} ({text(row['confidence'])}{', explicit' if row['explicit'] else ''}): {text('; '.join(row['evidence']))}")
        lines.append("")
    lines.extend(["## Queue", ""])
    for item in record["items"]:
        lines.append(f"- {item['id']}: {item['source']} → {item['recipient']} — {item['state']}")
    groups = {}
    for item in record["items"]:
        if item["state"] == "READY":
            groups.setdefault(item["source"], []).append(item)
    emitted_sources = set()
    source_rows = {s["id"]: s for s in record["sources"]}
    recipient_rows = {r["id"]: r for r in record["recipients"]}
    lines.extend(["", "## Recipient snapshots", ""])
    for recipient in record["recipients"]:
        lines.append(f"- {recipient['id']}: {text(recipient['profile'])}@{text(recipient['revision'])}")
        if recipient.get("snapshot"):
            snap = recipient["snapshot"]
            lines.append(f"  - {text(snap['root'])}; HEAD {text(snap.get('head') or 'unavailable')}; selected files: {text(', '.join(snap['files']))}; limits: {text(snap['scope'])}")
    common_reviews = {source: [field for field in REVIEW_FIELDS if len(items) > 1 and all(x["ledger"].get(field) == items[0]["ledger"].get(field) for x in items)] for source, items in groups.items()}
    for item in record["items"]:
        ident = item["id"]
        if item["state"] != "READY":
            lines.extend(["", f"## {ident}: {item['state']} — no verdict", "", text(item["reason"])])
            continue
        ledger, decision = item["ledger"], item["decision"]
        if item["source"] not in emitted_sources:
            lines.extend(render_shared_donor(item["source"], groups[item["source"]], source_rows[item["source"]], common_reviews[item["source"]]))
            emitted_sources.add(item["source"])
        lines.extend(["", f"<!-- aa:ledger:{ident} -->", f"## PROCESS LEDGER — {ident}", "", f"Source / recipient: {item['source']} / {item['recipient']}", f"- Donor basis: shared donor evidence {item['source']} above; distinct coverage variants name their pairs.", f"- Recipient overlap claims: {text(', '.join(ledger['coverage'].get('overlap_claims', [])) or 'none')}"])
        recipient = recipient_rows[item["recipient"]]
        lines.append(f"- Recipient identity: {text(recipient['profile'])}@{text(recipient['revision'])}")
        lines.append(f"- Recipient snapshot basis: {item['recipient']} in Recipient snapshots above.")
        for key, dimension in decision.get("inventory", {}).items():
            lines.append(f"- Recipient {text(key)}: {text(dimension['state'])}; scope: {text(dimension['scope'])}")
        lines.append(f"- Recipient claims: {text(', '.join(decision.get('recipient_claims', [])) or 'none')}")
        common = common_reviews[item["source"]]
        if common:
            lines.append(f"- Common review basis: {', '.join(common)} in shared donor evidence {item['source']} above applies to this pair.")
        lines.extend(render_review_fields(ledger, [field for field in REVIEW_FIELDS if field not in common]))
        lines.extend(["", f"<!-- aa:verdict:{ident} -->", f"### {text(decision['result'])}", "", text(decision["summary"]), "", f"Whole tool: {text(decision['whole_tool'])}. Mechanism value: {text(decision['mechanism_value'])}.", f"Evidence confidence: {text(decision['confidence'])}."])
        if decision.get("score"):
            lines.append(f"Whole-tool fit: {decision['score']['total']} (range −2 to 10). {text(decision['score']['rationale'])}")
        else:
            lines.append(f"Whole-tool fit unscored: {text(decision['score_reason'])}")
        lines.append(f"Next step: {text(decision['next_step'])}")
        if decision.get("transfer"):
            lines.extend(["", "Transfer contract:"])
            for key, value in decision["transfer"].items():
                lines.append(f"- {text(key)}: {text(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value)}")
    multi = {k: v for k, v in groups.items() if len(v) > 1}
    if multi:
        lines.extend(["", "## Cross-recipient summary", ""])
        for source, items in multi.items():
            results = {x["decision"]["result"] for x in items}
            tag = "CONFLICT" if len(results) > 1 else "agree"
            lines.append(f"- {source} ({tag}): " + "; ".join(f"{x['recipient']} → {text(x['decision']['result'])}" for x in items))
    lines.extend(["", "## Evidence index", ""])
    for e in record["evidence"]:
        lines.append(f"- {e['id']}: {text(e['subject'])}@{text(e['revision'])}; {e['bytes']} bytes; SHA-256 {e['sha256']}; `{text(e['path'])}`; read: {text(e['read_scope'])}; limits: {text(e['limitations'])}")
    lines.extend(["", "## Claim review", ""])
    for c in record["claims"]:
        lines.append(f"- {c['id']} ({c['status']}): {text(c['text'])}; support: {text(', '.join(c['evidence']))}; review: {text(c.get('review', 'not reviewed'))}; limits: {text(c['limitations'])}")
    return "\n".join(lines) + "\n"


def check_output(record, root, output, live=True):
    expected = render(record, root, live)
    require(output.replace("\r\n", "\n") == expected, "output differs from checked rendering (order, content or completeness)")
    return True


def invalidate_lessons(data, ident):
    require(isinstance(data, dict) and isinstance(data.get("lessons"), list), "lessons file requires lessons list")
    rows = identifiers(data["lessons"], "lessons")
    require(ident in rows, "unknown lesson")
    for row in rows.values():
        refs(row.get("parents"), rows, "lesson.parents", False)
    affected = {ident}
    while True:
        expanded = affected | {i for i, row in rows.items() if set(row["parents"]) & affected}
        if expanded == affected:
            break
        affected = expanded
    for i in affected:
        rows[i]["status"] = "stale"
        rows[i]["stale_because"] = ident
    return data


PATH_RULE_LISTS = ("governed_prefixes", "governed_exact", "measurement_dependencies",
                   "policy_prefixes", "preflight_self", "documentation_prefixes", "test_suffixes")


def relative_rule_path(value, prefix=False):
    require(isinstance(value, str) and bool(value), "path must be nonempty text")
    p = value.replace("\\", "/")
    require(not p.startswith("/") and ":" not in p and not any(ord(c) < 32 for c in p), "path must be relative")
    body = p[:-1] if prefix and p.endswith("/") else p
    require(all(part not in ("", ".", "..") for part in body.split("/")), "path must be canonical without traversal")
    require(not prefix or p.endswith("/"), "path prefix must end with /")
    return p


def load_path_rules(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate path-rule JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def recipient_path_class(path, rules):
    """Apply explicit caller rules; classification never grants edit authorization."""
    require(isinstance(rules, dict) and set(rules) == {"revision", *PATH_RULE_LISTS}, "complete explicit path rules required")
    require(isinstance(rules["revision"], str) and bool(rules["revision"].strip()), "path rules require a revision")
    normalized = {}
    for key in PATH_RULE_LISTS:
        values = rules[key]
        require(isinstance(values, list) and all(isinstance(x, str) and x for x in values), "path rule must be a text list: " + key)
        if key == "test_suffixes":
            require(all(x.startswith(".") and "/" not in x and "\\" not in x for x in values), "invalid test suffix")
            normalized[key] = tuple(values)
        else:
            normalized[key] = tuple(relative_rule_path(x, key.endswith("_prefixes")) for x in values)
    p = relative_rule_path(path)
    governed = not p.endswith(normalized["test_suffixes"]) and (
        p in normalized["governed_exact"] or p.startswith(normalized["governed_prefixes"]))
    if governed:
        category, safe = "governed", False
    elif p.startswith(normalized["policy_prefixes"]):
        category, safe = "freeze-policy-drift", False
    elif p in normalized["preflight_self"]:
        category, safe = "preflight-self", True
    elif p in normalized["measurement_dependencies"]:
        category, safe = "measurement-dependency", False
    elif p.startswith(normalized["documentation_prefixes"]):
        category, safe = "docs", True
    else:
        category, safe = "ungoverned-needs-disposition", False
    return {"path": p, "pin": rules["revision"], "class": category, "safe_to_change": safe,
            "authorization": "not-granted; caller rules require independent recipient review"}


def radar_path_class(path, rules=None):
    """Legacy API name only; no private project policy is bundled."""
    require(rules is not None, "No bundled recipient rules; supply explicit rules with classify-path --rules FILE")
    return recipient_path_class(path, rules)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("directory"); p.add_argument("--source", action="append", required=True); p.add_argument("--recipient", action="append", required=True)
    p = sub.add_parser("capture"); p.add_argument("directory"); p.add_argument("file"); p.add_argument("--subject", required=True); p.add_argument("--revision", required=True)
    p = sub.add_parser("snapshot"); p.add_argument("root"); p.add_argument("--path", action="append", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("score"); p.add_argument("--rubric", choices=["generic", "eddie", "tooling"], required=True); p.add_argument("--components", nargs=4, type=int, required=True); p.add_argument("--penalty", type=int, default=0)
    p = sub.add_parser("doubt"); p.add_argument("verdict", choices=sorted(RESULTS)); p.add_argument("--score", type=int); p.add_argument("--live", action="store_true"); p.add_argument("--consequential", action="store_true"); p.add_argument("--uncertain", action="store_true")
    for name in ("validate", "status", "render", "check-output", "history"):
        p = sub.add_parser(name); p.add_argument("record")
        p.add_argument("--historical", action="store_true", help="Do not check live recipient; replay only, not current decision validation")
        if name == "render": p.add_argument("--output", required=True)
        if name == "check-output": p.add_argument("output")
        if name == "history": p.add_argument("--ledger", required=True); p.add_argument("--published-report", required=True)
    for name in ("classify-path", "radar-path"):
        p = sub.add_parser(name); p.add_argument("path", nargs="+")
        p.add_argument("--rules", required=name == "classify-path", help="explicit caller-owned path rules; no bundled recipient policy")
    p = sub.add_parser("invalidate"); p.add_argument("file"); p.add_argument("id"); p.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            init_run(args.directory, args.source, args.recipient); print("Created QUEUED run; no source evaluated.")
        elif args.command == "capture":
            print(json.dumps(capture(args.directory, args.file, args.subject, args.revision), ensure_ascii=False, indent=2))
        elif args.command == "snapshot":
            save(args.output, snapshot(args.root, args.path)); print("Snapshot saved; scope is explicit selected files.")
        elif args.command == "score":
            print(score(args.rubric, args.components, args.penalty))
        elif args.command == "doubt":
            print(doubt_depth(args.verdict, args.score, args.live, args.consequential, args.uncertain))
        elif args.command in ("classify-path", "radar-path"):
            require(args.rules is not None, "No bundled recipient rules; supply --rules FILE")
            rules = load_path_rules(args.rules)
            print(json.dumps([recipient_path_class(x, rules) for x in args.path], indent=2))
        elif args.command == "invalidate":
            save(args.output, invalidate_lessons(load(args.file), args.id)); print("Changed lesson and descendants marked stale.")
        else:
            root = Path(args.record).resolve().parent
            record = load(args.record)
            errors = validate(record, root, not args.historical)
            require(not errors, "; ".join(errors))
            if args.command == "validate":
                checked = [] if args.historical else [r["id"] for r in record["recipients"] if r.get("snapshot") is not None]
                unchecked = [r["id"] for r in record["recipients"] if r["id"] not in checked]
                # R3 fix: v2 reported live_recipient_checked=true even when no snapshot existed.
                print(json.dumps({"valid_structure_and_bytes": True, "semantic_truth_certified": False, "live_recipient_checked": bool(checked) and not unchecked, "recipients_live_checked": checked, "recipients_not_checked": unchecked, "host_interception": False}))
            elif args.command == "status":
                print(json.dumps(record_status(record, root, not args.historical), indent=2))
            elif args.command == "render":
                output = Path(args.output)
                require(not output.exists(), "report output exists; use a new filename")
                output.write_text(render(record, root, not args.historical), encoding="utf-8", newline="\n")
                print(f"Rendered {output}. Emit its ledger before each result in the chat.")
            elif args.command == "check-output":
                check_output(record, root, Path(args.output).read_text(encoding="utf-8"), not args.historical); print("Exported report matches checked rendering; unseen chat not checked.")
            elif args.command == "history":
                require(not args.historical, "historical replay cannot create a new live verdict event")
                check_output(record, root, Path(args.published_report).read_text(encoding="utf-8"))
                path = Path(args.ledger)
                require(not path.is_symlink(), "history destination is a link")
                path.parent.mkdir(parents=True, exist_ok=True)
                event = {"ts": now(), "record_sha256": digest(canonical(record)), "decisions": [{"source": x["source"], "recipient": x["recipient"], "result": x["decision"]["result"]} for x in record["items"] if x["state"] == "READY"]}
                # Deliberately append only: do not read earlier decisions into the process.
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                print("Appended audit event; command assumes the named report was actually published.")
        return 0
    except (Invalid, ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
