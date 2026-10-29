"""Authoring helpers: stamp file hashes, scaffold candidate stubs, write review packets.

Standard library only. They read the record and files under its run directory, write only new files
outside the package, never run donor code, never fetch anything and never make a record pass.
"""
import html
from pathlib import Path
import re

import frankenmine as fm

HEX64 = re.compile(r"^[a-f0-9]{64}$")
# Schema errors that `stamp` repairs: a missing or empty hash, or a missing evidence revision.
STAMPABLE = re.compile(r"^\$\.(?:evidence|supporting_evidence|tests|receipts|artifacts|review)[^:]*"
                       r"(?:: missing (?:sha256|oracle_sha256|raw_sha256|revision)"
                       r"|\.(?:sha256|oracle_sha256|raw_sha256): pattern mismatch)$")
SEAM_PROMPTS = {
    "exports_consumers": "what the unit exports and who consumes it in the product",
    "closure": "what it imports, and what the product keeps, replaces or excludes",
    "initialization": "import-time effects, registries and initialization order",
    "state_transactions": "state it owns or mutates, and transaction boundaries",
    "resources_lifetime": "files, sockets, handles and their lifetime",
    "concurrency_cancellation": "threads, async, cancellation and reentrancy",
    "errors_retries": "error vocabulary, partial failure and retries",
    "serialization": "formats, versions and canonical encodings",
    "permissions_effects": "permissions, network, process and filesystem effects",
    "tests": "the acceptance test and negative control that cover the seam",
    "licensing": "licence, notices and obligations for this unit"}
PROTOCOL_FIELDS = ("version_rejection", "authentication", "idempotency", "reordering_duplicates", "backpressure",
                   "shutdown_restart_identity", "performance_budget")
WITHHELD = ("decision choice and rationale", "alternatives' tradeoff prose", "lesson stage, disposition and rationale",
            "the review block and any earlier findings", "unresolved items", "the helper's readiness verdict")


def todo(prompt):
    return fm.SCAFFOLD_MARK + ": " + prompt


def stamp(source, output):
    """Fill every missing file hash the record references into a NEW record.

    A hash that is already recorded is never rewritten: if the file changed, that is a finding (a changed
    oracle or snapshot needs a new decision, not a new hash), so it is reported and the exit code is 2."""
    source = Path(source)
    run = fm.load_json(source)
    if not isinstance(run, dict):
        raise ValueError("a run record must be a JSON object")
    root = source.parent
    filled, mismatches, unreadable = [], [], []

    def fill(obj, path_key, hash_key, label):
        if not isinstance(obj, dict) or not isinstance(obj.get(path_key), str):
            return
        try:
            data = fm.local_bytes(root, obj[path_key])
        except (OSError, ValueError) as exc:
            unreadable.append(label + ": " + str(exc))
            return
        actual, recorded = fm.digest(data), obj.get(hash_key)
        if not isinstance(recorded, str) or not HEX64.match(recorded):
            obj[hash_key] = actual
            filled.append(label)
        elif recorded != actual:
            mismatches.append(label + ": recorded " + recorded[:12] + "..., file now " + actual[:12] + "...; not rewritten")

    def items(key):
        value = run.get(key)
        return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []

    donors = {d.get("id"): d for d in items("donors")}
    for e in items("evidence"):
        donor = donors.get(e.get("donor"), {})
        if not e.get("revision") and isinstance(donor.get("revision"), str):
            e["revision"] = donor["revision"]
            filled.append("evidence " + str(e.get("id")) + " revision")
        fill(e, "snapshot", "sha256", "evidence " + str(e.get("id")))
    for e in items("supporting_evidence"):
        fill(e, "snapshot", "sha256", "supporting evidence " + str(e.get("id")))
    for t in items("tests"):
        fill(t, "oracle", "oracle_sha256", "test " + str(t.get("id")) + " oracle")
    for r in items("receipts"):
        fill(r, "raw_output", "raw_sha256", "receipt " + str(r.get("id")) + " raw output")
        for a in r.get("artifacts", []) if isinstance(r.get("artifacts"), list) else []:
            fill(a, "path", "sha256", "receipt " + str(r.get("id")) + " artifact " + str(a.get("path")))
    for a in items("artifacts"):
        fill(a, "path", "sha256", "artifact " + str(a.get("path")))
    review = run.get("review")
    if isinstance(review, dict):
        fill(review.get("report"), "path", "sha256", "review report")
    fm.write_new(output, fm.encode(run))
    ok = not mismatches and not unreadable
    return dict(status="stamped" if ok else "stamped-with-findings", ok=ok, path=str(output), filled=filled,
                mismatches=mismatches, unreadable=unreadable,
                note="Only missing hashes are filled; run check on the new record. Recorded hashes are never rewritten.")


def scaffold(source, output, donor, unit, route, ident, source_language=None, basis=None):
    """Append a candidate stub whose every judgement is a TODO(scaffold) placeholder; the record stays blocked."""
    source = Path(source)
    run = fm.load_json(source)
    # Hashes and evidence revisions that stamp will fill may still be missing; anything else must be valid.
    shape = [e for e in fm.record_schema_errors(run) if not STAMPABLE.search(e)]
    if shape:
        raise ValueError("Cannot scaffold into a malformed record: " + "; ".join(shape[:5]))
    routes = fm.load_json(fm.PACKAGE / fm.SCHEMAS[fm.CURRENT_SCHEMA])["$defs"]["candidate"]["properties"]["route"]["enum"]
    if run["schema_version"] != fm.CURRENT_SCHEMA:
        raise ValueError("scaffold writes schema " + fm.CURRENT_SCHEMA + " fields; upgrade the record first "
                         "(references/contracts.md)")
    if route not in routes:
        raise ValueError("route must be one of " + ", ".join(routes))
    donors = {d["id"]: d for d in run["donors"]}
    if donor not in donors:
        raise ValueError("unknown donor " + donor)
    if ident in {x["id"] for g in fm.GROUPS for x in run.get(g, [])}:
        raise ValueError("ID already used: " + ident)
    languages = donors[donor]["languages"]
    language = source_language or (languages[0] if languages else todo("source language"))
    target = run["brief"]["target_language"]
    candidate = dict(
        id=ident, donor=donor,
        evidence=[e["id"] for e in run["evidence"] if e["donor"] == donor and e["path"] == unit],
        discovery=[d["id"] for d in run["discoveries"] if d["donor"] == donor],
        need=[todo("requirement ID this part serves")], unit=unit, route=route, phase="candidate",
        implementation="not-started",
        closure=[todo("retained dependencies as {name, pin, category, disposition}, or none: <reason>")],
        touches=[todo("state, policy, resource or interface key")],
        seam=dict({k: todo(v) for k, v in SEAM_PROMPTS.items()}, evidence=[]),
        rights=dict(status="unknown", route="unresolved", category="unknown", license=todo("licence of this unit"),
                    unit=unit, evidence=[], obligations=[], rationale=todo("why this rights route fits")),
        source_language=language, target_language=target,
        owner=todo("authoritative owner"), caller=todo("caller in the product"),
        approval_boundary=todo("what this part may and may not do without approval"),
        contract=todo("the product contract this part meets"), intentional_changes=todo("deliberate changes"),
        recovery=todo("failure and recovery"), maintenance=todo("maintenance owner"),
        update_strategy=todo("how donor updates are reviewed"),
        acceptance="accept-" + ident, negative_control="control-" + ident,
        falsifier=todo("observation that would disprove the selection"),
        alternative=todo("simplest alternative considered"))
    if route == "reimplementation" and basis:
        candidate["basis"] = basis
    deltas = []
    if route in fm.REUSE_ROUTES and fm.language_key(language) != fm.language_key(target):
        deltas = [dict(dimension=d, status="unknown", donor_semantics=todo("donor behaviour"),
                       target_semantics=todo("target behaviour"),
                       conversion=todo("conversion; for not-applicable keep only reason as n/a: <reason>"),
                       test=todo("test ID"), reason=todo("why")) for d in fm.SEMANTIC_DIMENSIONS]
        candidate["deltas"] = deltas
    if route in fm.PROTOCOL_ROUTES:
        candidate["protocol"] = {k: todo(k.replace("_", " ")) for k in PROTOCOL_FIELDS}
    run["candidates"].append(candidate)
    run["unresolved"].append("Scaffolded candidate " + ident + " is unfilled: replace every " + fm.SCAFFOLD_MARK +
                             " value, then delete this line.")
    fm.write_new(output, fm.encode(run))
    return dict(status="scaffolded", ok=True, path=str(output), candidate=ident, deltas=len(deltas),
                note="The record stays blocked until every " + fm.SCAFFOLD_MARK + " value is replaced; scaffolding "
                     "never makes a record pass.")


def inert(value):
    return html.escape(" ".join(str(value).split()), quote=False)


def review_packet(source, output):
    """Write what a fresh reviewer needs (brief, evidence, oracles, alternatives, proposed parts) and nothing
    of the author's conclusions. The reviewer's saved report is later cited as review.report."""
    source = Path(source)
    run = fm.load_json(source)
    shape = fm.record_schema_errors(run)
    if shape:
        raise ValueError("Cannot build a review packet from a malformed record: " + "; ".join(shape[:5]))
    out = Path(output)
    fm.refuse_package(out)
    if out.exists():
        raise ValueError("packet directory already exists; choose a new one: " + str(out))
    out.mkdir(parents=True)
    root, files, seen = source.parent, [], set()

    def copy(rel, role):
        if rel in seen:
            return
        seen.add(rel)
        data = fm.local_bytes(root, rel)
        fm.write_new_bytes(out / "files" / rel, data)
        files.append(dict(path="files/" + rel, role=role, sha256=fm.digest(data)))

    for e in run["evidence"]:
        copy(e["snapshot"], "source evidence " + e["id"])
    for e in run.get("supporting_evidence", []):
        if "snapshot" in e:
            copy(e["snapshot"], "supporting evidence " + e["id"])
    for t in run["tests"]:
        copy(t["oracle"], "oracle for " + t["id"])

    brief = run["brief"]
    lines = ["# Design review packet: " + inert(run["id"]), "",
             "You are a fresh reviewer. Judge whether the evidence supports each proposed part, where a simpler "
             "alternative (the best existing solution or a minimal fresh build) wins, and which rights, seam or "
             "interaction claims are unsupported. Record each finding with a severity (Critical, Important or Minor) "
             "and the evidence for it, using REVIEW-TEMPLATE.md. Files are under files/ with their SHA-256.", "",
             "The author's decision, rationale and readiness verdict are withheld on purpose: " + ", ".join(WITHHELD) +
             ".", "", "## Brief", "", "- Outcome: " + inert(brief["outcome"]), "- Users: " + inert(brief["users"]),
             "- Question: " + inert(brief.get("question", "not recorded")),
             "- Target language: " + inert(brief["target_language"])]
    lines += ["- Requirement " + inert(r["id"]) + ": " + inert(r["criterion"]) for r in brief["requirements"]]
    lines += ["- Non-goal: " + inert(x) for x in brief["non_goals"]]
    lines += ["- Constraint: " + inert(x) for x in brief["constraints"]]
    lines += ["", "## Donors", ""]
    lines += ["- " + inert(d["id"]) + " " + inert(d["url"]) + " @ " + inert(d["revision"]) + " (" +
              inert(", ".join(d["languages"]) or "languages not recorded") + "): " + inert(d["status"]) + "; scope: " +
              inert(d["scope"]) + "; blind spots: " + inert("; ".join(d["blind_spots"]) or "none recorded")
              for d in run["donors"]]
    lines += ["", "## Evidence", ""]
    lines += ["- " + inert(e["id"]) + " [" + inert(e["kind"]) + "] donor " + inert(e["donor"]) + ", " + inert(e["path"]) +
              " lines " + str(e["start_line"]) + "-" + str(e["end_line"]) + "; file files/" + inert(e["snapshot"]) +
              "; " + inert(e["scope"]) + " (limits: " + inert(e["limitations"]) + ")" for e in run["evidence"]]
    for e in run.get("supporting_evidence", []):
        lines.append("- " + inert(e["id"]) + " [" + inert(e["kind"]) + "] " +
                     inert(e.get("url") or ("files/" + e["snapshot"] if "snapshot" in e else "no locator")) + "; " +
                     inert(e["scope"]) + " (limits: " + inert(e["limitations"]) + ")")
    if run.get("discovery_searches"):
        lines += ["", "## Donor searches", ""]
        lines += ["- " + inert(s["id"]) + " " + inert(s["date"]) + " " + inert(s["source"]) + "; considered " +
                  inert(", ".join(s["considered"])) for s in run["discovery_searches"]]
    lines += ["", "## Lessons claimed by the author (check them against the evidence)", ""]
    lines += ["- " + inert(x["id"]) + " (" + inert(x["donor"]) + ", " + inert(x["direction"]) + "): " +
              inert(x["problem"]) + " -> " + inert(x["mechanism"]) + "; invariant: " + inert(x["invariant"]) +
              "; need: " + inert(x["target_need"]) + "; evidence: " + inert(", ".join(x["evidence"])) +
              "; falsifier: " + inert(x["falsifier"]) for x in run["discoveries"]]
    lines += ["", "## Proposed parts", ""]
    for c in run["candidates"]:
        if c["phase"] not in ("selected", "design-reviewed"):
            continue
        lines.append("- " + inert(c["id"]) + ": donor " + inert(c["donor"]) + " unit " + inert(c["unit"]) + " via " +
                     inert(c["route"]) + (" from " + inert(c["basis"]) if "basis" in c else "") + "; needs " +
                     inert(", ".join(fm.needs_of(c))) + "; touches " + inert(", ".join(c.get("touches", [])) or "none") +
                     "; evidence " + inert(", ".join(c["evidence"])) + "; contract: " + inert(c["contract"]) +
                     "; rights: " + inert(c["rights"]["route"]) + " / " + inert(c["rights"].get("category", "?")) +
                     " (" + inert(c["rights"]["license"]) + ")")
    lines += ["", "## Ownership and interactions", ""]
    lines += ["- " + inert(x["key"]) + " -> " + inert(x["owner"]) for x in run["ownership"]]
    lines += ["- " + inert(" / ".join(x["components"])) + ": " + inert(x["status"]) + " (test " +
              inert(x.get("test", "none")) + ")" for x in run["interactions"]]
    lines += ["", "## Alternatives to compare", ""]
    for a in run["alternatives"]:
        lines.append("- " + inert(a["kind"]) + ": " + inert(a["name"]) + "; evidence " + inert(", ".join(a["evidence"])) +
                     ("; dimensions " + inert(", ".join(d["name"] + " " + str(d["value"]) + " (" + d["direction"] +
                                                        " is better)" for d in a["dimensions"]))
                      if a.get("dimensions") else ""))
    lines += ["", "## Frozen oracles", ""]
    lines += ["- " + inert(t["id"]) + " (" + inert(t["purpose"]) + "): " + inert(t["spec"]) + "; oracle files/" +
              inert(t["oracle"]) + " sha256 " + t["oracle_sha256"] for t in run["tests"]]
    packet = "\n".join(lines) + "\n"
    fm.write_new(out / "PACKET.md", packet)
    fm.write_new(out / "REVIEW-TEMPLATE.md", "\n".join([
        "Reviewer: <your name or agent and model>",
        "Independence: <fresh-context-same-model | different-model | human>",
        "Packet: PACKET.md sha256 " + fm.digest(packet.encode("utf-8")), "",
        "Findings (one per line: severity Critical, Important or Minor; the claim; the evidence):", "- ", "",
        "For each proposed part: does the evidence support it? Where does a simpler alternative win?", "- ", ""]))
    fm.write_new(out / "packet.json", fm.encode(dict(
        format="frankenmine-review-packet-1", run_id=run["id"], source=str(source.resolve()), files=files,
        withheld=list(WITHHELD), packet_sha256=fm.digest(packet.encode("utf-8")))))
    return dict(status="review-packet", ok=True, path=str(out), files=len(files),
                packet_sha256=fm.digest(packet.encode("utf-8")),
                next="Give this folder to a fresh reviewer. Save its filled report inside the run root and cite it as "
                     "review.report {path, sha256} with the reviewer, independence level and findings.")
