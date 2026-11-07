"""westack-eval blinding: export graded-run packets with identifiers removed, mix in calibration canaries,
seal the label mapping, and scan the packets for leaks with a check independent of the scrubber.

  python blind.py export CAMPAIGN_DIR      (writes blind/ once, and sealed/mapping.json)
  python blind.py scan CAMPAIGN_DIR        (re-scan blind/ for leaks; exit 1 on any)

Each item is one finished run (final message, changed files, status) or one pre-registered canary (its text, and
the changed files it declares, if any), under an id derived from a random salt kept in sealed/. When a rubric check targets tool_calls, each item also carries
tool_calls.jsonl (a run's calls read from its stream.jsonl, a canary's declared ones), scrubbed and scanned like the
rest; an item whose calls were not recorded gets no such file. Graders read blind/ only: each case's prompt (without
the arm's slash prefix) and rubric, and the items. The scrubber removes the campaign, run and skill paths
(any slash style, JSON-escaped, URL-encoded or host-encoded), the names of every skill an arm installs, run
ids, declared leak tokens and regex redactions. The scan then normalises text and file names on its own and
looks for every one of those tokens; any hit marks the export rejected, and nothing downstream accepts a
rejected export. A campaign may declare `blind.sentinel`, a string that appears in its grading material (the campaign
file itself holds it). Export first proves the scan finds a sentinel planted in a scratch folder, then looks for it in
every case fixture, installed skill folder and host run, and for links that leave a fixture or skill folder: any hit
rejects the export, because grading material reached a place the host could read. Bytecode caches (__pycache__/, *.pyc) are dropped and binary files are listed but not exported
(changes.json names them under omitted_binary): graders read text, and a .pyc carries the absolute path of the
run that compiled it. Standard library only; spawns nothing.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import random
import re
import secrets
import sys
import tempfile

MANIFEST_FORMAT = "blind-manifest-1"  # neutral on purpose: a fixed string naming the stack would itself be a leak
MAPPING_FORMAT = "westack-eval-sealed-1"
SEPARATOR = r"(?:\\\\|\\|/|%5c|%2f)+"
SCAN_LIMIT = 16 * 1024 * 1024  # bytes of a file the sentinel scan reads
NOTE = ("Graders: score every item against its case's rubric.json using only this folder. Never open ../sealed, "
        "../runs, ../ledger.jsonl or ../results.")


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


def normalise(text):
    text = text.lower()
    text = re.sub(r"%5c|%2f", "/", text)
    text = text.replace("\\", "/")
    return re.sub(r"/+", "/", text)


def is_cache(relative):
    """A bytecode cache (__pycache__/ at any depth, *.pyc, *.pyo): not an artefact the run's author made."""
    parts = str(relative).replace("\\", "/").split("/")
    return "__pycache__" in parts or parts[-1].endswith((".pyc", ".pyo"))


def as_text(data):
    """The text of a file's bytes, or None for a binary file (one holding NUL bytes, unless a UTF-16 byte-order
    mark says it is text). Bytes that are not valid UTF-8 are read with replacement, as before."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if b"\x00" in data:
        return None
    return data.decode("utf-8", errors="replace")


def tokens(c, folder, runs=()):
    """Every string that would identify an arm or a run: [{"token", "kind"}], longest first."""
    campaign = _sibling("campaign")
    folder = pathlib.Path(folder)
    forms = lambda p: {str(p.absolute()), str(p.resolve())}  # absolute only: a bare relative name is too short
    blind = c.get("blind") or {}
    weak = {w.lower() for w in blind.get("weak_names") or []}
    out = []
    for name in campaign.skill_names(folder, c):
        if name.lower() in weak or len(name) < 4:
            out += [{"token": "/" + name, "kind": "skill"}, {"token": "skills/" + name, "kind": "skill"}]
        else:
            out.append({"token": name, "kind": "skill"})
    for arm in c.get("arms") or []:
        for path in arm.get("install") or []:
            out += [{"token": form, "kind": "path"} for form in forms(campaign.resolve(folder, path))]
        prefix = (arm.get("prefix") or "").strip()
        if prefix:
            out.append({"token": prefix.split()[0], "kind": "skill"})
    for form in forms(folder):
        out.append({"token": form, "kind": "path"})
        out.append({"token": re.sub(r"[^A-Za-z0-9]", "-", form), "kind": "path"})
    for run in runs:
        if run:
            out.append({"token": run, "kind": "run"})
    for token in blind.get("leak_tokens") or []:
        out.append({"token": token, "kind": "custom"})
    if isinstance(blind.get("sentinel"), str) and blind["sentinel"]:
        out.append({"token": blind["sentinel"], "kind": "custom"})
    unique = {(t["token"], t["kind"]) for t in out if t["token"]}
    return [{"token": t, "kind": k} for t, k in sorted(unique, key=lambda x: (-len(x[0]), x[0], x[1]))]


def scrubber(toks, redactions=()):
    rules = []
    for item in toks:
        parts = [re.escape(p) for p in re.split(r"[\\/]+", item["token"].strip("\\/")) if p]
        if not parts:
            continue
        replacement = {"path": "[path]", "run": "[run]"}.get(item["kind"], "[redacted]")
        rules.append((re.compile(SEPARATOR.join(parts), re.I), replacement))
    rules.append((re.compile(r"(?i)\b[A-Za-z]--Users-[A-Za-z0-9._-]+"), "[path]"))
    for redaction in redactions:
        rules.append((re.compile(redaction["pattern"]), redaction.get("replacement", "[redacted]")))

    def scrub(text):
        for pattern, replacement in rules:
            text = pattern.sub(replacement, text)
        return text
    return scrub


def scan(folder, toks):
    """Leaks in a folder: a token found in a file's normalised text or relative path.

    Bytecode caches are skipped altogether, and a binary file is checked by name only: its bytes are not text
    (a .pyc holds the absolute path of the run that compiled it, which is not something a grader sees), and the
    export no longer writes one."""
    root = pathlib.Path(folder)
    wanted = [(normalise(t["token"]), t["kind"]) for t in toks if t.get("token")]
    leaks = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if is_cache(rel):
            continue
        name = normalise(rel)
        body = as_text(path.read_bytes())
        text = None if body is None else normalise(body)
        for token, kind in wanted:
            if token in name:
                leaks.append({"file": rel, "token_kind": kind, "where": "path", "token": token})
            if text is not None and token in text:
                leaks.append({"file": rel, "token_kind": kind, "where": "content", "token": token})
    return leaks


def _walk(root):
    """(path, is_link) for everything under root; a symbolic link or junction is reported and never followed."""
    junction = getattr(os.path, "isjunction", lambda path: False)
    stack = [pathlib.Path(root)]
    while stack:
        for entry in sorted(os.scandir(stack.pop()), key=lambda e: e.name):
            path = pathlib.Path(entry.path)
            if entry.is_symlink() or junction(path):
                yield path, True
            elif entry.is_dir(follow_symlinks=False):
                stack.append(path)
            else:
                yield path, False


def _sentinel_in(root, sentinel, label, where):
    hits = []
    for path, link in _walk(root):
        relative = path.relative_to(root).as_posix()
        if link or is_cache(relative):
            continue
        with path.open("rb") as stream:
            body = as_text(stream.read(SCAN_LIMIT))
        if body is not None and sentinel in body:
            hits.append({"file": label + "/" + relative, "token_kind": "sentinel", "where": where, "token": "sentinel"})
    return hits


def _links_out(root, label):
    """Links under root that leave it: the host could follow one to grading material."""
    base = pathlib.Path(root).resolve()
    return [{"file": label + "/" + path.relative_to(root).as_posix(), "token_kind": "sentinel", "where": "link",
             "token": "link"} for path, link in _walk(root) if link and not path.resolve().is_relative_to(base)]


def sentinel_control(sentinel):
    """The scan must find a sentinel planted in a scratch folder; if it cannot, its silence elsewhere means nothing."""
    with tempfile.TemporaryDirectory(prefix="westack-sentinel-") as temp:
        (pathlib.Path(temp) / "planted.txt").write_text("before %s after\n" % sentinel, encoding="utf-8")
        return len(_sentinel_in(temp, sentinel, "control", "control")) == 1


def host_side_leaks(folder, c, sentinel):
    """The sentinel where only grading material belongs: a case fixture, an installed skill folder, a host run (its stream
    holds what the host read), or a link out of a fixture or skill folder."""
    campaign = _sibling("campaign")
    folder = pathlib.Path(folder)
    hits = []
    for case in c["cases"]:
        if case.get("fixture") is not None:
            root = campaign.resolve(folder, case["fixture"])
            hits += _sentinel_in(root, sentinel, "fixture " + case["id"], "fixture") + _links_out(root, "fixture " + case["id"])
    for arm in c.get("arms") or []:
        for path in arm.get("install") or []:
            root = campaign.resolve(folder, path)
            hits += _sentinel_in(root, sentinel, "skill " + root.name, "skill folder") + _links_out(root, "skill " + root.name)
    runs = folder / "runs"
    for run_dir in sorted(p for p in runs.iterdir() if p.is_dir()) if runs.is_dir() else []:
        hits += _sentinel_in(run_dir, sentinel, run_dir.name, "host run")
    return hits


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def _canaries(c):
    """[(case id, kind, index, text, extra)]: campaign-level canaries go to the first case. A canary is a string, or
    an object whose `extra` (the targeted criteria and a label) is sealed with the mapping, never shown to graders."""
    campaign = _sibling("campaign")
    out = []
    first = c["cases"][0]["id"]
    for owner, block in [(first, c.get("calibration"))] + [(case["id"], case.get("calibration")) for case in c["cases"]]:
        for kind in ("good", "bad"):
            for index, entry in enumerate((block or {}).get(kind) or []):
                text, targets, label = campaign.canary_parts(entry)
                calls = campaign.canary_tool_calls(entry)
                files = campaign.canary_files(entry)
                out.append((owner, kind, index, text, dict(({"targets": targets} if targets else {}),
                                                           **({"label": label} if label else {}),
                                                           **({"tool_calls": calls} if calls is not None else {}),
                                                           **({"files": files} if files else {}))))
    return out


def export(folder, scrub=True):
    """Write blind/ (packets and manifest) and sealed/mapping.json once. scrub=False exists only for the
    broken-copy control of the blinder itself: its export must come back rejected."""
    campaign = _sibling("campaign")
    folder = pathlib.Path(folder)
    c = campaign.load(folder)
    with_calls = campaign.targets_tool_calls(c)
    check = campaign.verify(folder)
    if check["status"] != "match":
        raise campaign.EvalError("pre-registration %s; not blinding (%s)" % (check["status"],
                                                                             ", ".join(check.get("changed", []))))
    out, sealed = folder / "blind", folder / "sealed"
    if out.exists() or (sealed / "mapping.json").exists():
        raise campaign.EvalError("blind packets already exported for this campaign; they are exported once")
    ledger = [e for e in campaign.read_ledger(folder) if e.get("event") == "run"]
    runs = [e for e in ledger if e.get("status") in campaign.GRADABLE]
    toks = tokens(c, folder, [e.get("run") for e in ledger])
    sentinel = (c.get("blind") or {}).get("sentinel")
    host_side = {"sentinel": False, "note": "no sentinel declared: host-side leak controls were not exercised"}
    host_leaks = []
    if sentinel:
        if not sentinel_control(sentinel):
            raise campaign.EvalError("the leak scan could not find a sentinel planted in a scratch folder, so its silence "
                                     "would mean nothing: nothing is exported")
        host_leaks = host_side_leaks(folder, c, sentinel)
        host_side = {"sentinel": True, "control": "found", "hits": len(host_leaks)}
    clean = scrubber(toks, (c.get("blind") or {}).get("redactions") or []) if scrub else (lambda text: text)
    salt = secrets.token_hex(16)
    ident = lambda key: hashlib.sha256((salt + "|" + key).encode("utf-8")).hexdigest()[:12]
    entries = [(ident("run|" + e["run"]), {"run": e["run"], "arm": e["arm"], "case": e["case"],
                                            "replicate": e.get("replicate", 1), "status": e["status"]}) for e in runs]
    for case, kind, index, text, extra in _canaries(c):
        entries.append((ident("canary|%s|%s|%d" % (case, kind, index)),
                        dict({"canary": kind, "case": case, "index": index, "text": text}, **extra)))
    random.Random("%s|blind" % c["analysis"]["seed"]).shuffle(entries)
    out.mkdir()
    for case in c["cases"]:
        rubric = {k: case["rubric"].get(k) for k in ("criteria", "hard_fail")}
        _write_text(out / "cases" / case["id"] / "prompt.txt", clean(case["prompt"]) + "\n")
        _write_text(out / "cases" / case["id"] / "rubric.json", clean(json.dumps(rubric, indent=2)) + "\n")
    for item, info in entries:
        target = out / "items" / item
        changes = {"added": [], "modified": [], "deleted": [], "omitted_binary": []}
        if "run" in info:
            run_dir = folder / "runs" / info["run"]
            final = run_dir / "final.md"
            _write_text(target / "final.md", clean(final.read_text(encoding="utf-8", errors="replace"))
                        if final.is_file() else "")
            listed = campaign.read_json(run_dir / "artefacts.json") if (run_dir / "artefacts.json").is_file() else changes
            # Bytecode caches are not the run's work: not listed, not exported. A binary artefact is listed (by its
            # scrubbed name) and named under omitted_binary, but its bytes are not exported: graders read text.
            kept = {k: [p for p in listed.get(k, []) if not is_cache(p)] for k in ("added", "modified", "deleted")}
            changes = {k: [clean(p) for p in kept[k]] for k in kept}
            omitted = []
            for rel in kept["added"] + kept["modified"]:
                source = run_dir / "work" / pathlib.PurePosixPath(rel)
                if not source.is_file():
                    continue
                body = as_text(source.read_bytes())
                if body is None:
                    omitted.append(clean(rel))
                    continue
                _write_text(target / "artefacts" / pathlib.PurePosixPath(clean(rel)), clean(body))
            changes["omitted_binary"] = sorted(omitted)
            meta = {"status": info["status"]}
            stream = run_dir / "stream.jsonl"
            calls = campaign.tool_calls_from_stream(stream.read_text(encoding="utf-8", errors="replace")) \
                if stream.is_file() else None
        else:
            _write_text(target / "final.md", clean(info["text"]))
            files = info.get("files") or {}  # a canary's changed files go where a run's do
            for rel in sorted(files):
                _write_text(target / "artefacts" / pathlib.PurePosixPath(clean(rel)), clean(files[rel]))
            changes["added"] = sorted(clean(rel) for rel in files)
            meta = {"status": "completed"}
            calls = info.get("tool_calls")
        if with_calls and calls is not None:  # not recorded: no file, and a check on the calls is unknown
            lines = campaign.tool_call_lines(calls)
            _write_text(target / "tool_calls.jsonl", clean(lines))
        _write_text(target / "changes.json", json.dumps(changes, indent=2) + "\n")
        _write_text(target / "meta.json", json.dumps(meta, indent=2) + "\n")
    mapping = {"format": MAPPING_FORMAT, "salt": salt, "items": dict(entries), "scrubbed": scrub}
    blob = (json.dumps(mapping, indent=2, sort_keys=True) + "\n").encode("utf-8")
    sealed.mkdir(exist_ok=True)
    with (sealed / "mapping.json").open("xb") as stream:
        stream.write(blob)
    manifest = {"format": MANIFEST_FORMAT, "status": "pending", "note": NOTE,
                "items": [{"item": item, "case": info["case"]} for item, info in entries],
                "mapping_sha256": hashlib.sha256(blob).hexdigest(), "leak_count": None, "host_side": host_side}
    _write_text(out / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    # The verdict comes from a scan of every file graders will see, the manifest included.
    leaks = scan(out, toks) + host_leaks
    manifest.update(status="rejected" if leaks else "clean", leak_count=len(leaks))
    with (out / "manifest.json").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(manifest, indent=2) + "\n")
    if leaks:
        with (sealed / "leaks.json").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(leaks, indent=2) + "\n")
    return dict(manifest, leaks=leaks)


def unblind(folder):
    """The sealed mapping, after checking it is the one sealed at export."""
    campaign = _sibling("campaign")
    folder = pathlib.Path(folder)
    try:
        manifest = campaign.read_json(folder / "blind" / "manifest.json")
        blob = (folder / "sealed" / "mapping.json").read_bytes()
    except (OSError, ValueError) as exc:
        raise campaign.EvalError("no blind export to unblind: " + str(exc))
    if hashlib.sha256(blob).hexdigest() != manifest.get("mapping_sha256"):
        raise campaign.EvalError("the sealed mapping changed after blinding; its hash no longer matches the manifest")
    return json.loads(blob)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export").add_argument("campaign")
    sub.add_parser("scan").add_argument("campaign")
    args = parser.parse_args(argv)
    campaign = _sibling("campaign")
    try:
        if args.command == "export":
            result = export(args.campaign)
            out = {k: v for k, v in result.items() if k != "leaks"}
            out["items"] = len(result["items"])
            code = 0 if result["status"] == "clean" else 1
        else:
            folder = pathlib.Path(args.campaign)
            c = campaign.load(folder)
            runs = [e.get("run") for e in campaign.read_ledger(folder) if e.get("event") == "run"]
            leaks = scan(folder / "blind", tokens(c, folder, runs))
            out = {"status": "rejected" if leaks else "clean", "leak_count": len(leaks),
                   "leak_kinds": sorted({(x["token_kind"], x["where"]) for x in leaks})}
            code = 1 if leaks else 0
    except campaign.EvalError as exc:
        sys.stderr.write("blind.py: " + str(exc) + "\n")
        return 1
    sys.stdout.write(json.dumps(out, indent=2, default=list) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
