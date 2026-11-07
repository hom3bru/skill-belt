"""Schema-2 intake/measurement checks. Reads declared captures; never fetches or runs donors."""
from __future__ import annotations

import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

ROLES = {"repo": ("map", "entrypoint", "callers", "configuration", "tests"),
         "paper": ("method", "results", "limitations")}
KIND_ALIASES = {"repository": "repo", "git-repo": "repo", "github-repo": "repo", "research-paper": "paper",
                "arxiv-paper": "paper", "social-media-post": "social-post"}
SURFACES = {"full-text", "selected-source", "abstract", "metadata", "media"}
REASONS = {"proposal", "unresolved", "research-lead", "no-benefit", "assumption-mismatch",
           "net-burden", "policy", "already-covered"}
NEGATIVE_REASONS = {"research-lead", "no-benefit", "assumption-mismatch", "net-burden", "policy"}
PAYLOAD_KEYS = ("metric", "unit", "workload", "denominator", "sample_size", "baseline", "candidate")
METRIC_WORDS = re.compile(r"\b(?:costs?|cheaper|expensive|latency|faster|slower|tokens?|bytes?|memory|throughput|savings?|saves?|speed|improvement|accuracy)\b", re.I)
NUMBER_UNIT = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*(%|USD|dollars?|ms|milliseconds?|seconds?|tokens?|bytes?)\b|\$\s*(\d+(?:\.\d+)?)", re.I)
# A percent sign has no trailing word boundary when followed by whitespace.
PERCENT = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*%")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def fields(row, names, label):
    need(isinstance(row, dict), f"{label} must be an object")
    for name in names:
        need(text(row.get(name)), f"{label}.{name} needs text")


def unique(rows, label):
    need(isinstance(rows, list), f"{label} must be a list")
    result = {}
    for row in rows:
        need(isinstance(row, dict) and text(row.get("id")), f"{label} needs IDs")
        need(row["id"] not in result, f"duplicate {label} ID")
        result[row["id"]] = row
    return result


def read_refs(ids, context, label, subjects=None, required=True):
    need(isinstance(ids, list) and (ids or not required), f"{label} needs evidence references")
    need(all(isinstance(i, str) and i in context["evidence"] for i in ids) and len(ids) == len(set(ids)), f"{label} has unknown/duplicate evidence")
    rows = [context["evidence"][i] for i in ids]
    need(all(r["read_scope"] != "unread" for r in rows), f"{label} cites unread evidence")
    if subjects is not None:
        need(all(r["subject"] in subjects for r in rows), f"{label} evidence belongs to another source/recipient")
    return rows


def normal_url(url):
    need(text(url), "link URL needs text")
    value = html.unescape(url).strip().rstrip(".,;!")
    while value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1]
    parts = urlsplit(value)
    need(parts.scheme in {"http", "https"} and parts.netloc, "link needs an HTTP(S) URL")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, parts.fragment))


def urls(data, base=None):
    body = data.decode("utf-8-sig", errors="replace")
    found = re.findall(r"https?://[^\s<>\[\]\"']+", html.unescape(body))
    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            found.extend(value for key, value in attrs if key in {"href", "src"} and value)
    Links().feed(body)
    found.extend(re.findall(r"!?\[[^\]]*\]\(([^\s)]+)", body))
    found.extend(re.findall(r"(?m)^\s*\[[^\]]+\]:\s*(\S+)", body))
    result = set()
    for value in found:
        if value.startswith("#") or urlsplit(value).scheme not in {"", "http", "https"}:
            continue
        try:
            result.add(normal_url(urljoin(base, value) if base else value))
        except ValueError:
            pass
    return result


def _bytes(context, root, path, contained):
    reader = context.get("read_bytes")
    return reader(path) if reader else contained(root, path).read_bytes()


def _usable_capture(evidence, context, root, contained):
    cache = context["_usable"]
    key = (evidence["path"], evidence["sha256"])
    if key not in cache:
        cache[key] = _usable(_bytes(context, root, evidence["path"], contained))
    return cache[key]


def capture_urls(evidence, source, root, contained, context=None):
    origin = evidence["origin"]
    if not origin.startswith(("http://", "https://")):
        origin = source.get("resolved_locator", source["locator"])
        # Repository-root relative references are resolved within that root, not its owner.
        if KIND_ALIASES.get(source["kind"], source["kind"]) == "repo" and origin.startswith(("http://", "https://")):
            origin = origin.rstrip("/") + "/"
    origin = origin if origin.startswith(("http://", "https://")) else None
    if context is None:
        return urls(contained(root, evidence["path"]).read_bytes(), origin)
    key = (evidence["path"], evidence["sha256"], source["id"], origin)
    cache = context["_urls"]
    if key not in cache:
        cache[key] = frozenset(urls(_bytes(context, root, evidence["path"], contained), origin))
    return cache[key]


def seed(inputs, digest, canonical):
    return {"schema_version": 1, "inputs_sha256": digest(canonical(inputs)), "artifacts": [
        {"id": s["id"], "coverage": {}, "links": [], "named_works": [], "lookups": [], "attempts": [],
         "discovery": "open", "background": {"status": "pending", "note": ""},
         "retrieval": {"available_methods": [], "exhausted": False, "next_step": ""}}
        for s in inputs["sources"]],
        "recording": {"state": "pending", "path": "run.json", "sha256": None, "index": None}, "lineage": []}


def _usable(data):
    body = data.decode("utf-8-sig", errors="replace").strip()
    if not body:
        return False
    if body.lower() in {"forbidden", "access denied", "not found", "sign in", "log in", "login required"}:
        return False
    visible = " ".join(html.unescape(re.sub(r"<[^>]*>", " ", body)).lower().split())
    if len(visible) < 120 and re.fullmatch(r"(?:(?:sign in|log in)\s*)+(?:to (?:continue|view this (?:post|page|content)))?[.!]?", visible):
        return False
    if len(visible) < 300 and re.match(r"^(?:[45]\d\d\s+)?(?:404\s+)?(?:not found|forbidden|bad gateway|service unavailable)\b", visible):
        return False
    try:
        row = json.loads(body)
        if isinstance(row, dict) and any(type(row.get(k)) is int and row[k] >= 400 for k in ("code", "status", "status_code")):
            return False
    except (ValueError, TypeError):
        pass
    return True


def _artifact(node, source, context, root, contained, outstanding):
    sid = source["id"]
    need(node.get("discovery") in {"open", "closed"}, f"{sid}: invalid discovery state")
    background = node.get("background")
    need(isinstance(background, dict) and background.get("status") in {"pending", "checked", "not-needed"}, f"{sid}: background status missing")
    if background["status"] != "pending":
        fields(background, ("note",), f"{sid}.background")
    else:
        outstanding.append(f"{sid}: background research not accounted for")
    if node["discovery"] != "closed":
        outstanding.append(f"{sid}: source discovery remains open")
    attempts = node.get("attempts")
    need(isinstance(attempts, list), f"{sid}: attempts must be a list")
    bad_receipts = set()
    methods = set()
    for attempt in attempts:
        fields(attempt, ("method", "url", "outcome", "note"), f"{sid}.attempt")
        need(attempt["outcome"] in {"content", "error", "stub", "not-found"}, "invalid retrieval outcome")
        read_refs(attempt.get("evidence"), context, "retrieval attempt", {sid})
        methods.add(attempt["method"])
        if attempt["outcome"] != "content":
            bad_receipts.update(attempt["evidence"])
    retrieval = node.get("retrieval")
    need(isinstance(retrieval, dict) and type(retrieval.get("exhausted")) is bool, f"{sid}: retrieval state missing")
    available = retrieval.get("available_methods")
    need(isinstance(available, list) and all(text(m) for m in available) and len(available) == len(set(available)), "available retrieval methods must be distinct")
    if retrieval["exhausted"]:
        need(len(methods) >= 2 and set(available) <= methods and available,
             "retrieval exhaustion needs distinct methods and all declared alternatives; one failed fetch is not exhaustion")
        fields(retrieval, ("next_step",), "exhausted retrieval")
    coverage = node.get("coverage")
    need(isinstance(coverage, dict), f"{sid}: coverage must be an object")
    for role, row in coverage.items():
        fields(row, ("state", "surface", "note"), f"{sid}.coverage.{role}")
        need(row["state"] in {"read", "not-applicable", "unknown"} and row["surface"] in SURFACES, "invalid coverage state/surface")
        evidence = read_refs(row.get("evidence"), context, f"{sid}.{role}", {sid}, row["state"] != "unknown")
        if row["state"] in {"read", "not-applicable"}:
            need(not set(row["evidence"]) & bad_receipts, "an error/stub retrieval cannot support a read")
            need(all(e.get("artifact_kind", "source") == "source" and _usable_capture(e, context, root, contained) for e in evidence),
                 "empty/error content cannot support a read")
            if role in {"method", "results", "limitations"}:
                need(row["surface"] not in {"abstract", "metadata"}, "abstract-only evidence cannot establish paper method/results/limitations coverage")
            if role == "body":
                need(row["surface"] != "metadata", "a metadata preview is not a body read")
    kind = KIND_ALIASES.get(source["kind"], source["kind"])
    missing_roles = [role for role in ROLES.get(kind, ("body",))
                     if coverage.get(role, {}).get("state") not in ({"read"} if role == "body" else {"read", "not-applicable"})]
    for role in missing_roles:
        outstanding.append(f"{sid}: {role} coverage unresolved")
    # All declared read source captures are inspected for links, not just an agent-chosen shortlist.
    captures = [e for e in context["evidence"].values() if e["subject"] == sid and e["read_scope"] != "unread"
                and e.get("artifact_kind", "source") == "source"]
    extracted = set().union(*(capture_urls(e, source, root, contained, context) for e in captures)) if captures else set()
    links = node.get("links")
    need(isinstance(links, list), f"{sid}: links must be a list")
    accounted = set()
    link_rows = []
    for edge in links:
        fields(edge, ("url", "resolved", "classification", "reason"), "link")
        original, resolved = normal_url(edge["url"]), normal_url(edge["resolved"])
        support = read_refs(edge.get("evidence"), context, "link parent", {sid})
        need(any(original in capture_urls(e, source, root, contained, context) for e in support), "link URL is absent from its cited parent capture")
        need(original not in accounted, f"{sid}: duplicate link edge; retain aliases/parents without duplicate edges")
        accounted.add(original)
        need(edge["classification"] in {"research", "non-research"}, "invalid link classification")
        child = edge.get("source")
        if edge["classification"] == "research":
            if child is None:
                outstanding.append(f"{sid}: unqueued linked artifact {edge['url']}")
            else:
                need(child in context["sources"], "link references an unknown queued source")
                target = context["sources"][child]
                aliases = [target["locator"], target.get("resolved_locator", target["locator"]), *target.get("aliases", [])]
                identities = set()
                for alias in aliases:
                    try:
                        identities.add(normal_url(alias))
                    except ValueError:
                        pass
                need(original in identities or resolved in identities, "linked source identity differs from original/resolved locator")
                a, b = urlsplit(original), urlsplit(resolved)
                if a._replace(fragment="") != b._replace(fragment=""):
                    resolution = read_refs(edge.get("resolution_evidence", []), context, "redirect resolution", {sid})
                    need(any({original, resolved} <= capture_urls(e, source, root, contained, context) for e in resolution),
                         "a changed link identity needs a captured original-to-final resolution receipt")
        else:
            need(child is None, "non-research edge must not silently hide a queued child")
        link_rows.append({"parent": sid, "url": edge["url"], "source": child, "classification": edge["classification"]})
    for value in sorted(extracted - accounted):
        outstanding.append(f"{sid}: unaccounted captured link {value}")
        link_rows.append({"parent": sid, "url": value, "source": None, "classification": "unaccounted"})
    lookups = unique(node.get("lookups"), "lookups")
    for lookup in lookups.values():
        fields(lookup, ("query", "method", "status", "note"), "lookup")
        need(lookup["status"] in {"found", "not-found", "blocked"}, "invalid lookup status")
        read_refs(lookup.get("evidence"), context, "lookup", {sid})
        matches = lookup.get("matches")
        need(isinstance(matches, list) and all(m in context["sources"] for m in matches), "lookup matches must be queued source IDs")
        if lookup["status"] == "found":
            need(matches, "a found lookup needs its queued matches")
    need(isinstance(node.get("named_works"), list), "named_works must be a list")
    for work in node["named_works"]:
        fields(work, ("name", "lookup"), "named work")
        if work["lookup"] not in lookups:
            outstanding.append(f"{sid}: named work {work['name']} has no recorded lookup")
        elif lookups[work["lookup"]]["status"] != "found":
            outstanding.append(f"{sid}: named work {work['name']} remains unresolved")
    if kind in {"social", "social-post", "post", "tweet"} and not any(e["classification"] == "research" for e in links) and not lookups:
        outstanding.append(f"{sid}: social source without resource links needs a recorded background/project lookup")
    return missing_roles, link_rows


def _lineage(intake, context, root, contained):
    for revision in intake["lineage"]:
        need(isinstance(revision, dict), "queue lineage entry must be an object")
        parents = {}
        for name in ("parent_record", "parent_inputs", "parent_intake"):
            descriptor = revision.get(name)
            fields(descriptor, ("path", "sha256"), "queue lineage")
            data = _bytes(context, root, descriptor["path"], contained)
            need(context["digest"](data) == descriptor["sha256"], "queue lineage snapshot hash differs")
            parents[name] = json.loads(data.decode("utf-8-sig"))
        old = parents["parent_record"]
        need(all(s["id"] in context["sources"] and context["sources"][s["id"]]["locator"] == s["locator"] for s in old["sources"]),
             "queue extension lost or replaced a previous source identity")
        need(all(r["id"] in context["recipients"] for r in old["recipients"]), "queue extension lost a selected recipient")
        for previous in old["items"]:
            current = context["items"].get(previous["id"])
            need(current is not None and all(current[k] == previous[k] for k in ("source", "recipient"))
                 and current["transitions"][:len(previous["transitions"])] == previous["transitions"],
                 "queue extension lost a previous pair or its state history")
        need(all(e["id"] in context["evidence"] and context["evidence"][e["id"]]["sha256"] == e["sha256"] for e in old["evidence"]),
             "queue extension lost or changed previous captured evidence")
        need(all(c["id"] in context["claims"] for c in old["claims"]), "queue extension lost previous claim IDs")


def _finite(value):
    try:
        return type(value) in {int, float} and math.isfinite(value)
    except OverflowError:
        return False


def measurement_statement(row):
    """Measured wording is derived from the payload, not attached to arbitrary prose."""
    need(row.get("status") in {"measured", "static"}, "canonical statement requires measured/static values")
    before, after = row["baseline"]["value"], row["candidate"]["value"]
    need(_finite(before) and _finite(after), "canonical statement needs finite values")
    if before:
        percent = (after - before) / abs(before) * 100
        direction = "decrease" if percent < 0 else "increase" if percent > 0 else "change"
        change = f"{abs(percent):.12g}% {direction}"
    else:
        change = "percentage undefined: zero baseline"
    if row["status"] == "measured":
        scope = f"{row['workload']}; {row['denominator']}; n={row['sample_size']}; revisions {row['baseline']['revision']} -> {row['candidate']['revision']}"
    else:
        scope = row["scope"]
    return f"{row['status'].capitalize()} {row['metric']} ({scope}): {before:.12g} {row['unit']} -> {after:.12g} {row['unit']} ({change})."


def _measurement(row, item, context, root, contained):
    fields(row, ("status", "metric", "unit", "scope"), "measurement")
    status = row["status"]
    need(status in {"unknown", "estimated", "reported", "static", "measured"}, "unknown measurement status")
    common = {"id", "status", "metric", "unit", "scope"}
    allowed = {"unknown": {"note", "next_test", "evidence", "value", "range", "baseline", "candidate", "receipt", "check"},
               "estimated": {"assumptions", "evidence", "range", "qualitative", "receipt"},
               "reported": {"value", "evidence", "note"}, "static": {"baseline", "candidate"},
               "measured": set(PAYLOAD_KEYS) | {"receipt", "check"}}
    need(set(row) <= common | allowed[status], "measurement contains fields outside its declared status")
    subjects = {item["source"], item["recipient"]}
    if status == "unknown":
        need(all(row.get(k) is None for k in ("value", "range", "baseline", "candidate", "receipt", "check")),
             "unknown measurement cannot contain numeric values, zero substitutes or a receipt")
        fields(row, ("note",), "unknown measurement")
        if "evidence" in row:
            read_refs(row["evidence"], context, "unknown measurement context", subjects, required=False)
        return
    if status in {"estimated", "reported"}:
        support = read_refs(row.get("evidence"), context, "estimated/reported measurement", subjects)
        if status == "estimated":
            fields(row, ("assumptions",), "estimate")
            need(row.get("receipt") is None, "estimate must not masquerade as an executed measurement")
            if row.get("range") is not None:
                value = row["range"]
                need(isinstance(value, dict) and set(value) == {"low", "high"}
                     and all(_finite(value[k]) for k in value) and value["low"] <= value["high"], "estimate range must be finite and ordered")
            else:
                fields(row, ("qualitative",), "qualitative estimate")
        else:
            need(all(e.get("artifact_kind", "source") == "source" for e in support), "reported numbers need source captures, not execution receipts")
            need(_finite(row.get("value")), "reported measurement needs a finite quoted value")
            needle = format(row["value"], "g")
            need(any(re.search(r"(?<![\d.])" + re.escape(needle) + r"(?![\d.])", _bytes(context, root, e["path"], contained).decode("utf-8-sig", errors="replace")) for e in support),
                 "reported number is absent from its cited capture")
        return
    if status == "static":
        metrics = {"captured-bytes": "bytes", "captured-lines": "lines", "captured-files": "files"}
        need(row["metric"] in metrics and row["unit"] == metrics[row["metric"]], "static footprint is captured bytes/lines/files, never runtime cost")
        for name in ("baseline", "candidate"):
            side = row.get(name)
            need(isinstance(side, dict), "static measurement needs baseline and candidate")
            evidence = read_refs(side.get("evidence"), context, "static footprint", subjects)
            need(all(e.get("artifact_kind", "source") == "source" for e in evidence), "static footprint needs source captures")
            data = [_bytes(context, root, e["path"], contained) for e in evidence]
            value = sum(len(b) for b in data) if row["unit"] == "bytes" else sum(len(b.splitlines()) for b in data) if row["unit"] == "lines" else len(data)
            need(type(side.get("value")) is int and side["value"] == value, "static measurement differs from captured bytes/lines/files")
        return
    fields(row, ("workload", "denominator", "receipt", "check"), "measured comparison")
    need(type(row.get("sample_size")) is int and row["sample_size"] > 0, "measurement sample_size must be positive")
    revisions = {context["sources"][item["source"]]["revision"], context["recipients"][item["recipient"]]["revision"]}
    for name in ("baseline", "candidate"):
        side = row.get(name)
        need(isinstance(side, dict) and set(side) == {"value", "revision"} and _finite(side.get("value")), "measured comparison needs finite baseline/candidate values")
        need(side.get("revision") in revisions and side["revision"] != "unresolved", "measurement revision is outside this resolved source/recipient pair")
    receipt = context["executions"].get(row["receipt"])
    need(receipt is not None and receipt["eligible"] and receipt["subject"] in subjects and receipt.get("_read_scope") != "unread",
         "measured comparison needs this pair's eligible execution receipt")
    checks = [c for c in receipt["checks"] if c["id"] == row["check"] and c["kind"] == "positive" and c["status"] == "pass"]
    need(len(checks) == 1, "measurement check must name a passing positive receipt check")
    try:
        payload = json.loads(checks[0]["detail"])
    except (ValueError, TypeError) as error:
        raise ValueError("measurement receipt detail is not a structured JSON payload") from error
    need(payload == {key: row[key] for key in PAYLOAD_KEYS},
         "measurement values/units/workload/denominator/revisions differ from captured receipt payload")


def _quantities(body, rows):
    """Check common asserted numeric metrics; experiment criteria are deliberately excluded."""
    percents = [float(v) for v in PERCENT.findall(body)]
    matches = list(NUMBER_UNIT.finditer(body))
    # A harness may use its own units, and static footprints include files/lines.
    # Those asserted quantities must not evade the canonical binding just because
    # they are absent from the short vocabulary of common runtime units.
    declared = [(float(match.group(1)), row["unit"].lower()) for row in rows
                for match in re.finditer(r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*"
                                         + re.escape(row["unit"]) + r"(?!\w)", body, re.I)]
    if not rows and not METRIC_WORDS.search(body) and not any(m.group(3) for m in matches):
        return
    if not percents and not matches and not declared:
        return
    rows = [r for r in rows if r["status"] != "unknown"]
    need(rows, "quantified cost/performance claim needs a measurement/estimate/reported receipt; keep unknown targets in the experiment")
    bound = [r for r in rows if r["status"] in {"measured", "static"}]
    if bound:
        need(any(body == measurement_statement(row) for row in bound),
             "numeric measurement statement must match generated metric/workload/units/direction; keep other wording as unverified context")
        return
    allowed_percent = []
    allowed_values = []
    ranges = []
    units = {"usd": "usd", "dollar": "usd", "dollars": "usd", "ms": "ms", "millisecond": "ms", "milliseconds": "ms",
             "second": "seconds", "seconds": "seconds", "token": "tokens", "tokens": "tokens", "byte": "bytes", "bytes": "bytes"}
    for row in rows:
        if row["status"] in {"static", "measured"}:
            before, after = row["baseline"]["value"], row["candidate"]["value"]
            if before:
                allowed_percent.append(abs((before - after) / before * 100))
            allowed_values.extend((units.get(row["unit"].lower(), row["unit"].lower()), v) for v in (before, after, abs(before - after)))
        elif row["status"] == "reported":
            allowed_values.append((units.get(row["unit"].lower(), row["unit"].lower()), row["value"]))
            if row["unit"] in {"%", "percent"}:
                allowed_percent.append(abs(row["value"]))
        elif row.get("range") is not None:
            allowed_values.extend((units.get(row["unit"].lower(), row["unit"].lower()), v) for v in row["range"].values())
            ranges.append((units.get(row["unit"].lower(), row["unit"].lower()), row["range"]["low"], row["range"]["high"]))
            if row["unit"] in {"%", "percent"}:
                allowed_percent.extend(abs(v) for v in row["range"].values())
    for value in percents:
        need(any(math.isclose(abs(value), expected, abs_tol=0.5) for expected in allowed_percent)
             or any(unit in {"%", "percent"} and low <= value <= high for unit, low, high in ranges),
             "claimed percentage differs from the captured comparison or explicit estimate")
    for match in matches:
        if match.group(2) == "%":
            continue
        value = float(match.group(3) or match.group(1))
        unit = "usd" if match.group(3) else units.get(match.group(2).lower(), match.group(2).lower())
        need(any(unit == expected_unit and math.isclose(value, n, rel_tol=1e-9, abs_tol=0.005) for expected_unit, n in allowed_values)
             or any(unit == expected_unit and low <= value <= high for expected_unit, low, high in ranges), "claimed numeric value/units differ from its measurement basis")
    for value, raw_unit in declared:
        unit = units.get(raw_unit, raw_unit)
        need(any(unit == expected_unit and math.isclose(value, n, rel_tol=1e-9, abs_tol=0.005) for expected_unit, n in allowed_values)
             or any(unit == expected_unit and low <= value <= high for expected_unit, low, high in ranges), "claimed declared-unit quantity differs from its measurement basis")


def retained_lead(decision):
    return decision["result"] == "DISCARD" and (
        decision["basis"]["reason"] == "research-lead" or bool(decision.get("promising_check"))
    )


def _check_lead(item, context, clusters, recipient_checks):
    decision = item["decision"]
    if not retained_lead(decision):
        need(decision["basis"]["reason"] != "research-lead", "research-lead requires a retained DISCARD result")
        return
    experiment = decision["experiment"]
    fields(experiment, ("flips_to", "cluster"), "retained lead experiment")
    need(experiment["flips_to"] in {"ADAPT", "ADAPT-with-prerequisite"}, "invalid possible result for a retained lead")
    read_refs(experiment.get("seam_evidence"), context, "retained lead seam evidence", {item["recipient"]})
    # Normalize boundary whitespace only; command case and interior spaces can be significant.
    check = experiment["test"].strip().replace("\r\n", "\n")
    promising = decision.get("promising_check")
    need(promising is None or promising.strip().replace("\r\n", "\n") == check,
         "promising_check must match experiment.test")
    cluster = experiment["cluster"]
    need(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", cluster), "invalid retained lead cluster ID")
    owner = item["recipient"]
    prior = clusters.get(cluster)
    need(prior is None or prior[0] == owner, "retained lead cluster spans recipients")
    need(prior is None or prior[1] == check, "retained lead cluster has conflicting checks")
    key = owner, check
    need(key not in recipient_checks or recipient_checks[key] == cluster,
         "the same recipient check must use one cluster")
    clusters[cluster] = (owner, check)
    recipient_checks[key] = cluster


def _check_shared_prerequisite(item, context, prior):
    experiment = item["decision"]["experiment"]
    if "shared_prerequisite" not in experiment:
        return
    check = experiment["shared_prerequisite"]
    need(retained_lead(item["decision"]), "a shared prerequisite belongs to a retained lead")
    fields(check, ("id", "test", "criterion", "reopen"), "shared prerequisite")
    need(set(check) - {"condition"} == {"id", "test", "criterion", "reopen", "evidence"}
         and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", check["id"]), "invalid shared prerequisite fields or ID")
    if "condition" in check:
        fields(check, ("condition",), "blocked shared prerequisite")
    read_refs(check["evidence"], context, "shared prerequisite", {item["recipient"]})
    key = item["recipient"], check["id"]
    need(key not in prior or prior[key] == check, "conflicting shared prerequisite for this recipient and ID")
    prior[key] = check


def _decision(item, context, root, contained, schema_version):
    d = item["decision"]
    b = d.get("basis")
    fields(b, ("reason", "unit", "baseline", "benefit", "added", "removed", "alternative"), "decision.basis")
    need(b["reason"] in REASONS, "invalid decision basis: purpose/domain/language/missing measurements are not rejection reasons")
    subjects = {item["source"], item["recipient"]}
    read_refs(b.get("evidence"), context, "decision basis", subjects)
    experiment = d.get("experiment")
    fields(experiment, ("state", "hypothesis", "baseline", "test", "criterion", "reopen"), "decision.experiment")
    need(experiment["state"] in {"proposed", "blocked"}, "experiment must be a proposal or explicit blocked/reopening condition, not an invented run")
    if experiment["state"] == "blocked":
        fields(experiment, ("condition",), "blocked experiment")
    rows = unique(item["ledger"].get("measurements", []), "measurements")
    for row in rows.values():
        _measurement(row, item, context, root, contained)
    refs = b.get("measurements")
    need(isinstance(refs, list) and all(r in rows for r in refs) and len(refs) == len(set(refs)), "basis has unknown/duplicate measurements")
    if d["result"] == "DISCARD":
        need(b["reason"] in NEGATIVE_REASONS, "DISCARD needs a supported negative basis or retained research-lead, not unresolved value")
        if b["reason"] == "net-burden":
            need(any(rows[r]["status"] in {"measured", "static", "estimated"} for r in refs),
                 "cost/bloat DISCARD needs transfer-unit burden evidence; missing/unknown measurements are not a rejection reason")
            support = [context["evidence"][r]["subject"] for r in b["evidence"]]
            need(set(subjects) <= set(support), "cost/bloat rejection needs inspected donor and recipient evidence")
        if b["reason"] in {"no-benefit", "assumption-mismatch"}:
            need(any(context["evidence"][r]["subject"] == item["recipient"] for r in b["evidence"]), "recipient-specific rejection needs recipient evidence")
        if schema_version == 3 and b["reason"] == "assumption-mismatch":
            fields(b, ("assumption",), "assumption-mismatch basis")
            need(any(context["evidence"][r]["subject"] == item["source"] for r in b["evidence"]),
                 "assumption-mismatch needs donor evidence")
    _quantities(d["summary"], [rows[r] for r in refs])
    for claim_id in d["claims"]:
        claim = context["claims"][claim_id]
        ids = claim.get("measurement_refs", [])
        need(isinstance(ids, list) and all(r in rows for r in ids), "claim has unknown measurement references")
        if claim["kind"] != "experiment":
            _quantities(claim["text"], [rows[r] for r in ids])
        for ident in ids:
            if rows[ident]["status"] in {"unknown", "estimated", "reported"}:
                bound = any(row["status"] in {"measured", "static"} and claim["text"] == measurement_statement(row) for row in (rows[i] for i in ids))
                need(bound or claim["level"] == "claimed", "unknown/estimated/reported measurements must stay CLAIMED, never TESTED/OBSERVED")
            if rows[ident]["status"] == "reported":
                read_refs(rows[ident].get("evidence"), context, "reported claim", {claim["subject"]})
    return rows, b["reason"] == "research-lead" or bool(d.get("promising_check"))


def _recording(record, intake, context, root, contained, outstanding):
    receipt = intake.get("recording")
    need(isinstance(receipt, dict) and receipt.get("state") in {"pending", "recorded", "indexed"}, "recording state missing")
    if receipt["state"] == "pending":
        outstanding.append("durable record readback pending")
        return "pending"
    fields(receipt, ("path", "sha256"), "recording")
    path = contained(root, receipt["path"])
    need(path.is_file(), "claimed saved record is missing")
    raw = _bytes(context, root, receipt["path"], contained)
    need(context["digest"](raw) == receipt["sha256"] and json.loads(raw.decode("utf-8-sig")) == record,
         "saved record readback/hash differs from the checked record; record_readback must be refreshed")
    if receipt["state"] == "indexed":
        index = receipt.get("index")
        fields(index, ("path", "sha256"), "index receipt")
        data = _bytes(context, root, index["path"], contained)
        need(context["digest"](data) == index["sha256"], "index receipt hash differs")
        payload = json.loads(data.decode("utf-8-sig"))
        need(payload == {"record_sha256": receipt["sha256"], "source_ids": list(context["sources"]), "item_ids": list(context["items"])},
             "index receipt does not bind this saved record and all source/recipient items")
    else:
        need(receipt.get("index") is None, "unindexed record cannot claim an index receipt")
    return receipt["state"]


def check(record, root, context, contained, intake=None, complete=False):
    if record["schema_version"] == 1:
        need(not complete, "legacy record has no coverage/measurement contract; cannot certify complete coverage")
        return {"contract": "legacy", "complete": False, "outstanding": ["legacy record: intake/measurement coverage unverified"],
                "coverage": [], "links": [], "recording": "legacy-unverified", "retained_leads": 0, "measurements": {}}
    # Caches are private to this invocation and discarded with its checked snapshot.
    context = {**context, "_urls": {}, "_usable": {}}
    if intake is None:
        path = contained(root, "intake.json")
        need(path.is_file(), "schema-2 record requires intake.json; missing sidecar cannot downgrade gates")
        intake = json.loads(_bytes(context, root, "intake.json", contained).decode("utf-8-sig"))
    need(isinstance(intake, dict) and set(intake) == {"schema_version", "inputs_sha256", "artifacts", "recording", "lineage"}
         and type(intake["schema_version"]) is int and intake["schema_version"] == 1, "invalid intake contract schema")
    inputs = json.loads(_bytes(context, root, "inputs.json", contained).decode("utf-8-sig"))
    need(intake["inputs_sha256"] == context["digest"](context["canonical"](inputs)), "intake contract differs from immutable input manifest")
    nodes = unique(intake["artifacts"], "intake artifacts")
    need(nodes.keys() == context["sources"].keys(), "intake must account for every registered source")
    need(isinstance(intake["lineage"], list), "queue lineage must be a list")
    _lineage(intake, context, root, contained)
    outstanding, links, missing = [], [], {}
    for sid, source in context["sources"].items():
        missing[sid], rows = _artifact(nodes[sid], source, context, root, contained, outstanding)
        links.extend(rows)
    leads, measurements, grid, all_measurements, owners = 0, {}, [], {}, {}
    prerequisites, clusters, recipient_checks = {}, {}, {}
    for item in context["items"].values():
        if item["state"] != "READY":
            outstanding.append(f"{item['id']}: {item['source']} → {item['recipient']} is {item['state']}")
            rows = unique(item.get("ledger", {}).get("measurements", []), "measurements")
            for row in rows.values():
                _measurement(row, item, context, root, contained)
            measurements[item["id"]] = list(rows.values())
        else:
            need(not missing[item["source"]] or item["decision"]["result"] == "INCONCLUSIVE",
                 "unread coverage can support INCONCLUSIVE, not a completed transfer/rejection")
            rows, lead = _decision(item, context, root, contained, record["schema_version"])
            if record["schema_version"] == 3:
                _check_lead(item, context, clusters, recipient_checks)
            if record.get("report_format") == "decision-frontier-v1":
                _check_shared_prerequisite(item, context, prerequisites)
                lead = retained_lead(item["decision"])
            measurements[item["id"]] = list(rows.values())
            leads += int(lead)
        for ident, row in rows.items():
            need(ident not in all_measurements or all_measurements[ident] == row, "a shared measurement ID has conflicting payloads")
            all_measurements[ident] = row
            owners.setdefault(ident, set()).update((item["source"], item["recipient"]))
        grid.append({"source": item["source"], "recipient": item["recipient"], "item": item["id"],
                     "state": item["state"], "unresolved_roles": missing[item["source"]],
                     "result": item.get("decision", {}).get("result")})
    # A false quantitative claim must not escape checking merely because no verdict cites it yet.
    for claim in context["claims"].values():
        ids = claim.get("measurement_refs", [])
        need(isinstance(ids, list) and len(ids) == len(set(ids)) and all(i in all_measurements for i in ids), "claim has unknown/duplicate measurement references")
        need(all(claim["subject"] in owners[i] for i in ids), "measurement claim belongs to another source/recipient")
        if claim["kind"] == "experiment":
            need(claim["level"] == "claimed" and claim["status"] == "unvalidated", "experiment targets are unvalidated/CLAIMED proposals, never already measured facts")
        else:
            _quantities(claim["text"], [all_measurements[i] for i in ids])
        if any(all_measurements[i]["status"] in {"unknown", "estimated", "reported"} for i in ids):
            bound = any(row["status"] in {"measured", "static"} and claim["text"] == measurement_statement(row) for row in (all_measurements[i] for i in ids))
            need(bound or claim["level"] == "claimed", "unmeasured/reported quantities stay CLAIMED, never TESTED/OBSERVED")
        for ident in ids:
            if all_measurements[ident]["status"] == "reported":
                read_refs(all_measurements[ident].get("evidence"), context, "reported claim", {claim["subject"]})
    publication = _recording(record, intake, context, root, contained, outstanding)
    status = {"contract": f"v{record['schema_version']}", "complete": not outstanding, "outstanding": outstanding, "coverage": grid,
              "links": links, "recording": publication, "retained_leads": leads, "measurements": measurements}
    need(not complete or status["complete"], "complete coverage gate: " + "; ".join(outstanding))
    return status
