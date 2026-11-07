"""westack-eval routing: the installed skill population, held-out splits, an offline lexical proxy router,
the shared-trigger lint, and the confusion matrix with the misroute rate per sibling pair.

  python route.py population --out FILE [--registry [--host claude] [--project DIR]] [--root DIR ...]
                             [--plugin NAME=DIR ...]
  python route.py lint FILE
  python route.py proxy CAMPAIGN_DIR
  python route.py keep BEFORE_RESULT AFTER_RESULT

`keep` keeps a changed description only if held-out routing improved (exit 0 keep, 1 reject, 2 inconclusive).
`population` reads front matter only (never executes what it finds). --registry asks the westack core's
scripts/registry.py (beside this skill) for the documented host roots; --root adds a folder of skills and
--plugin NAME=DIR a plugin's skills folder, named NAME:skill. Manual-only skills (disable-model-invocation:
true) are kept but never routed to by the model. `proxy` writes one decision per case to the campaign
ledger; it is a lexical proxy, not a model, and says nothing about how a host routes. Host routing runs
from the westack repository (tools/eval/campaign_run.py). Standard library only; no network.

A prompt that names a skill outright (`/name` or `$name`) is the user's call, not the model's choice. The host expands
a typed command without a Skill call, so such a case counts as routed to that skill only when the stream shows it
loaded (`explicit_route`), and it is tallied apart from model-chosen routing (`matrix`), never inside its accuracy.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import pathlib
import re
import sys

POPULATION_FORMAT = "westack-eval-population-1"
PROXY_LABEL = ("offline-proxy-lexical-1: a lexical-overlap proxy, not a model; it says nothing about how a "
               "host routes")
HEAD_LIMIT = 256 * 1024
NONE = "NONE"
UNRECOGNISED = "UNRECOGNISED"  # a skill call that names nothing in the population
SIGN = re.compile(r"([/$])([A-Za-z0-9][A-Za-z0-9_.:/\\-]*)")
OPENERS = "([{\"'"  # a sign after one of these (or after a space) starts a word
STOP = set("""a an and any are as at be been before but by can do does for from get go had has have how i if in
into is it its let lets me my no not of on or our please run so some than that the their them then there these
this to up us use used using via was we what when where which while who why will with you your""".split())


def _sibling(name):
    path = pathlib.Path(__file__).resolve().with_name(name + ".py")
    key = "westack_eval_" + name + "_" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return module


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace("''", "'") if value[0] == "'" else inner.replace('\\"', '"')
    return value


def block(text):
    """The raw front-matter text between the --- lines (newlines normalised), or None."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?\n)---(?:\n|$)", text, re.S)
    return match[1] if match else None


def frontmatter(text):
    """Lenient parse of any skill's front matter: (top-level keys, metadata map, errors). Block scalars
    (| or >) are joined with spaces; lists and other nested keys are ignored. Never raises on content."""
    raw = block(text)
    if raw is None:
        return {}, {}, ["missing --- block"]
    keys, meta, errors, current, folded = {}, {}, [], None, None
    for line in raw.split("\n"):
        if not line.strip():
            continue
        if line[0] in " \t":
            if folded is not None:
                folded.append(line.strip())
            elif current == "metadata":
                parsed = re.fullmatch(r"\s+([A-Za-z0-9_.-]+):(?: (.*))?", line)
                if parsed:
                    meta[parsed[1]] = _unquote(parsed[2] or "")
            continue
        folded = None
        parsed = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):(?: (.*))?", line)
        if not parsed:
            errors.append("unparseable line")
            current = None
            continue
        key, value = parsed[1], (parsed[2] or "").strip()
        if key in keys:
            errors.append("duplicate key " + key)
        current = key
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            folded = []
            keys[key] = folded
        else:
            keys[key] = _unquote(value)
    return {k: " ".join(v) if isinstance(v, list) else v for k, v in keys.items()}, meta, errors


def _folders(root):
    """SKILL.md folders at <root>/<name> and one level deeper (<root>/<group>/<name>)."""
    found = []
    try:
        children = sorted(p for p in pathlib.Path(root).iterdir() if p.is_dir())
    except OSError:
        return found
    for child in children:
        if (child / "SKILL.md").is_file():
            found.append(child)
            continue
        try:
            found.extend(sorted(g for g in child.iterdir() if g.is_dir() and (g / "SKILL.md").is_file()))
        except OSError:
            continue
    return found


def describe(folder, namespace=None):
    with (pathlib.Path(folder) / "SKILL.md").open("rb") as stream:
        text = stream.read(HEAD_LIMIT).decode("utf-8", errors="replace")
    keys, meta, errors = frontmatter(text)
    name = keys.get("name") or pathlib.Path(folder).name
    full = namespace + ":" + name if namespace else name
    raw = block(text) or ""
    flag = str(keys.get("disable-model-invocation", "")).strip().lower() == "true"
    return {"name": full, "alias": re.sub(r"[^A-Za-z0-9_.-]+", "-", full), "namespace": namespace,
            "description": keys.get("description", ""), "invocable": not flag, "stack": meta.get("stack"),
            "frontmatter": raw, "frontmatter_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "source": str(folder), "errors": errors}


def _collect(pairs):
    skills, duplicates, seen = [], [], {}
    for folder, namespace in pairs:
        entry = describe(folder, namespace)
        if entry["name"] in seen:
            duplicates.append({"name": entry["name"], "kept": seen[entry["name"]], "dropped": entry["source"]})
            continue
        seen[entry["name"]] = entry["source"]
        skills.append(entry)
    return {"format": POPULATION_FORMAT, "skills": sorted(skills, key=lambda s: s["name"]), "duplicates": duplicates,
            "claim": "front matter read from disk; nothing executed; on disk is not the same as listed by a host"}


def population(roots):
    """Population from [(root folder, namespace or None)], in order; the first of a duplicate name wins."""
    return _collect([(folder, namespace) for root, namespace in roots for folder in _folders(root)])


def registry_folders(host="claude", project="."):
    """Skill folders from the westack core's registry.py (beside this skill), or an error string."""
    path = pathlib.Path(__file__).resolve().parents[2] / "westack" / "scripts" / "registry.py"
    if not path.is_file():
        raise FileNotFoundError("westack core not installed beside this skill: " + str(path))
    spec = importlib.util.spec_from_file_location("westack_eval_core_registry", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hosts = module.HOSTS if host == "all" else (host,)
    report = module.scan(hosts, pathlib.Path.home(), pathlib.Path(project).absolute())
    return [pathlib.Path(s["path"]) for s in report["skills"]]


# ------------------------------------------------------------------ splits
def assign_splits(cases, fraction, seed):
    """Copies of the cases with split dev or held-out; an explicit split is kept. Deterministic in the seed;
    both splits are non-empty when there are at least two undecided cases."""
    out = [dict(c) for c in cases]
    undecided = [c for c in out if c.get("split") not in {"dev", "held-out"}]
    score = {c["id"]: int(hashlib.sha256(("%s|%s" % (seed, c["id"])).encode()).hexdigest()[:8], 16) / 2 ** 32
             for c in undecided}
    for c in undecided:
        c["split"] = "held-out" if score[c["id"]] < fraction else "dev"
    if len(undecided) >= 2 and fraction > 0:
        ranked = sorted(undecided, key=lambda c: score[c["id"]])
        if all(c["split"] == "dev" for c in undecided):
            ranked[0]["split"] = "held-out"
        if all(c["split"] == "held-out" for c in undecided):
            ranked[-1]["split"] = "dev"
    return out


# ------------------------------------------------------------------ proxy router
def _tokens(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    out = set()
    for word in words:
        if word in STOP or len(word) < 2:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        out.add(word)
    return out


def _documents(pop):
    docs = {s["name"]: _tokens(s.get("description", "")) | _tokens(re.sub(r"[-:_]", " ", s["name"]))
            for s in pop["skills"] if s.get("invocable", True)}
    total = len(docs)
    frequency = {}
    for words in docs.values():
        for word in words:
            frequency[word] = frequency.get(word, 0) + 1
    idf = {w: math.log((total + 1) / (f + 0.5)) for w, f in frequency.items()}
    return docs, idf


def proxy_decide(pop, prompt, threshold=1.0):
    """The proxy's choice for one request: a skill name, NONE, or AMBIGUOUS:a|b for a tie at the top."""
    docs, idf = _documents(pop)
    query = _tokens(prompt)
    scores = {name: sum(idf[w] for w in query & words) for name, words in docs.items()}
    if not scores:
        return NONE
    top = max(scores.values())
    if top < threshold:
        return NONE
    leaders = sorted(n for n, s in scores.items() if abs(s - top) < 1e-9)
    return leaders[0] if len(leaders) == 1 else "AMBIGUOUS:" + "|".join(leaders)


def lint(pop, threshold=0.8):
    """Static checks: model-invocable pairs whose descriptions share a trigger (word-set Jaccard at or above
    the threshold, or identical text), and duplicate names."""
    invocable = [s for s in pop["skills"] if s.get("invocable", True)]
    shared = []
    for i, a in enumerate(invocable):
        for b in invocable[i + 1:]:
            wa, wb = _tokens(a.get("description", "")), _tokens(b.get("description", ""))
            same = " ".join(a.get("description", "").lower().split()) == " ".join(b.get("description", "").lower().split())
            similarity = len(wa & wb) / len(wa | wb) if wa | wb else 0.0
            if same or similarity >= threshold:
                first, second = sorted((a["name"], b["name"]))
                shared.append({"a": first, "b": second, "similarity": round(similarity, 3), "identical": same})
    return {"shared_triggers": sorted(shared, key=lambda s: (s["a"], s["b"])),
            "duplicates": pop.get("duplicates", []), "threshold": threshold}


# ------------------------------------------------------------------ explicit invocation
def explicit_mentions(pop, prompt):
    """The skills a prompt names outright, in order: `/name` or `$name` where the sign starts a word (a path, a URL or a
    variable is not a mention) and the name, or its alias, is a skill of the population. Prose never counts. `leading`:
    the prompt opens with this `/name`, the one place a host expands a typed command."""
    index = {}
    for skill in pop.get("skills") or []:
        for key in (skill.get("name"), skill.get("alias")):
            if key:
                index.setdefault(key, skill)
    found, seen = [], set()
    start = len(prompt) - len(prompt.lstrip())
    for match in SIGN.finditer(prompt):
        begin = match.start()
        if begin and not (prompt[begin - 1].isspace() or prompt[begin - 1] in OPENERS):
            continue
        if "/" in match[2] or "\\" in match[2]:
            continue
        skill = index.get(match[2].rstrip(".:"))
        if skill is None or skill["name"] in seen:
            continue
        seen.add(skill["name"])
        found.append({"skill": skill["name"], "alias": skill["alias"], "form": match[1],
                      "leading": match[1] == "/" and begin == start, "manual_only": not skill.get("invocable", True)})
    return found


def _same(call, mention):
    call = str(call)
    return call in (mention["alias"], mention["skill"]) or call.split(":")[-1] == mention["alias"]


def explicit_route(pop, prompt, invoked=(), reads=(), listed=(), model_calls=0):
    """None when the prompt names no skill outright. Otherwise the first named skill the stream shows loaded, or the first
    one named when none is: {"skill", "alias", "form", "leading", "manual_only", "loaded", "evidence"}. Evidence is a Skill
    call for it ("skill-call"), a read of its SKILL.md ("skill-read") or, for a leading `/name` only, the host's own skill
    list naming it together with a model call ("host-expanded"): the host leaves no expansion event for a typed command.
    The reply text is never evidence, and a `$name` is not expanded by this host, so it needs a call or a read."""
    mentions = explicit_mentions(pop, prompt)
    if not mentions:
        return None
    calls, read, shown = list(invoked or ()), set(reads or ()), set(listed or ())
    for m in mentions:
        evidence = None
        if any(_same(call, m) for call in calls):
            evidence = "skill-call"
        elif m["alias"] in read:
            evidence = "skill-read"
        elif m["leading"] and m["alias"] in shown and model_calls >= 1:
            evidence = "host-expanded"
        if evidence:
            return dict(m, loaded=True, evidence=evidence)
    return dict(mentions[0], loaded=False, evidence=None)


# ------------------------------------------------------------------ confusion matrix
def _targets(decision):
    if decision.startswith("AMBIGUOUS:"):
        return set(decision.split(":", 1)[1].split("|"))
    return {decision}


def _rate(k, n):
    lo, hi = _sibling("evalstats").wilson(k, n)
    return {"k": k, "n": n, "rate": (k / n) if n else None, "wilson95": [lo, hi]}


def _explicit(cases, decisions, explicit):
    """The tally of the cases whose prompt named their skill outright: how many, how many the host loaded, how many ended
    at the expected skill, how many named a manual-only skill, and the loads per named skill."""
    by_skill, loaded, correct, manual = {}, 0, 0, 0
    for case in cases:
        info = explicit[case["id"]]
        row = by_skill.setdefault(info.get("skill"), {"n": 0, "loaded": 0})
        row["n"] += 1
        row["loaded"] += bool(info.get("loaded"))
        loaded += bool(info.get("loaded"))
        correct += decisions[case["id"]] == case["expect"]
        manual += bool(info.get("manual_only"))
    return {"n": len(cases), "loaded": _rate(loaded, len(cases)), "correct": correct, "manual_only": manual,
            "by_skill": by_skill}


def matrix(cases, decisions, rule=0.10, explicit=None):
    """Confusion matrix per split. A case expecting A whose decision is B, or a tie that includes B, is a
    misroute A->B; a pair is flagged when either direction reaches `rule` (the merge-or-differentiate rule).
    `explicit` maps the ids of cases whose prompt named their skill outright to that route's record: those cases are the
    user's call, so they leave the model-chosen counts and get a tally of their own under each split's "explicit"."""
    explicit = explicit or {}
    out = {"rule": rule, "splits": {}, "undecided": sorted(c["id"] for c in cases if c["id"] not in decisions)}
    for split in ("dev", "held-out"):
        chosen = [c for c in cases if c.get("split", "dev") == split and c["id"] in decisions and c["id"] not in explicit]
        named = [c for c in cases if c.get("split", "dev") == split and c["id"] in explicit and c["id"] in decisions]
        confusion, pairs, false, misses, expected_n = {}, {}, {}, {}, {}
        correct = 0
        unknown = 0
        for case in chosen:
            expected, decision = case["expect"], decisions[case["id"]]
            unrecognised = decision.startswith("UNKNOWN:")
            row = confusion.setdefault(expected, {})
            shown = UNRECOGNISED if unrecognised else decision
            row[shown] = row.get(shown, 0) + 1
            expected_n[expected] = expected_n.get(expected, 0) + 1
            correct += decision == expected
            if unrecognised:  # outside the answer list: neither a miss nor a misroute to a sibling
                unknown += 1
                continue
            targets = _targets(decision)
            if expected == NONE:
                for name in targets - {NONE}:
                    false[name] = false.get(name, 0) + 1
                continue
            if decision == NONE:
                misses[expected] = misses.get(expected, 0) + 1
            for other in targets - {expected, NONE}:
                key = tuple(sorted((expected, other)))
                pairs.setdefault(key, {}).setdefault(expected, 0)
                pairs[key][expected] += 1
        listed = []
        for (a, b), counts in sorted(pairs.items()):
            ab, ba = _rate(counts.get(a, 0), expected_n.get(a, 0)), _rate(counts.get(b, 0), expected_n.get(b, 0))
            flag = any(r["rate"] is not None and r["rate"] >= rule for r in (ab, ba))
            note = None
            if flag and min(r["n"] for r in (ab, ba) if r["n"]) < 10:
                note = "rule applied to a point estimate from fewer than 10 cases; read the interval"
            listed.append({"a": a, "b": b, "a_to_b": ab, "b_to_a": ba, "flag": flag, "note": note})
        n = len(chosen)
        out["splits"][split] = {"n": n, "correct": correct, "accuracy": correct / n if n else None,
                                "accuracy_wilson95": list(_sibling("evalstats").wilson(correct, n)),
                                "confusion": confusion, "pairs": listed, "false_triggers": false, "misses": misses,
                                "unrecognised": unknown, "explicit": _explicit(named, decisions, explicit)}
    return out


def keep_description(before, after):
    """Keep a changed description only if held-out routing improves. Both arguments are routing analysis results, one
    campaign folder per description version, scoring the same held-out cases once each. {"decision": keep | reject |
    inconclusive, "reasons"}. No improvement is a reason to reject: a change must earn its place, and a new flagged
    sibling pair on the held-out split rejects it whatever the accuracy did."""
    splits = []
    for result in (before, after):
        split = (((result or {}).get("matrix") or {}).get("splits") or {}).get("held-out")
        if (result or {}).get("verdict") != "valid" or not split or not split.get("n"):
            return {"decision": "inconclusive", "reasons": ["a result is not a valid routing result with held-out cases"]}
        splits.append(split)
    before_split, after_split = splits
    if before_split["n"] != after_split["n"]:
        return {"decision": "inconclusive", "reasons": ["the results score different held-out sets (%d and %d cases)"
                                                         % (before_split["n"], after_split["n"])]}
    improved = after_split["accuracy"] > before_split["accuracy"]
    flagged = lambda split: {(p["a"], p["b"]) for p in split.get("pairs") or [] if p.get("flag")}
    fresh = sorted(flagged(after_split) - flagged(before_split))
    reasons = ["held-out accuracy %d/%d before, %d/%d after" % (before_split["correct"], before_split["n"],
                                                               after_split["correct"], after_split["n"])]
    if fresh:
        reasons.append("new flagged sibling pair(s): " + ", ".join("%s|%s" % pair for pair in fresh))
    if not improved:
        reasons.append("held-out routing did not improve")
    return {"decision": "keep" if improved and not fresh else "reject", "reasons": reasons}


def heldout_looks(campaign_dir, population_sha):
    """Record one look at the held-out split for this population version; reuse across versions is not clean."""
    path = pathlib.Path(campaign_dir) / "heldout-looks.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"population_sha256": population_sha,
                                 "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}) + "\n")
    looks = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    versions = {look["population_sha256"] for look in looks}
    return {"looks": len(looks), "population_versions": len(versions), "clean": len(versions) <= 1,
            "note": None if len(versions) <= 1 else "the held-out cases have been scored against %d population "
                    "versions: they were used to tune descriptions and now count as dev" % len(versions)}


def run_proxy(campaign_dir):
    """Write one proxy decision per undecided case to the campaign ledger. Spawns nothing."""
    campaign = _sibling("campaign")
    folder = pathlib.Path(campaign_dir)
    data = campaign.load(folder)
    if data.get("kind") != "routing" or (data.get("backend") or {}).get("name") != "proxy":
        raise campaign.EvalError("not a routing campaign with the proxy backend")
    check = campaign.verify(folder)
    if check["status"] != "match":
        raise campaign.EvalError("pre-registration " + check["status"] + ": " + ", ".join(check.get("changed", [])))
    prereg = campaign.read_json(folder / "prereg.json")["sha256"]
    pop = campaign.read_json(folder / data["population"])
    threshold = (data["backend"].get("params") or {}).get("threshold", 1.0)
    decided = {e["case"] for e in campaign.read_ledger(folder) if e.get("event") == "run"}
    written = 0
    for index, case in enumerate(data["cases"], 1):
        if case["id"] in decided:
            continue
        campaign.append_ledger(folder, {
            "event": "run", "run": "proxy-%04d" % index, "case": case["id"], "arm": "proxy", "replicate": 1,
            "status": "completed", "decision": proxy_decide(pop, case["prompt"], threshold), "spawned": False,
            "backend": PROXY_LABEL, "cost_usd": 0.0, "cost_known": True,
            "tokens": {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0, "all": 0},
            "prereg_sha256": prereg})
        written += 1
    return {"written": written, "label": PROXY_LABEL}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    pop = sub.add_parser("population")
    pop.add_argument("--out", required=True, help="new file for the snapshot (exclusive create)")
    pop.add_argument("--registry", action="store_true", help="use the westack core registry's host roots")
    pop.add_argument("--host", default="claude", choices=["claude", "codex", "cursor", "all"])
    pop.add_argument("--project", default=".")
    pop.add_argument("--root", action="append", default=[])
    pop.add_argument("--plugin", action="append", default=[], metavar="NAME=DIR")
    check = sub.add_parser("lint")
    check.add_argument("population")
    proxy = sub.add_parser("proxy")
    proxy.add_argument("campaign")
    keep = sub.add_parser("keep")
    keep.add_argument("before")
    keep.add_argument("after")
    args = parser.parse_args(argv)
    code = 0
    try:
        if args.command == "population":
            pairs = [(f, None) for f in registry_folders(args.host, args.project)] if args.registry else []
            pairs += [(f, None) for root in args.root for f in _folders(root)]
            for item in args.plugin:
                name, _, root = item.partition("=")
                if not name or not root:
                    raise ValueError("--plugin needs NAME=DIR")
                pairs += [(f, name) for f in _folders(root)]
            result = _collect(pairs)
            text = json.dumps(result, indent=2) + "\n"
            with open(args.out, "x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
            summary = {"skills": len(result["skills"]), "invocable": sum(s["invocable"] for s in result["skills"]),
                       "duplicates": len(result["duplicates"]), "out": args.out,
                       "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        elif args.command == "lint":
            with open(args.population, encoding="utf-8") as stream:
                summary = lint(json.load(stream))
        elif args.command == "keep":
            loaded = []
            for path in (args.before, args.after):
                with open(path, encoding="utf-8-sig") as stream:
                    loaded.append(json.load(stream))
            summary = keep_description(*loaded)
            code = {"keep": 0, "reject": 1}.get(summary["decision"], 2)
        else:
            summary = run_proxy(args.campaign)
    except (OSError, ValueError) as exc:
        sys.stderr.write("route.py: " + str(exc) + "\n")
        return 64
    except Exception as exc:  # EvalError from the campaign module
        if type(exc).__name__ != "EvalError":
            raise
        sys.stderr.write("route.py: " + str(exc) + "\n")
        return 1
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
