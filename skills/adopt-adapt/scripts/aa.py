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
LIVE_RESULTS = {"ADOPT", "ADAPT", "ADAPT-with-prerequisite"}
CONFIDENCE_LEVELS = {"low", "medium", "high"}  # anchors: SKILL.md §4
ADAPT_MIN_VALUE = 2  # SKILL.md §8 decision tree
ADOPT_MIN_FIT = 8
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
# Fourth pass. Ladder levels and reviewer levels are the shared vocabulary's (references/evidence-vocabulary.md).
LADDER = ("claimed", "present", "wired", "tested", "observed")
RUN_LEVELS = {"tested", "observed"}
REVIEW_LEVELS = ("self", "fresh-context-same-model", "different-model", "human")
TRANSFER_RELATIONS = {"new", "replaces", "augments", "makes-usable"}  # references/transfer.md §4
SEAM_STATUSES = {"governed", "frozen", "perimeter", "ungoverned"}
REVIEWED_SEAMS = {"governed", "frozen", "perimeter"}
REFUTATION_OUTCOMES = {"confirmed", "refuted", "unknown"}
REUSE_ROUTES = LEGAL_ROUTES - {"discard"}
WAIVER_KEYS = ("by", "covers", "text", "date")
OUTCOME_RESULTS = ("passed", "failed", "skipped", "blocked", "not-run")  # evidence-vocabulary.md results
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
HTTP_URL = re.compile(r"https?://[^\s/]+\S*")


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
    require(rubric in known_rubrics(), "unknown rubric")
    limits = [3, 2, 3, 2] if rubric in {"tooling", "coding-workflow"} else [3, 3, 2, 2]
    require(isinstance(components, list) and len(components) == 4, "score needs four components")
    require(all(type(v) is int and 0 <= v <= cap for v, cap in zip(components, limits)), "score component outside rubric")
    require(type(penalty) is int and penalty in {-2, -1, 0}, "penalty must be -2, -1 or 0")
    return sum(components) + penalty


# Profile names are the installed files in references/profiles/ plus the aliases those profiles declare,
# so an edition that omits a recipient's profile also omits its name. No recipient is named in code.
PROFILE_DIR = Path(__file__).resolve().parents[1] / "references" / "profiles"


GENERIC_ALIASES = {"tooling": "coding-workflow"}  # legacy v2 name


def profile_aliases():
    aliases_file = PROFILE_DIR / "aliases.json"  # profile-owned legacy names, shipped with those profiles
    # Profile metadata, not a record: read directly so building the CLI parser never loads a record.
    declared = json.loads(aliases_file.read_text(encoding="utf-8-sig")) if aliases_file.is_file() else {}
    require(isinstance(declared, dict), "profile aliases must be a JSON object")
    aliases = {**GENERIC_ALIASES, **declared}
    require(all(isinstance(k, str) and isinstance(v, str) for k, v in aliases.items()), "profile aliases must map names to profile names")
    return aliases


def known_profiles():
    stems = {p.stem for p in PROFILE_DIR.glob("*.md")}
    return stems | {alias for alias, target in profile_aliases().items() if target in stems} | {"unspecified"}


def known_rubrics():
    return (known_profiles() - {"unspecified"}) | {"generic"}


def resolve_profile(name):
    return profile_aliases().get(name, name) if isinstance(name, str) else name


def rubric_for(profile):
    """The rubric a recipient is scored on: its own profile's when that profile has a '## … Rubric' section,
    otherwise the generic rubric (SKILL.md §4). An unspecified recipient has none."""
    name = resolve_profile(profile)
    if name == "unspecified":
        return None
    path = PROFILE_DIR / f"{name}.md"
    if name == "generic" or not path.is_file():
        return "generic"
    return name if re.search(r"^## .*\bRubric\b", path.read_text(encoding="utf-8"), re.M) else "generic"


ROUTING_SECTION = re.compile(r"^## Routing signals[^\n]*\n(.*?)(?=^## |\Z)", re.M | re.S)


def routing_index():
    """Every installed profile's '## Routing signals' section, generated so it cannot drift from the profiles.
    A run reads this instead of every profile, then loads only the profiles it selects (references/routing.md)."""
    lines = ["# Routing index", "",
             "Generated by `aa.py routing-index` from the `## Routing signals` section of each installed profile. "
             "Choose recipients here, then read only the chosen profiles in full."]
    for path in sorted(PROFILE_DIR.glob("*.md")):
        match = ROUTING_SECTION.search(path.read_text(encoding="utf-8"))
        require(match is not None, f"profile {path.stem} has no '## Routing signals' section")
        lines.extend(["", f"## {path.stem} (references/profiles/{path.name})", "", match.group(1).strip()])
    return "\n".join(lines) + "\n"


def profile_path_rules_file(name):
    require(isinstance(name, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name) is not None, "profile name must be a lowercase profile id")
    path = PROFILE_DIR / f"{name}-path-rules.json"
    require(path.is_file(), f"profile {name} ships no path-rules file")
    return path
CONFIDENCE = {"high", "medium", "low"}


def check_routing(record):
    """Validate recorded routing, not host activation or automatic path detection.

    Every recipient with a verdict (a READY pair) needs a routing row for its profile, `unspecified` included,
    so a profile cannot be inherited silently from `init`. Input-only and incomplete pairs stay recoverable."""
    recipients = record["recipients"]
    routing = record.get("routing")
    seen = {}
    if routing is not None:
        require(isinstance(routing, list) and routing, "routing must be a nonempty list")
        for row in routing:
            require(isinstance(row, dict) and set(row) == {"profile", "confidence", "evidence", "explicit"}, "routing row needs profile/confidence/evidence/explicit")
            require(row["profile"] in known_profiles(), "unknown routing profile")
            require(resolve_profile(row["profile"]) not in seen, "duplicate routing profile")
            require(row["confidence"] in CONFIDENCE, "routing confidence must be high/medium/low")
            require(isinstance(row["evidence"], list) and row["evidence"] and all(isinstance(x, str) and x.strip() for x in row["evidence"]), "routing row needs evidence strings")
            require(type(row["explicit"]) is bool, "routing explicit must be boolean")
            if row["profile"] == "self":
                require(row["explicit"] is True, "never route to self without explicit user intent")
            seen[resolve_profile(row["profile"])] = row
    with_verdict = {x.get("recipient") for x in record["items"] if isinstance(x, dict) and x.get("state") == "READY"}
    for r in recipients:
        if r.get("profile") == "self":
            require(routing is not None, "self profile requires a routing entry with explicit intent")
        if r.get("id") in with_verdict or r.get("profile") == "self":
            require(resolve_profile(r.get("profile")) in seen,
                    f"recipient {r.get('id')} profile {r.get('profile')} not justified in routing: every recipient with a verdict requires a routing entry for its profile (`unspecified` included)")


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


def doubt_depth(verdict, value=None, live=False, consequential=False, uncertain=False, salvage_found=False):
    """The single doubt rule of SKILL.md §7, shared by the CLI and the validator."""
    full = verdict in LIVE_RESULTS or live or salvage_found or consequential or uncertain or (value is not None and 5 <= value <= 7)
    return "full" if full else "light"


def check_mechanism_value(decision):
    value = decision.get("mechanism_value")
    if isinstance(value, str):
        raise Invalid(f"decision.mechanism_value must be an integer 0-3 (SKILL.md §4 anchors); legacy text {value!r} needs re-assessment, not conversion")
    require(type(value) is int and 0 <= value <= 3, "decision.mechanism_value must be an integer 0-3 (SKILL.md §4 anchors)")
    require(decision.get("confidence_level") in CONFIDENCE_LEVELS, "decision.confidence_level must be low, medium or high (SKILL.md §4 anchors)")
    return value


def check_inventory_ladder(inventory, executions, recipient_id):
    """SKILL.md §0.7 / evidence-vocabulary.md: TESTED and OBSERVED need a receipt from a run in this work."""
    implemented = inventory["implemented"]["state"] == "present"
    for key in ("wired", "tested", "observed"):
        if inventory[key]["state"] == "present":
            require(implemented, f"inventory.{key} present requires inventory.implemented present")
    for key, label in (("tested", "TESTED"), ("observed", "OBSERVED")):
        if inventory[key]["state"] == "present":
            receipt = executions.get(inventory[key].get("run")) if isinstance(inventory[key].get("run"), str) else None
            require(receipt is not None and receipt["subject"] == recipient_id and receipt.get("_read_scope") != "unread" and receipt["eligible"] is True,
                    f"inventory.{key} present needs `run` = the ID of this recipient's eligible execution evidence: {label} means it ran in this work with a passing receipt; author-tested results rank no higher than WIRED (keep the state unknown and say so in scope)")


IDEA_CHECKS = {"patent_signal": {"none", "hit", "unknown"}, "terms_restriction": {"none", "present", "unknown"}}


def check_legal_row(row, label, legal):
    """references/legal.md: the patent-signal check runs on every reuse route; GREEN needs no patent signal, and
    GREEN(idea-only) also needs no terms restriction. A hit is YELLOW plus counsel."""
    reuse = row.get("route") in REUSE_ROUTES
    if reuse:
        require(row.get("patent_signal") in IDEA_CHECKS["patent_signal"], f"{label}: every reuse route needs patent_signal (hit/none/unknown)")
    if row.get("route") == "idea-only":
        allowed = IDEA_CHECKS["terms_restriction"]
        require(row.get("terms_restriction") in allowed, f"{label}: idea-only route needs terms_restriction ({'/'.join(sorted(allowed))})")
        if row["flag"] == "GREEN":
            require(row["patent_signal"] == "none" and row["terms_restriction"] == "none", f"{label}: GREEN(idea-only) needs patent_signal none and terms_restriction none; otherwise the flag is YELLOW or worse")
    elif reuse and row["flag"] == "GREEN":
        require(row["patent_signal"] == "none", f"{label}: GREEN needs patent_signal none on every reuse route (MIT and BSD carry no patent grant); a hit or an open patent question is YELLOW or worse")
    if reuse and row["patent_signal"] == "hit":
        require(legal.get("escalate_to_lawyer") is True, f"{label}: a patent-signal hit is YELLOW plus counsel; set escalate_to_lawyer true")


def effective_flag(row, legal, label):
    """An UNKNOWN licence becomes YELLOW only with the owner's recorded waiver; nothing else can be waived."""
    waiver = row.get("waiver")
    if waiver is None:
        return row["flag"]
    strings(waiver, WAIVER_KEYS, f"{label}.waiver")
    require(row["flag"] == "UNKNOWN", f"{label}: an owner waiver applies only to an UNKNOWN flag")
    require(waiver["covers"] == "licence", f"{label}: an owner waiver covers an unknown licence only; unknown terms, TPM status or hard-line facts cannot be waived")
    require(ISO_DATE.fullmatch(waiver["date"]) is not None, f"{label}: waiver date must be YYYY-MM-DD")
    require(legal.get("hard_line_hit") is False, f"{label}: no waiver applies past a hard line")
    return "YELLOW"


def legal_basis(legal, decision):
    """Return (effective flag, part or None, route) governing a transfer: a named clean part, or the whole tool."""
    ident = decision.get("legal_part")
    parts = legal.get("parts")
    check_legal_row(legal, "ledger.legal", legal)
    whole = effective_flag(legal, legal, "ledger.legal")
    rows = {}
    if parts is not None:
        rows = identifiers(parts, "legal.parts")
        for row in rows.values():
            strings(row, ("part", "flag", "route", "basis"), "legal part")
            require(row["flag"] in LEGAL_FLAGS and row["route"] in LEGAL_ROUTES, "legal part needs a known flag and route")
            check_legal_row(row, f"legal part {row['id']}", legal)
            effective_flag(row, legal, f"legal part {row['id']}")
            if legal["hard_line_hit"]:
                require(row["flag"] == "RED", f"hard line: legal part {row['id']} comes from a donor past a hard line and must be RED")
    if ident is None:
        return whole, None, legal["route"]
    require(parts is not None and ident in rows, "decision.legal_part must name an entry in ledger.legal.parts")
    require(not legal["hard_line_hit"], "hard line: no part of a donor past a hard line may transfer")
    part = rows[ident]
    if whole in {"RED", "UNKNOWN"}:
        require(decision["whole_tool"] == "DISCARD", "whole-tool legal RED/UNKNOWN requires whole-tool DISCARD; only the named clean part may transfer")
    require(part["route"] != "discard", "a discarded legal part cannot carry a transfer")
    return effective_flag(part, legal, f"legal part {part['id']}"), part, part["route"]


def check_caps(decision, decisive, mechanism_value, source_id):
    """SKILL.md §4: confidence and mechanism value are capped by the ladder levels of the claims they rest on."""
    level = {c["id"]: LADDER.index(c["level"]) for c in decisive}
    confidence = decision["confidence_level"]
    if decision["result"] == "INCONCLUSIVE":
        require(confidence == "low", "INCONCLUSIVE means a decisive unknown is open: confidence_level must be low")
    weak = [c["id"] for c in decisive if c["status"] == "inferred" or c["level"] == "claimed"]
    if weak:
        require(confidence == "low", f"confidence_level must be low: decisive claim(s) {', '.join(weak)} rest on CLAIMED or inferred evidence (SKILL.md §4)")
    if confidence == "high":
        require(all(level[c["id"]] >= LADDER.index("wired") for c in decisive) and any(c["level"] in RUN_LEVELS for c in decisive),
                "confidence_level high needs every decisive claim at WIRED or above and at least one TESTED or OBSERVED claim with its run")
    if mechanism_value >= 2:
        require(any(c["subject"] == source_id and c["status"] == "supported" and level[c["id"]] >= LADDER.index("present") for c in decisive),
                "mechanism_value >= 2 needs the donor mechanism inspected at PRESENT or above (a supported source claim at level present or higher)")
    if mechanism_value == 3:
        require(any(c["level"] in RUN_LEVELS for c in decisive), "mechanism_value 3 needs a decisive claim at TESTED or OBSERVED, with its run recorded in this work")


def check_review(review, root, required, reason):
    """SKILL.md §7: an independent review is required only for ADOPT, governed/frozen/perimeter seams, consequential
    decisions or high confidence; its level comes from the shared vocabulary and self never satisfies it."""
    if review is None:
        require(not required, f"independent review required ({reason}): record ledger.review with a level above self and the packet or report hash")
        return
    strings(review, ("level", "artifact", "sha256", "disconfirming"), "review")
    require(review["level"] in REVIEW_LEVELS, "review level must be self, fresh-context-same-model, different-model or human")
    require(type(review.get("checked")) is bool, "review.checked must be boolean (was the strongest disconfirming observation checked?)")
    require(SHA256.fullmatch(review["sha256"]) is not None and digest(contained(root, review["artifact"]).read_bytes()) == review["sha256"],
            "review artifact bytes do not match review.sha256")
    if required:
        require(review["level"] != "self", f"independent review required ({reason}): level self cannot satisfy it")


def check_refutation_targets(targets):
    require(isinstance(targets, list) and targets, "coverage.refutation_targets missing")
    for row in targets:
        target = row.get("target") if isinstance(row, dict) else row
        if isinstance(row, dict):
            require(set(row) <= {"target", "outcome"} and row.get("outcome") in REFUTATION_OUTCOMES, "refutation target outcome must be confirmed, refuted or unknown")
        require(isinstance(target, str) and len(re.findall(r"[^\W\d_]{2,}", target)) >= 2,
                "refutation target must state the observation that would refute the claim, not a placeholder")


def refutation_text(row):
    return f"{row['target']} ({row['outcome']})" if isinstance(row, dict) else row


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


def parse_recipient(spec):
    """`id=profile`, or a bare `id` that defaults to `unspecified` (no fit, no ADAPT, and no verdict until a
    routing row records the chosen profile)."""
    require(isinstance(spec, str), "recipient must be text: id or id=profile")
    ident, separator, profile = spec.partition("=")
    profile = profile if separator else "unspecified"
    require(profile in known_profiles(), f"recipient {ident}: unknown profile {profile!r}; installed: {', '.join(sorted(known_profiles()))}")
    return ident, profile


def init_run(root, sources, recipients):
    root = Path(root)
    require(not (root / "run.json").exists(), "run already exists")
    source_rows = [{"id": f"s{i+1}", "locator": url, "revision": "unresolved", "kind": "unresolved"} for i, url in enumerate(sources)]
    recipient_rows = [{"id": rid, "profile": profile, "revision": "unresolved", "snapshot": None} for rid, profile in map(parse_recipient, recipients)]
    identifiers(recipient_rows, "recipients")
    require(not ({s["id"] for s in source_rows} & {r["id"] for r in recipient_rows}), "need distinct source and recipient IDs (source IDs are s1, s2, ...)")
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
        require(r["profile"] in known_profiles(), "unknown recipient profile")
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
        # SKILL.md §0.7 and references/evidence-vocabulary.md: the highest level actually shown for this claim.
        level = c.get("level")
        require(level in LADDER, f"claim {c['id']} needs a ladder level (claimed/present/wired/tested/observed; references/evidence-vocabulary.md); legacy claims need re-assessment, not conversion")
        if c["status"] in {"stale", "unvalidated"}:
            require(level == "claimed", f"claim {c['id']}: a {c['status']} claim stays at level claimed until it is re-checked")
        if level != "claimed":
            require(evidence and all(e["read_scope"] != "unread" for e in evidence), f"claim {c['id']}: level {level} needs read evidence of its subject at this revision; it cites none, or only unread evidence")
        if level in RUN_LEVELS:
            run = bound_execution(c, executions, f"claim {c['id']} at level {level}")
            require(run["subject"] == c["subject"], f"claim {c['id']}: its run belongs to another subject")
        if c["status"] == "supported":
            strings(c, ("review",), "supported claim")
            require(all(e["read_scope"] != "unread" for e in evidence), "supported claim cites unread evidence")
            if c["kind"] == "verified_outcome":
                receipt = bound_execution(c, executions, "supported verified_outcome")
                require(receipt["subject"] == c["subject"], "outcome execution evidence belongs to another subject")
                require(c["execution"] in c["evidence"], "verified_outcome must cite its execution evidence in claim.evidence")
                require(level in RUN_LEVELS, f"claim {c['id']}: a supported verified_outcome is TESTED or OBSERVED")
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
        for key in ("examined", "blind_spots"):
            require(isinstance(cov.get(key), list) and (cov[key] or key == "blind_spots") and all(nonempty(x) for x in cov[key]), f"coverage.{key} missing")
        check_refutation_targets(cov.get("refutation_targets"))
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
        require(isinstance(legal.get("hard_line_hit"), bool), "legal.hard_line_hit must be bool (references/legal.md hard lines)")
        if legal["hard_line_hit"]:
            require(legal["flag"] == "RED", "hard line: a donor past a hard line is RED as a whole")
        require(isinstance(legal.get("sources"), list) and legal["sources"], "legal.sources required")
        for src in legal["sources"]:
            strings(src, ("title", "url", "accessed"), "legal source")
            require(HTTP_URL.fullmatch(src["url"]) is not None, "legal source url must be an http(s) URL")
            require(ISO_DATE.match(src["accessed"]) is not None, "legal source accessed must start with an ISO date (YYYY-MM-DD)")
        present_risks = check_donor_risks(ledger, source)
        source_executions = {k: v for k, v in executions.items() if v["subject"] == source["id"]}
        check_re_claims(ledger, source_executions)
        check_hooks(ledger)
        decision = item.get("decision")
        strings(decision, ("whole_tool", "result", "summary", "confidence", "next_step"), "decision")
        require(decision["result"] in RESULTS and decision["whole_tool"] in RESULTS, "unknown disposition")
        mechanism_value = check_mechanism_value(decision)
        if decision.get("promising_check") is not None:
            require(nonempty(decision["promising_check"]) and decision["result"] == "DISCARD" and mechanism_value == 1,
                    "promising_check labels a DISCARD at mechanism value 1 only: DISCARD (promising: <check to run>)")
        support = refs(decision.get("claims"), claims, "decision.claims")
        require(all(c["status"] in {"supported", "inferred"} and c["subject"] in {source["id"], recipient["id"]} for c in support), "decision rests on unsupported/stale/wrong-scope claim")
        require(any(c["subject"] == source["id"] and c["status"] == "supported" for c in support), "decision needs supported source facts")
        if any(c.get("contradictions") for c in support):
            strings(decision, ("contradiction_resolution",), "decision")
        target_claims = refs(decision.get("recipient_claims", []), claims, "decision.recipient_claims", False)
        require(all(c["subject"] == recipient["id"] and c["status"] == "supported" for c in target_claims), "recipient decision needs supported recipient facts")
        if "OPPORTUNITY" in {decision["result"], decision["whole_tool"]}:
            require(recipient["profile"] == "unspecified", "OPPORTUNITY means no recipient; a named recipient gets ADOPT, ADAPT, ALREADY-COVERED, DISCARD or INCONCLUSIVE")
        if recipient["profile"] == "unspecified":
            require(decision["result"] in {"OPPORTUNITY", "INCONCLUSIVE", "DISCARD"} and decision.get("score") is None,
                    "unspecified recipient cannot have a target-specific result or fit; choose its profile (`init --recipient id=profile`) and record its routing row")
        live_transfer = decision["result"] in LIVE_RESULTS
        transfer_flag, _, governing_route = legal_basis(legal, decision)
        if live_transfer and transfer_flag in {"RED", "UNKNOWN"}:
            raise Invalid("legal RED/UNKNOWN blocks transfer plan")
        if live_transfer and transfer_flag == "YELLOW":
            require(decision["result"] == "ADAPT-with-prerequisite", "YELLOW legal flag requires ADAPT-with-prerequisite")
        if live_transfer:
            require(governing_route != "discard", "a legal route of discard cannot carry a transfer; name a clean part with its own lawful route")
            require(mechanism_value >= ADAPT_MIN_VALUE, "a transfer result needs mechanism_value >= 2; keep a lower-value clue as a promising lesson or DISCARD")
        if live_transfer or decision["result"] == "ALREADY-COVERED":
            require(target_claims and recipient.get("snapshot") is not None, "target-specific result needs live snapshot and recipient support")
            inventory = decision.get("inventory")
            require(isinstance(inventory, dict) and set(inventory) == {"implemented", "wired", "tested", "observed"}, "inventory needs four separate dimensions")
            for dimension in inventory.values():
                strings(dimension, ("state", "scope"), "inventory dimension")
                require(dimension["state"] in {"present", "absent", "unknown"}, "invalid inventory state")
            check_inventory_ladder(inventory, executions, recipient["id"])
            covered = inventory["implemented"]["state"] == "present" and inventory["wired"]["state"] == "present"
            if decision["result"] == "ALREADY-COVERED":
                require(covered, "unwired helper does not close capability gap")
                require(mechanism_value == 0, "ALREADY-COVERED means the recipient already has it WIRED: mechanism_value 0 (SKILL.md §4)")
            elif covered:
                relation = decision.get("transfer", {}).get("relation") if isinstance(decision.get("transfer"), dict) else None
                require(relation in {"replaces", "augments"}, "the recipient already has this implemented and wired: that is ALREADY-COVERED unless transfer.relation says the mechanism replaces or augments it")
        total = None
        if decision.get("score") is not None:
            s = decision["score"]
            require(isinstance(s, dict), "score must be an object or null")
            total = score(s.get("rubric"), s.get("components"), s.get("penalty"))
            require(type(s.get("total")) is int and s["total"] == total, "score total mismatch")
            strings(s, ("rationale",), "score")
            expected = rubric_for(recipient["profile"])
            require(resolve_profile(s["rubric"]) == expected,
                    f"score rubric {s['rubric']} does not match recipient {recipient['id']}: profile {recipient['profile']} scores on the {expected} rubric")
        else:
            strings(decision, ("score_reason",), "unscored decision")
        if "ADOPT" in {decision["result"], decision["whole_tool"]}:
            require(total is not None and total >= ADOPT_MIN_FIT, "whole-tool ADOPT needs a scored whole-tool fit >= 8")
            require(mechanism_value >= ADAPT_MIN_VALUE, "whole-tool ADOPT needs mechanism_value >= 2")
        decisive = list({c["id"]: c for c in [*support, *target_claims]}.values())
        check_caps(decision, decisive, mechanism_value, source["id"])
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
        transfer = decision.get("transfer") if live_transfer else None
        if live_transfer:
            strings(transfer, TRANSFER_KEYS, "transfer")
            require(transfer.get("relation") in TRANSFER_RELATIONS, "transfer.relation must be new, replaces, augments or makes-usable (references/transfer.md §4)")
            require(transfer.get("seam_status") in SEAM_STATUSES, "transfer.seam_status must be governed, frozen, perimeter or ungoverned (the recipient's rules for the receiving seam)")
            verification = transfer.get("verification")
            strings(verification, ("donor_parity", "domain_correctness", "recipient_regression", "entry_integration"), "transfer.verification")
            if decision["result"] == "ADAPT-with-prerequisite":
                strings(transfer, ("prerequisite",), "transfer")
        doubt = ledger.get("doubt")
        strings(doubt, ("depth", "against", "for", "environment", "resolution"), "doubt")
        require(type(doubt.get("consequential")) is bool and type(doubt.get("decision_uncertainty")) is bool, "doubt routing inputs must be booleans")
        depth = doubt_depth(decision["result"], total, live_transfer, doubt["consequential"], doubt["decision_uncertainty"],
                            salvage_found=any(x["result"] == "found" for x in hunt.values()))
        require(doubt["depth"] == depth, f"doubt route must be {depth}")
        doubt_evidence = refs(doubt.get("evidence"), ev, "doubt.evidence")
        # Other queued donors may support a comparison; recipient facts stay local.
        require(all(e["subject"] in sources or e["subject"] == recipient["id"] for e in doubt_evidence), "doubt evidence belongs to another recipient")
        require(isinstance(doubt.get("unknowns"), list) and all(nonempty(x) for x in doubt["unknowns"]), "doubt.unknowns must be text list")
        if decision["result"] == "INCONCLUSIVE":
            require(doubt["unknowns"], "INCONCLUSIVE must name what is missing in doubt.unknowns")
        triggers = [name for name, hit in (("ADOPT", "ADOPT" in {decision["result"], decision["whole_tool"]}),
                                           ("consequential decision", doubt["consequential"]),
                                           ("high confidence", decision["confidence_level"] == "high"),
                                           ("governed, frozen or perimeter seam", bool(transfer) and transfer.get("seam_status") in REVIEWED_SEAMS)) if hit]
        check_review(ledger.get("review"), root, bool(triggers), ", ".join(triggers))


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


def handoff(record, root, live=True, record_name="run.json"):
    """Read-only recovery projection, using the record's existing authority/IDs.

    Reject invalid evidence and mappings rather than publishing a partially checked
    success. JSON pointers identify the original fields; local paths are data, never
    fetched, executed, or turned into source-controlled Markdown links.
    """
    status = record_status(record, root, live)
    require(nonempty(record_name) and Path(record_name).name == record_name,
            "handoff record reference must be a local filename")
    contained(root, record_name)

    def reference(pointer):
        return {"path": record_name, "pointer": pointer}

    sources = {s["id"]: (i, s) for i, s in enumerate(record["sources"])}
    recipients = {r["id"]: (i, r) for i, r in enumerate(record["recipients"])}
    pairs = []
    for i, item in enumerate(record["items"]):
        si, source = sources[item["source"]]
        ri, recipient = recipients[item["recipient"]]
        pointer = f"/items/{i}"
        ready = item["state"] == "READY"
        unresolved = []
        if ready:
            ledger, decision = item["ledger"], item["decision"]
            transfer = decision.get("transfer")
            prerequisite = transfer.get("prerequisite") if isinstance(transfer, dict) else None
            if nonempty(prerequisite):
                unresolved.append({"kind": "prerequisite", "text": prerequisite,
                                   "reference": reference(pointer + "/decision/transfer/prerequisite")})
            for j, unknown in enumerate(ledger["doubt"]["unknowns"]):
                unresolved.append({"kind": "unknown", "text": unknown,
                                   "reference": reference(pointer + f"/ledger/doubt/unknowns/{j}")})
            for j, flag in enumerate(ledger["gates"]["flags"]):
                if flag["status"] != "resolved":
                    unresolved.append({"kind": "gate", "code": flag["code"], "scope": flag["scope"],
                                       "status": flag["status"], "text": flag["resolution"],
                                       "reference": reference(pointer + f"/ledger/gates/flags/{j}")})
            next_step = {"text": decision["next_step"], "basis": reference(pointer + "/decision/next_step"),
                         "authorization": "not-assessed"}
        else:
            unresolved.append({"kind": "reason", "text": item["reason"],
                               "reference": reference(pointer + "/reason")})
            next_step = {"text": "Consult the recorded reason and request scope before continuing this pair.",
                         "basis": reference(pointer + "/reason"), "authorization": "not-assessed"}
        subjects = {source["id"], recipient["id"]}
        pairs.append({
            "id": item["id"], "state": item["state"], "reference": reference(pointer),
            "source": {"id": source["id"], "locator": source["locator"], "revision": source["revision"],
                       "reference": reference(f"/sources/{si}")},
            "recipient": {"id": recipient["id"], "profile": recipient["profile"], "revision": recipient["revision"],
                          "reference": reference(f"/recipients/{ri}"),
                          "snapshot_reference": reference(f"/recipients/{ri}/snapshot") if recipient.get("snapshot") else None,
                          "snapshot_scope": recipient["snapshot"]["scope"] if recipient.get("snapshot") else "unavailable",
                          "live_checked": live and recipient.get("snapshot") is not None},
            "ledger_reference": reference(pointer + "/ledger") if isinstance(item.get("ledger"), dict) else None,
            "unresolved": unresolved, "next_step": next_step,
            "evidence": [{**{k: e[k] for k in ("id", "subject", "revision", "path", "read_scope", "limitations")},
                          "artifact_kind": e.get("artifact_kind", "source"), "reference": reference(f"/evidence/{j}")}
                         for j, e in enumerate(record["evidence"]) if e["subject"] in subjects],
            "claims": [{**{k: c[k] for k in ("id", "subject", "status", "level", "limitations")},
                        "reference": reference(f"/claims/{j}")}
                       for j, c in enumerate(record["claims"]) if c["subject"] in subjects],
        })
    return {"record": record_name, "record_sha256": digest(canonical(record)), "scope": status["scope"],
            "freshness": "live checks limited to recorded recipient snapshots; remote origins not refreshed" if live else "historical replay; present applicability not checked",
            "structure_and_bytes_checked": True, "semantic_truth_certified": False, "implementation_verified": False,
            "limitations": "READY means assessment ready to render; transfer remains a proposal. This index establishes no implementation, acceptance or permission. Claims retain recorded status, not independent semantic verification. Consult the original ledger and request scope; an empty unresolved list is not approval.",
            "resources": "unavailable; not recorded by this schema", "pairs": pairs}


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


REVIEW_FIELDS = ("gates", "legal", "donor_risks", "re_claims", "hooks", "doubt", "review")


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
    if "review" in fields and ledger.get("review") is not None:
        review = ledger["review"]
        lines.append(f"- REVIEW: {text(review['level'])}; artifact {text(review['artifact'])} sha256 {text(review['sha256'])}; strongest disconfirming: {text(review['disconfirming'])}; checked: {'yes' if review['checked'] else 'no'}")
    return lines


def render_ladder(record, decision):
    """The evidence-ladder table of the claims a verdict rests on (references/output-template.md)."""
    rows = {c["id"]: c for c in record["claims"]}
    lines = ["", "Evidence ladder (claims this verdict rests on):", "", "| Claim | Subject | Level | Status | Evidence | Run | Claim text |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for ident in dict.fromkeys([*decision["claims"], *decision.get("recipient_claims", [])]):
        c = rows[ident]
        lines.append(f"| {text(ident)} | {text(c['subject'])} | {text(c['level'].upper())} | {text(c['status'])} | {text(', '.join(c['evidence']) or 'none')} | {text(c.get('execution', '—'))} | {text(c['text'])} |")
    return lines + [""]


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
                lines.append(f"- Coverage: {text('; '.join(value['examined']))}; refutation targets: {text('; '.join(refutation_text(x) for x in value['refutation_targets']))}")
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
        lines.extend(render_ladder(record, decision))
        common = common_reviews[item["source"]]
        if common:
            lines.append(f"- Common review basis: {', '.join(common)} in shared donor evidence {item['source']} above applies to this pair.")
        lines.extend(render_review_fields(ledger, [field for field in REVIEW_FIELDS if field not in common]))
        heading = decision["result"] + (f" (promising: {decision['promising_check']})" if decision.get("promising_check") else "")
        lines.extend(["", f"<!-- aa:verdict:{ident} -->", f"### {text(heading)}", "", text(decision["summary"]), "", f"Whole tool: {text(decision['whole_tool'])}. Mechanism value: {text(decision['mechanism_value'])}/3.", f"Evidence confidence: {text(decision['confidence_level'])} — {text(decision['confidence'])}."])
        flag, part, _ = legal_basis(ledger["legal"], decision)
        if part is not None:
            lines.append(f"Legal basis for transfer: part {text(part['id'])} ({text(flag)}, {text(part['route'])}) — {text(part['part'])}; {text(part['basis'])}. Whole-tool legal flag: {text(ledger['legal']['flag'])}.")
        waived = [row for row in (ledger["legal"], *ledger["legal"].get("parts", [])) if row.get("waiver")]
        for row in waived:
            lines.append(f"Licence waiver: {text(row.get('id', 'whole tool'))} UNKNOWN licence treated as YELLOW by {text(row['waiver']['by'])} on {text(row['waiver']['date'])}: {text(row['waiver']['text'])}")
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


# Recipient path rules are data, never bundled authority. A rules file may pin the recipient file it
# was derived from (`source.path` + LF-normalised `source.sha256_lf`); a changed, missing or unchecked
# source fails closed. Classification never grants edit authorization.
PATH_RULE_LISTS = ("governed_prefixes", "governed_exact", "measurement_dependencies",
                   "policy_prefixes", "preflight_self", "documentation_prefixes", "test_suffixes")
FAIL_CLOSED = {"stale", "missing", "unchecked"}


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


def normalized_rules(rules):
    require(isinstance(rules, dict) and {"revision", *PATH_RULE_LISTS} <= set(rules) <= {"revision", "source", "derived_from", *PATH_RULE_LISTS}, "complete explicit path rules required")
    require(nonempty(rules["revision"]), "path rules require a revision")
    normalized = {}
    for key in PATH_RULE_LISTS:
        values = rules[key]
        require(isinstance(values, list) and all(isinstance(x, str) and x for x in values), "path rule must be a text list: " + key)
        if key == "test_suffixes":
            require(all(x.startswith(".") and "/" not in x and "\\" not in x for x in values), "invalid test suffix")
            normalized[key] = tuple(values)
        else:
            normalized[key] = tuple(relative_rule_path(x, key.endswith("_prefixes")) for x in values)
    return normalized


def recipient_path_class(path, rules):
    """Classify one path under explicit rules, in the pinned preflight's attribution order."""
    normalized = normalized_rules(rules)
    p = relative_rule_path(path)
    governed = not p.endswith(normalized["test_suffixes"]) and (
        p in normalized["governed_exact"] or p.startswith(normalized["governed_prefixes"]))
    reason = None
    if governed:
        category, safe = "governed", False
    elif p.startswith(normalized["policy_prefixes"]):
        category, safe = "freeze-policy-drift", False
    elif p in normalized["preflight_self"]:
        # The recipient's guard may exempt its own files from drift reports; that is not permission to edit it.
        category, safe = "freeze-checker", False
        reason = "Edits to the freeze checker can weaken the guard itself; they need the recipient owner's explicit approval."
    elif p in normalized["measurement_dependencies"]:
        category, safe = "measurement-dependency", False
    elif p.startswith(normalized["documentation_prefixes"]):
        category, safe = "docs", True
    else:
        category, safe = "ungoverned-needs-disposition", False
    result = {"path": p, "pin": rules["revision"], "class": category, "safe_to_change": safe,
              "authorization": "not-granted; classification is a planning hint under the stated rules"}
    if reason:
        result["reason"] = reason
    return result


def check_rules_source(rules, root=None):
    """Compare the rules' pinned recipient source with the file on disk (CRLF normalised to LF)."""
    source = rules.get("source")
    if source is None:
        return {"status": "caller-attested", "warning": "Rules carry no pinned source; the caller vouches that they match the live recipient."}
    strings(source, ("path", "sha256_lf"), "rules.source")
    require(SHA256.fullmatch(source["sha256_lf"]), "rules.source.sha256_lf must be 64 lowercase hex")
    info = {"path": source["path"], "expected_sha256_lf": source["sha256_lf"]}
    if root is None:
        return {**info, "status": "unchecked", "warning": f"Rules are pinned to {source['path']}; supply --root to compare them with the live file. Results fail closed until then."}
    target = contained(Path(root), relative_rule_path(source["path"]))
    if not target.is_file():
        return {**info, "status": "missing", "warning": f"Pinned rules source {source['path']} is absent under {Path(root).resolve()}; results fail closed."}
    observed = digest(target.read_bytes().replace(b"\r\n", b"\n"))
    if observed != source["sha256_lf"]:
        return {**info, "observed_sha256_lf": observed, "status": "stale",
                "warning": f"{source['path']} differs from the file these rules were derived from; re-derive the rules from the live file. Results fail closed."}
    return {**info, "observed_sha256_lf": observed, "status": "current", "warning": ""}


def classify_paths(paths, rules, root=None):
    freshness = check_rules_source(rules, root)
    results = []
    for path in paths:
        result = recipient_path_class(path, rules)
        if freshness["status"] in FAIL_CLOSED:
            result = {**result, "pinned_class": result["class"], "class": "rules-not-current", "safe_to_change": False}
        results.append(result)
    return {"rules_revision": rules["revision"], "freshness": freshness, "results": results}


def profile_path_class(path, profile, root=None):
    """Classify under a profile's bundled dated rules; never current authority without a matching root."""
    report = classify_paths([path], load_path_rules(profile_path_rules_file(profile)), root)
    return {**report["results"][0], "freshness": report["freshness"]["status"]}


def append_outcome(record_path, item_id, result, ledger_path, receipt=None, reason=None):
    """SKILL.md §8 outcome log: append an implemented plan's acceptance-test result next to the original verdict,
    mechanism value and confidence. Write-only: it never executes anything and never reads earlier ledger lines,
    and the line is calibration data, never an input to a fresh judgment (§0.8)."""
    record_path = Path(record_path)
    record = load(record_path)
    # The recipient has changed since the assessment (that is the point), so replay the record historically.
    errors = validate(record, record_path.resolve().parent, live=False)
    require(not errors, "; ".join(errors))
    require(result in OUTCOME_RESULTS, f"outcome result must be one of {', '.join(OUTCOME_RESULTS)}")
    item = next((x for x in record["items"] if x["id"] == item_id), None)
    require(item is not None and item["state"] == "READY", f"item {item_id} is not a READY pair in this record")
    decision = item["decision"]
    require(decision["result"] in LIVE_RESULTS, f"item {item_id} is {decision['result']}: an outcome records the acceptance test of a transfer plan")
    event = {"ts": now(), "kind": "outcome", "record_sha256": digest(canonical(record)), "item": item_id, "source": item["source"],
             "recipient": item["recipient"], "result": decision["result"], "mechanism_value": decision["mechanism_value"],
             "confidence_level": decision["confidence_level"], "acceptance_test": decision["transfer"]["verification"], "outcome": result,
             "use": "calibration data for reviewing this skill; never an input to a fresh judgment (SKILL.md §0.8)"}
    if result in {"passed", "failed"}:
        require(receipt is not None, f"{result} needs --receipt: the raw acceptance-test output")
    if receipt is not None:
        receipt = Path(receipt)
        require(receipt.is_file() and not receipt.is_symlink(), "receipt must be a regular local file")
        data = receipt.read_bytes()
        event["receipt"] = {"path": str(receipt.resolve()), "sha256": digest(data), "bytes": len(data)}
    if result in {"skipped", "blocked", "not-run"}:
        require(nonempty(reason), f"{result} needs --reason")
    if reason is not None:
        require(nonempty(reason), "reason must be nonempty text")
        event["reason"] = reason
    path = Path(ledger_path)
    require(not path.is_symlink(), "outcome ledger is a link")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Append only: earlier lines are never read, so no past outcome can steer the next judgment.
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("directory"); p.add_argument("--source", action="append", required=True)
    p.add_argument("--recipient", action="append", required=True, help="id=profile; a bare id is `unspecified` and gets no verdict until a routing row records its profile")
    sub.add_parser("routing-index", help="print every installed profile's routing signals (read this, then only the chosen profiles)")
    p = sub.add_parser("outcome", help="append an implemented plan's acceptance-test result next to its verdict; writes only")
    p.add_argument("record"); p.add_argument("--item", required=True); p.add_argument("--result", choices=OUTCOME_RESULTS, required=True)
    p.add_argument("--receipt", help="raw acceptance-test output (required for passed/failed)"); p.add_argument("--reason"); p.add_argument("--ledger", required=True)
    p = sub.add_parser("capture"); p.add_argument("directory"); p.add_argument("file"); p.add_argument("--subject", required=True); p.add_argument("--revision", required=True)
    p = sub.add_parser("snapshot"); p.add_argument("root"); p.add_argument("--path", action="append", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("score"); p.add_argument("--rubric", choices=sorted(known_rubrics()), required=True); p.add_argument("--components", nargs=4, type=int, required=True); p.add_argument("--penalty", type=int, default=0)
    p = sub.add_parser("doubt"); p.add_argument("verdict", choices=sorted(RESULTS)); p.add_argument("--score", type=int); p.add_argument("--live", action="store_true", help="a transfer plan is proposed"); p.add_argument("--salvage-found", action="store_true", help="any salvage lens found something"); p.add_argument("--consequential", action="store_true"); p.add_argument("--uncertain", action="store_true")
    for name in ("validate", "status", "handoff", "render", "check-output", "history"):
        p = sub.add_parser(name); p.add_argument("record")
        p.add_argument("--historical", action="store_true", help="Do not check live recipient; replay only, not current decision validation")
        if name == "render": p.add_argument("--output", required=True)
        if name == "handoff": p.add_argument("--output", help="New JSON filename inside the run directory; default stdout")
        if name == "check-output": p.add_argument("output")
        if name == "history": p.add_argument("--ledger", required=True); p.add_argument("--published-report", required=True)
    p = sub.add_parser("classify-path"); p.add_argument("path", nargs="+")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--rules", help="caller-owned path-rules JSON")
    group.add_argument("--profile", help="use references/profiles/<profile>-path-rules.json (a dated pin)")
    p.add_argument("--root", help="recipient root; compares the rules' pinned source file with the live file")
    p = sub.add_parser("invalidate"); p.add_argument("file"); p.add_argument("id"); p.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            init_run(args.directory, args.source, args.recipient); print("Created QUEUED run; no source evaluated.")
        elif args.command == "routing-index":
            # UTF-8 regardless of the console code page: profiles use arrows and dashes.
            sys.stdout.flush()
            sys.stdout.buffer.write(routing_index().encode("utf-8"))
            sys.stdout.buffer.flush()
        elif args.command == "outcome":
            append_outcome(args.record, args.item, args.result, args.ledger, args.receipt, args.reason)
            print("Appended outcome next to the original verdict; it is calibration data, never an input to a fresh judgment.")
        elif args.command == "capture":
            print(json.dumps(capture(args.directory, args.file, args.subject, args.revision), ensure_ascii=False, indent=2))
        elif args.command == "snapshot":
            save(args.output, snapshot(args.root, args.path)); print("Snapshot saved; scope is explicit selected files.")
        elif args.command == "score":
            print(score(args.rubric, args.components, args.penalty))
        elif args.command == "doubt":
            print(doubt_depth(args.verdict, args.score, args.live, args.consequential, args.uncertain, salvage_found=args.salvage_found))
        elif args.command == "classify-path":
            rules = load_path_rules(args.rules if args.rules else profile_path_rules_file(args.profile))
            report = classify_paths(args.path, rules, args.root)
            print(json.dumps(report, indent=2))
            if report["freshness"]["status"] in FAIL_CLOSED:
                print(f"WARNING: path rules are not current ({report['freshness']['status']}): {report['freshness']['warning']}", file=sys.stderr)
                return 1
        elif args.command == "invalidate":
            save(args.output, invalidate_lessons(load(args.file), args.id)); print("Changed lesson and descendants marked stale.")
        else:
            root = Path(args.record).resolve().parent
            record = load(args.record)
            if args.command == "handoff":
                index = handoff(record, root, not args.historical, Path(args.record).name)
                output = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
                if args.output:
                    require(Path(args.output).name == args.output, "handoff output must be a filename inside the run directory")
                    target = contained(root, args.output)
                    # Exclusive creation preserves earlier reports/indexes, including on retry.
                    with target.open("x", encoding="utf-8", newline="\n") as stream:
                        stream.write(output)
                    print(f"Wrote recovery index {target}; record remains authoritative.")
                else:
                    print(output, end="")
                return 0
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
                # Carries value and confidence so a later acceptance-test outcome can sit next to them (SKILL.md §8 outcome log).
                event = {"ts": now(), "record_sha256": digest(canonical(record)), "decisions": [{"item": x["id"], "source": x["source"], "recipient": x["recipient"], "result": x["decision"]["result"], "mechanism_value": x["decision"]["mechanism_value"], "confidence_level": x["decision"]["confidence_level"]} for x in record["items"] if x["state"] == "READY"]}
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
