"""Read-only, tool-neutral acquisition waves. Never fetches, executes or marks evidence read."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit

_spec = importlib.util.spec_from_file_location("acquisition_aa", Path(__file__).with_name("aa.py"))
aa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aa)

REPO_KINDS = {"repo", "repository", "git-repo", "github-repo"}
SOCIAL_KINDS = {"social", "social-post", "social-media-post", "post", "tweet"}
UNKNOWN_REVISIONS = {"unresolved", "unknown", "unversioned"}
PROVIDERS = ("deepwiki", "codewiki")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _identity(value):
    """Normalize only HTTP identity syntax; keep query/version and original scope elsewhere."""
    if not _text(value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/", parsed.query, ""))
    return value  # A '#' can be a real local filename, not a mechanism fragment.


def _visibility(source):
    value = source.get("visibility", "unknown")
    aa.require(isinstance(value, str) and value in {"public", "private", "unknown"}, "source.visibility must be public, private or unknown")
    return value


def _github(source):
    value = source.get("resolved_locator") or source["locator"]
    if not _text(value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "github.com" or parsed.username or parsed.password:
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts[:2]):
        return None
    owner, repo = parts[:2]
    repo = repo.removesuffix(".git")
    return f"{owner}/{repo}" if owner and repo else None


def _repository(source):
    """Use a declared canonical repository URL, without assuming hosted index support."""
    github = _github(source)
    if github:
        return github
    canonical = source.get("resolved_locator")
    if not _text(canonical):
        return None
    try:
        parsed = urlsplit(canonical)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    return _identity(canonical)


def _groups(sources):
    """Share declared canonical bytes at one pin; never merge merely similar names."""
    groups = []
    for source in sources:
        aa.require(isinstance(source.get("aliases", []), list) and all(_text(a) for a in source.get("aliases", [])),
                   "source.aliases must be a list of nonempty locators")
        visibility = _visibility(source)
        revision = source["revision"]
        canonical = _identity(source.get("resolved_locator"))
        pinned = revision.casefold() not in UNKNOWN_REVISIONS
        # An original redirect/shortener can resolve differently across captures.
        # Only explicit aliases establish equality with a different canonical URI.
        aliases = {_identity(a) for a in source.get("aliases", [])}
        matches = []
        if canonical and pinned:
            for group in groups:
                if group["revision"] == revision and group["visibility"] == visibility and any(
                    canonical == other["canonical"] or canonical in other["aliases"] or other["canonical"] in aliases
                    for other in group["identities"] if other["canonical"]
                ):
                    matches.append(group)
        if matches:
            group = matches[0]
            for extra in matches[1:]:
                group["sources"].extend(extra["sources"])
                group["identities"].extend(extra["identities"])
                groups.remove(extra)
        else:
            group = {"revision": revision, "visibility": visibility, "sources": [], "identities": []}
            groups.append(group)
        group["sources"].append(source)
        group["identities"].append({"canonical": canonical if pinned else None, "aliases": aliases})
    # Transitive aliases cannot change supplied source order.
    order = {source["id"]: index for index, source in enumerate(sources)}
    for group in groups:
        group["sources"].sort(key=lambda source: order[source["id"]])
    groups.sort(key=lambda group: order[group["sources"][0]["id"]])
    return groups


def _waves(tasks, jobs):
    remaining, done, waves = list(tasks), set(), []
    while remaining:
        ready = [task for task in remaining if set(task["after"]) <= done][:jobs]
        aa.require(ready, "acquisition task dependencies contain a cycle")
        waves.append({"id": f"w{len(waves) + 1}", "tasks": ready})
        done.update(task["id"] for task in ready)
        remaining = [task for task in remaining if task["id"] not in done]
    return waves


def plan(record, root, jobs=4):
    """Validate current evidence, then plan bounded independent reads without carrying verdicts."""
    aa.require(type(jobs) is int and jobs > 0, "jobs must be a positive integer")
    aa.require(isinstance(record, dict), "record must be an object")
    root = Path(root)
    intake_path = aa.contained(root, "intake.json") if record.get("schema_version") in {2, 3} else None
    intake_bytes = intake_path.read_bytes() if intake_path else None
    status = aa.contract_status(record, root)
    intake = json.loads(intake_bytes.decode("utf-8-sig")) if intake_bytes is not None else {"artifacts": []}
    nodes = {node["id"]: node for node in intake["artifacts"]}
    pairs = [{key: item[key] for key in ("id", "source", "recipient", "state")} for item in record["items"]]
    scopes = {row["source"]: row["unresolved_roles"] for row in status["coverage"]}
    tasks, shared, conditional, unresolved = [], [], [], []

    def task(kind, group, **details):
        row = {"id": f"a{len(tasks) + 1}", "kind": kind, "source_ids": [s["id"] for s in group["sources"]],
               "after": [], **details}
        tasks.append(row)
        return row

    for number, group in enumerate(_groups(record["sources"]), 1):
        sources = group["sources"]
        ids = {source["id"] for source in sources}
        captures = [{key: e[key] for key in ("id", "subject", "revision", "sha256", "path", "origin", "read_scope")}
                    for e in record["evidence"] if e["subject"] in ids and e.get("artifact_kind", "source") == "source"]
        group_pairs = [row["id"] for row in pairs if row["source"] in ids]
        shared.append({"id": f"d{number}", "source_ids": [s["id"] for s in sources], "revision": group["revision"],
                       "visibility": group["visibility"], "scopes": [{"source": s["id"], "locator": s["locator"],
                           "resolved_locator": s.get("resolved_locator"), "aliases": s.get("aliases", [])} for s in sources],
                       "pairs": group_pairs, "captures": captures})
        missing = {s["id"]: scopes.get(s["id"], ["legacy coverage unverified"]) for s in sources}
        open_discovery = any(nodes.get(s["id"], {}).get("discovery", "open") != "closed" for s in sources)
        is_repo = any(s["kind"] in REPO_KINDS for s in sources)
        repository = next((_repository(s) for s in sources if _repository(s)), None)
        need_public_identity = is_repo and group["visibility"] != "private" and (group["visibility"] != "public" or not repository)
        attempts = [attempt for s in sources for attempt in nodes.get(s["id"], {}).get("attempts", [])]
        failed_refs = {ref for attempt in attempts if attempt["outcome"] != "content" for ref in attempt["evidence"]}
        provider_captures = {}
        for provider, host in (("deepwiki", "deepwiki.com"), ("codewiki", "codewiki.google")):
            refs = {ref for attempt in attempts if attempt["method"].casefold() in {provider, "provider:" + provider}
                    and attempt["outcome"] == "content" for ref in attempt["evidence"]}
            for evidence in captures:
                try:
                    origin = urlsplit(evidence["origin"])
                    if evidence["id"] not in failed_refs and origin.scheme in {"http", "https"} and origin.hostname in {host, "www." + host}:
                        refs.add(evidence["id"])
                except ValueError:
                    pass
            provider_captures[provider] = [e for e in captures if e["id"] in refs and e["id"] not in failed_refs]
        hosted_ids = {e["id"] for refs in provider_captures.values() for e in refs} if is_repo and group["visibility"] == "public" else set()
        unread = [e["id"] for e in captures if e["read_scope"] == "unread" and e["id"] not in hosted_ids]
        primary = None
        if need_public_identity or unread or any(missing.values()) or open_discovery or not captures:
            kind = "confirm-public-identity" if need_public_identity else "inspect-captures" if unread else "read-primary"
            primary = task(kind, group, target=sources[0].get("resolved_locator", sources[0]["locator"]),
                           existing_captures=[e["id"] for e in captures if e["id"] not in hosted_ids], unread_captures=unread,
                           unresolved_roles=missing, discover_links=open_discovery,
                           work="Inspect existing bytes before refetching; resolve/pin and read missing primary scope, associated links and context. Establish access scope locally or with existing authorized tools before hosted checks.")
        failed = [a for a in attempts if a["outcome"] != "content"]
        if failed and (any(missing.values()) or open_discovery):
            retrieval = [nodes.get(s["id"], {}).get("retrieval", {}) for s in sources]
            primary["failed_attempts"] = [{key: a[key] for key in ("method", "url", "outcome", "evidence")} for a in failed]
            primary["next_steps"] = [r.get("next_step") for r in retrieval if r.get("next_step")]
            primary["work"] += " Use the existing attempt trail to pursue a materially different available authorized method directly, or retain the explicit exhausted-access next step; do not serially repeat the failed read. Unread material supplies no negative finding."
        if is_repo and group["visibility"] == "public" and repository:
            for provider in PROVIDERS:
                # A read acquisition receipt may describe an unread body. Only an
                # explicit full-body coverage row closes inspection; retrieval alone does not.
                if any(nodes.get(s["id"], {}).get("coverage", {}).get(provider, {}).get("state") == "read"
                       and nodes[s["id"]]["coverage"][provider]["surface"] not in {"metadata", "abstract"} for s in sources):
                    continue
                available = provider_captures[provider]
                failed_provider = [a for a in failed if a["method"].casefold() in {provider, "provider:" + provider}]
                exhausted = bool(failed_provider) and all(nodes.get(s["id"], {}).get("retrieval", {}).get("exhausted") for s in sources)
                kind = "inspect-hosted-overview" if available else "review-recorded-attempts" if exhausted else "check-hosted-overview"
                details = {"provider": provider, "existing_captures": [e["id"] for e in available],
                           "unread_captures": [e["id"] for e in available if e["read_scope"] == "unread"],
                           "failed_attempts": [{key: a[key] for key in ("method", "url", "outcome", "evidence")} for a in failed_provider],
                           "next_steps": [nodes[s["id"]]["retrieval"]["next_step"] for s in sources if nodes.get(s["id"], {}).get("retrieval", {}).get("next_step")]}
                if kind != "review-recorded-attempts":
                    details["query"] = f'site:{"deepwiki.com" if provider == "deepwiki" else "codewiki.google"} "{repository}"'
                task(kind, group, **details,
                     work="Inspect existing provider captures before fetching. Retrieval metadata is not a body read; inspect unread bodies or reuse read bodies after scope/freshness review. Resume only materially different applicable methods not already exhausted; honor recorded current-run exhaustion and retain its next access step instead of identical repeated probes. An unavailable overview alone never blocks a source-grounded review. Check existing public pages only, retain provenance/version uncertainty, verify decisive claims in pinned source, and never trigger hosted indexing.")
        elif need_public_identity:
            conditional.append({"after": primary["id"], "condition": "A public repository identity is established and declared in source metadata",
                                "providers": list(PROVIDERS), "action": "Replan the next wave with BOTH existing-page checks; never send an unknown/private identity to hosted services."})
        named = [copy.deepcopy(work) for s in sources for work in nodes.get(s["id"], {}).get("named_works", [])
                 if next((lookup["status"] for lookup in nodes.get(s["id"], {}).get("lookups", []) if lookup["id"] == work["lookup"]), None) != "found"]
        social_without_lookup = any(s["kind"] in SOCIAL_KINDS and not nodes.get(s["id"], {}).get("lookups")
                                    and not any(e.get("classification") == "research" for e in nodes.get(s["id"], {}).get("links", [])) for s in sources)
        background_pending = any(nodes.get(s["id"], {}).get("background", {}).get("status", "pending") == "pending" for s in sources)
        if background_pending or named or social_without_lookup:
            independent_identity = is_repo and group["visibility"] == "public" and repository
            task("research-background", group, after=[primary["id"]] if primary and not captures and not independent_identity else [],
                 named_works=named, visibility=group["visibility"],
                 work="Search useful project/alias/developer/repository/paper/documentation context. Establish access scope from supplied/read context; public names already disclosed there may be searched online. Otherwise use authorized local/connector context; explicitly private identifiers stay out of public queries. Resolve identities, queue substantive discoveries for every recipient, and try alternate queries/methods for unresolved works; no new permission prompt is implied.")
        unresolved.extend({"parent": s["id"], "named_work": work["name"], "lookup": work["lookup"], "action": "Resolve and queue; no known target URL is assumed"}
                          for s in sources for work in nodes.get(s["id"], {}).get("named_works", [])
                          if next((lookup["status"] for lookup in nodes.get(s["id"], {}).get("lookups", []) if lookup["id"] == work["lookup"]), None) != "found")
    links = copy.deepcopy(status["links"])
    for row in links:
        edge = next((edge for edge in nodes.get(row["parent"], {}).get("links", []) if edge["url"] == row["url"]), None)
        if edge:
            row["resolved"] = edge["resolved"]
        if row["source"] is None and row["classification"] in {"research", "unaccounted"}:
            unresolved.append({**row, "action": "Resolve/classify and queue substantive work; then replan all recipient pairs"})
    aa.require(intake_path is None or intake_path.read_bytes() == intake_bytes, "intake changed while planning; regenerate from current saved work")
    return {"schema_version": 1, "mode": "plan-only", "record_sha256": aa.digest(aa.canonical(record)),
            "contract": status["contract"], "current_coverage_complete": status["complete"], "max_parallel": jobs,
            "waves": _waves(tasks, jobs), "shared_sources": shared, "links": links,
            "recipient_work": [{"recipient": recipient["id"], "pairs": [row for row in pairs if row["recipient"] == recipient["id"]]}
                               for recipient in record["recipients"]],
            "conditional_next_wave": conditional, "unresolved_discoveries": unresolved, "outstanding": status["outstanding"],
            "execution": "Batch only independent read-only tool calls in each wave within host limits. Merge captures/discoveries, then replan; this plan is not a scheduler or execution receipt. Share pinned bytes with correct per-subject bindings, never historical verdicts; cross-run reuse requires identity/revision/freshness review. Verify decisive primary claims before separate recipient judgments; unknown measurements keep their pilot path."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        record_path = Path(args.record).absolute()
        result = plan(aa.load(record_path), record_path.parent, args.jobs)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
