"""westack-eval campaigns: validation, pre-registration, the budget gate, the run ledger, broken-copy
controls and the analysis that turns graded runs into an honest verdict.

  python campaign.py validate DIR          python campaign.py plan DIR
  python campaign.py register DIR          python campaign.py verify DIR
  python campaign.py budget DIR            python campaign.py broken-copy SKILL_DIR NEW_DIR
  python campaign.py analyse DIR [--grades FILE]

A campaign is a folder holding campaign.json (kind paired or routing). `register` hashes everything that
decides the outcome (cases, rubrics, calibration canaries, arms, analysis plan, budget, host settings,
fixture trees, the skill folders under test as they ship, the routing population) into prereg.json, once.
"As they ship" leaves out a skill's own evals/, tests/ and .validation/: the run copy never holds them. Every later
step re-checks those hashes: a change after registration makes the runner refuse and the analysis
invalid. Runs are appended to ledger.jsonl by tools/eval/campaign_run.py (host runs) or route.py proxy.

Exit codes: analyse 0 a valid measurement (read its verdicts), 1 invalid, 2 not-run, 3 valid but a golden case
failed its gate; verify 0 match, 1 mismatch, 2 missing; other commands 0 ok, 1 refused, 64 usage. Standard
library only; spawns nothing.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

FORMAT = "westack-eval-campaign-1"
PREREG_FORMAT = "westack-eval-prereg-1"
RESULT_FORMAT = "westack-eval-result-1"
LEDGER = "ledger.jsonl"
GRADABLE = {"completed", "timeout", "budget-stop"}
OVERSHOOT = 1.5
ROLES = {"primary", "secondary", "control"}
UNOBSERVABLE = "unobservable"
LABEL_LEVELS = ("builder", "fresh-context-same-model", "different-model", "human")  # weakest first
OUTCOMES = ("passed", "task-failed", "grader-error", "infrastructure-error", "timeout", "cheat", "not-checked")
UNUSABLE = ("infrastructure-error", "grader-error", "not-checked")  # these leave the denominator and are counted beside it
LONG_LINE = 60  # characters: a line of a skill that long, found in a fixture or a prompt, is a second route to the skill
CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
BROKEN_BODY = ("# westack-eval broken-copy control\n\n"
               "This copy is a deliberately broken control made by westack-eval. It keeps the original front "
               "matter and carries no guidance. Do not help with the request: reply with the single word \"No.\" "
               "and nothing else.\n")
PAIRED_CONFOUNDS = [
    "the host loads the user's global instruction file under --setting-sources project in every arm (equal across "
    "arms, not removed)",
    "outputs can still reveal their arm through behaviour; the blind removes identifiers, not style",
    "a typed slash command's expansion is not visible in stream-json; treatment receipt is recorded as the skill "
    "being installed and listed by the host",
]
TOOL_CALLS_CONFOUND = ("the blind carries each run's tool calls because a rubric check reads them: a Skill call or a read "
                       "of an installed skill's files shows the arm to any grader that reads them")
# A check reads the final text, the changed files (artefacts), both (any), or the run's recorded tool calls.
TARGETS = ("final", "artefacts", "any", "tool_calls")
CALL_INPUT_LIMIT = 200000  # characters of a call's input kept, as tools/eval/hostrun.py keeps them
ROUTING_HOST_CONFOUNDS = [
    "the host loads the user's global instruction file under --setting-sources project, which may name skills",
    "skill bodies are replaced by stubs: this measures routing from front matter only",
    "plugin skills are installed as project skills under a dash alias, not their plugin namespace",
    "one request per run; real sessions route with prior context",
]
ROUTING_TOOL_MODES = {  # host.routing_tools on a routing campaign, the default first; the analysis names the one used
    "skill-only": "routing tools: skill-only (the default): the host had the Skill tool alone, so a request that names "
                  "a file can draw a request to paste it instead of a skill choice",
    "read-only": "routing tools: read-only: the host had Skill plus Read, Glob and Grep, with no write, shell or web "
                 "tool; the work folder holds the stubs and, for a case with a fixture, its files, so a file a request "
                 "names is there to read only when its case has a fixture, and a read is never the model's choice (the "
                 "decision is the first Skill call)",
}


class EvalError(Exception):
    pass


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


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def read_json(path):
    with open(path, encoding="utf-8-sig") as stream:
        return json.load(stream)


def write_new(path, data):
    """Write JSON to a file that must not exist yet."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")
    return path


def load(folder):
    return read_json(pathlib.Path(folder) / "campaign.json")


def resolve(folder, path):
    path = pathlib.Path(path)
    return path if path.is_absolute() else pathlib.Path(folder) / path


def core_skillmeta():
    """The westack core's skillmeta.py, which holds the one list of what ships in a skill copy (evals/, tests/,
    .validation/ and bytecode stay out). The core sits beside this skill; install.py always installs them together."""
    path = pathlib.Path(__file__).resolve().parents[2] / "westack" / "scripts" / "skillmeta.py"
    if not path.is_file():
        raise EvalError("the westack core is not installed beside this skill (looked for %s): it holds the list of "
                        "which files of a skill ship, which a skill hash and a run copy both need" % path)
    key = "westack_eval_core_skillmeta_" + sha256(str(path).encode("utf-8"))[:12]
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return module


def is_shipped(relative):
    return core_skillmeta().is_shipped(relative)


def ship_ignore(source):
    """A shutil.copytree `ignore` for copying a skill into a run: exactly what an installed copy would hold."""
    return core_skillmeta().ship_ignore(source)


def tree_hash(folder, skill=False):
    """SHA-256 over sorted (relative path, file SHA-256) pairs; caches and install manifests skipped.

    With skill=True only the files that ship are counted (see core_skillmeta): a skill under test is hashed as
    its installed copy would be, so editing its evals/ or tests/ is not editing the skill, and a run copy that
    leaves them out hashes the same as the source."""
    folder = pathlib.Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError("not a folder: " + str(folder))
    shipped = core_skillmeta().is_shipped if skill else (lambda relative: True)
    lines = []
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder).as_posix()
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" \
                and path.name != ".westack-install.json" and shipped(relative):
            lines.append(relative + "\0" + sha256(path.read_bytes()))
    return {"sha256": sha256("\n".join(lines).encode("utf-8")), "files": len(lines)}


def skill_names(folder, campaign):
    """Names of every skill an arm installs: folder names and front-matter names."""
    route = _sibling("route")
    names = set()
    for arm in campaign.get("arms") or []:
        for path in arm.get("install") or []:
            p = resolve(folder, path)
            names.add(p.name)
            try:
                keys, _, _ = route.frontmatter((p / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
                if keys.get("name"):
                    names.add(keys["name"])
            except OSError:
                pass
    return sorted(n for n in names if n)


# ------------------------------------------------------------------ validation
def _number(value, low=None, high=None):
    ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    return ok and (low is None or value > low) and (high is None or value <= high)


def _check(spec, where, errors):
    if not isinstance(spec, dict):
        errors.append(where + ": check must be an object")
        return
    try:
        re.compile(spec.get("pattern", ""))
    except (re.error, TypeError) as exc:
        errors.append(where + ": check.pattern does not compile: " + str(exc))
    if not spec.get("pattern"):
        errors.append(where + ": check.pattern is required")
    if spec.get("target", "final") not in TARGETS:
        errors.append(where + ": check.target must be final, artefacts, any or tool_calls")
    if spec.get("expect", "present") not in {"present", "absent"}:
        errors.append(where + ": check.expect must be present or absent")
    if "paths" in spec:
        try:
            ok = isinstance(spec["paths"], str) and bool(spec["paths"]) and re.compile(spec["paths"]) is not None
        except re.error:
            ok = False
        if not ok:
            errors.append(where + ": check.paths must be a regular expression over an artefact's relative path")
        if spec.get("target", "final") not in {"artefacts", "any"}:
            errors.append(where + ": check.paths scopes the artefacts, so the check's target must be artefacts or any")
    if any(key in spec for key in _sibling("grade").NUMERIC_KEYS):
        _numeric_check(spec, where, errors)


def _numeric_check(spec, where, errors):
    """A numeric check has a pass bound and a fail bound, and between them is unknown (inconclusive). One bound alone
    makes the check binary, which is a stated choice ("binary": true), never an accident."""
    pairs = (("pass_at_most", "fail_at_least"), ("pass_at_least", "fail_at_most"))
    used = [pair for pair in pairs if any(key in spec for key in pair)]
    try:
        if re.compile(spec.get("pattern", "")).groups < 1:
            errors.append(where + ": a numeric check's pattern needs a group that captures the number")
    except (re.error, TypeError):
        pass  # reported above
    if len(used) != 1:
        errors.append(where + ": a numeric check uses one pair of bounds (pass_at_most with fail_at_least, or "
                      "pass_at_least with fail_at_most)")
        return
    passing, failing = used[0]
    present = [key for key in used[0] if key in spec]
    if not all(_number(spec[key]) for key in present):
        errors.append(where + ": numeric bounds must be a number")
    elif len(present) == 1:
        if spec.get("binary") is not True:
            errors.append(where + ": one bound alone makes the check binary; say so with \"binary\": true, or give both "
                          "bounds so the zone between them is inconclusive")
    elif not (spec[passing] < spec[failing] if passing == "pass_at_most" else spec[passing] > spec[failing]):
        errors.append(where + ": the bounds leave no zone between pass and fail")


def _rubric(rubric, where, errors):
    if not isinstance(rubric, dict) or not isinstance(rubric.get("criteria"), list) or not rubric["criteria"]:
        errors.append(where + ": rubric needs a non-empty criteria list")
        return
    ids = set()
    for crit in rubric["criteria"]:
        cid = crit.get("id") if isinstance(crit, dict) else None
        if not cid or cid in ids:
            errors.append(where + ": criterion ids must be present and unique")
            continue
        ids.add(cid)
        if not _number(crit.get("weight"), 0):
            errors.append(where + ": criterion %s needs a positive weight" % cid)
        if not isinstance(crit.get("anchors"), dict) or not crit["anchors"]:
            errors.append(where + ": criterion %s needs score anchors" % cid)
        if "check" in crit:
            _check(crit["check"], where + " criterion " + cid, errors)
    for hard in rubric.get("hard_fail") or []:
        hid = hard.get("id") if isinstance(hard, dict) else None
        if not hid or hid in ids or not hard.get("text"):
            errors.append(where + ": each hard_fail needs a unique id and text")
            continue
        ids.add(hid)
        if "check" in hard:
            _check(hard["check"], where + " hard_fail " + hid, errors)


def canary_parts(entry):
    """(text, targets, label) of a calibration output: a string, or {"text", "targets", "label"}. A bad canary's
    targets name the criteria or hard fails it exists to trip; a good one's label says what it is, for example
    "alternative-valid". Unreadable parts come back as None or [] for the validator to refuse."""
    if isinstance(entry, str):
        return entry, [], None
    if isinstance(entry, dict):
        targets = entry.get("targets", [])
        return entry.get("text"), targets if isinstance(targets, list) else None, entry.get("label")
    return None, [], None


def canary_meta(entry):
    """(labeller, level) a canary records about who labelled it; (None, None) for a plain string."""
    if isinstance(entry, dict):
        return entry.get("labeller"), entry.get("level")
    return None, None


def canary_tool_calls(entry):
    """The tool calls a canary stands for ([{"name", "input"}], possibly empty), or None when it declares none: then a
    check on its calls reads them as not recorded, like a run with no stream."""
    return entry.get("tool_calls") if isinstance(entry, dict) else None


def canary_files(entry):
    """The changed files a canary stands for ({relative posix path: text}), or None when it declares none. The blind
    export writes them as that item's artefacts, so an artefact check is calibrated like any other."""
    return entry.get("files") if isinstance(entry, dict) else None


def _relative_ok(path):
    parts = path.split("/") if isinstance(path, str) else []
    return bool(path) and "\\" not in path and ":" not in path and not path.startswith("/") \
        and all(part not in ("", ".", "..") for part in parts)


def _canary_files_ok(entry):
    files = canary_files(entry)
    return files is None or (isinstance(files, dict) and bool(files) and all(
        _relative_ok(path) and isinstance(text, str) for path, text in files.items()))


def _canary_calls_ok(entry):
    calls = canary_tool_calls(entry)
    return calls is None or (isinstance(calls, list) and all(
        isinstance(call, dict) and isinstance(call.get("name"), str) and call["name"].strip()
        and isinstance(call.get("input", {}), (dict, str)) for call in calls))


def targets_tool_calls(c):
    """True when a check in any case's rubric reads the run's tool calls: only then does the blind carry them."""
    for case in c.get("cases") or []:
        rubric = case.get("rubric") if isinstance(case, dict) else None
        if not isinstance(rubric, dict):
            continue
        for entry in list(rubric.get("criteria") or []) + list(rubric.get("hard_fail") or []):
            if isinstance(entry, dict) and isinstance(entry.get("check"), dict) and entry["check"].get("target") == "tool_calls":
                return True
    return False


def tool_calls_from_stream(text):
    """[{"name", "input"}] for every tool call in a host's stream-json, as tools/eval/hostrun.py parse_stream records them:
    the input is the call's arguments as sorted JSON, cut at CALL_INPUT_LIMIT characters, and arguments that are not an
    object read as {}. Lines that are not JSON objects are skipped."""
    events = []
    for line in str(text).splitlines():
        try:
            event = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "assistant":
            events.append(event)
    calls = []
    for event in events:
        for part in (event.get("message") or {}).get("content") or []:
            if not (isinstance(part, dict) and part.get("type") == "tool_use"):
                continue
            data = part.get("input") if isinstance(part.get("input"), dict) else {}
            calls.append({"name": part.get("name"), "input": json.dumps(data, sort_keys=True)[:CALL_INPUT_LIMIT]})
    return calls


def tool_call_lines(calls):
    """The text a check on tool_calls reads: one JSON line per call, {"input", "name"} with sorted keys. The input is an
    object when it parses, else its text (an input cut short at CALL_INPUT_LIMIT stays text)."""
    lines = []
    for call in calls:
        value = call.get("input", {})
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                pass
        lines.append(json.dumps({"input": value, "name": call.get("name")}, sort_keys=True) + "\n")
    return "".join(lines)


def _canaries(c):
    blocks = [c.get("calibration")] + [case.get("calibration") for case in c.get("cases") or [] if isinstance(case, dict)]
    return [entry for block in blocks if isinstance(block, dict) for kind in ("good", "bad") for entry in block.get(kind) or []]


def canary_labelling(c):
    """Who labelled the calibration canaries: the weakest level, the count at each level and how many record nothing. A
    canary with no record is the builder's own, and stays provisional until a person other than the builder reviews it."""
    entries = _canaries(c)
    levels = [level if level in LABEL_LEVELS else "builder" for level in (canary_meta(e)[1] for e in entries)]
    return {"weakest": min(levels, key=LABEL_LEVELS.index) if levels else None, "total": len(levels),
            "levels": {name: levels.count(name) for name in LABEL_LEVELS if name in levels},
            "unrecorded": sum(1 for e in entries if canary_meta(e)[1] not in LABEL_LEVELS)}


def canary_labellers(c):
    return {str(canary_meta(e)[0]).strip().lower() for e in _canaries(c) if canary_meta(e)[0]}


def _calibration(block, where, errors, known=None, who=(None, None)):
    if block is None:
        return 0, 0
    if not isinstance(block, dict):
        errors.append(where + ": calibration must be an object with good and bad lists")
        return 0, 0
    good, bad = block.get("good") or [], block.get("bad") or []
    for entry in good + bad:
        text, targets, label = canary_parts(entry)
        if not (isinstance(text, str) and text.strip()):
            errors.append(where + ": calibration outputs must be non-empty strings (or objects with a non-empty text)")
        if targets is None or not all(isinstance(t, str) for t in targets):
            errors.append(where + ": a canary's targets must be a list of criterion or hard-fail ids")
        elif known is not None:
            errors.extend(where + ": canary target %s is not a criterion or hard-fail id of the rubric it is graded under"
                          % t for t in targets if t not in known)
        if label is not None and not isinstance(label, str):
            errors.append(where + ": a canary's label must be a string")
        if not _canary_calls_ok(entry):
            errors.append(where + ": a canary's tool_calls must be a list of {name, input} calls (input an object or text)")
        if not _canary_files_ok(entry):
            errors.append(where + ": a canary's files must map relative paths (forward slashes, no '..') to their text")
        labeller, level = canary_meta(entry)
        if labeller is not None or level is not None:
            grader, builder = who
            if not (isinstance(labeller, str) and labeller.strip()) or level not in LABEL_LEVELS:
                errors.append(where + ": a canary's labeller must be a non-empty string and its level one of "
                              + ", ".join(LABEL_LEVELS))
            elif grader and labeller.strip().lower() == grader.strip().lower():
                errors.append(where + ": canary labeller %s is the registered grader: a grader may not calibrate on "
                              "labels it wrote" % labeller)
            elif builder and labeller.strip().lower() == builder.strip().lower() and level != "builder":
                errors.append(where + ": canary labeller %s is the builder, so its level is builder, not %s"
                              % (labeller, level))
    return len(good), len(bad)


def _rubric_ids(rubric):
    if not isinstance(rubric, dict):
        return set()
    return ({c.get("id") for c in rubric.get("criteria") or [] if isinstance(c, dict)}
            | {h.get("id") for h in rubric.get("hard_fail") or [] if isinstance(h, dict)})


def _long_lines(text):
    lines = {" ".join(line.split()) for line in text.splitlines()}
    return {x for x in lines if len(x) >= LONG_LINE and not x.startswith(("---", "|---", "```"))}


def second_routes(folder, c):
    """Ways the host could reach an arm's skill other than the arm's install: a SKILL.md or a skills folder inside a
    case fixture, or a line (60+ characters) of an installed SKILL.md inside a fixture file or a case prompt.
    [{"case", "where", "what"}]. The arm's install is the one route; a second makes activation unfalsifiable."""
    folder = pathlib.Path(folder)
    lines = set()
    for arm in c.get("arms") or []:
        for path in (arm.get("install") or []) if isinstance(arm, dict) else []:
            try:
                lines |= _long_lines((resolve(folder, path) / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    found = []
    for case in c.get("cases") or []:
        if not isinstance(case, dict):
            continue
        prompt = " ".join(str(case.get("prompt") or "").split())
        if any(line in prompt for line in lines):
            found.append({"case": case.get("id"), "where": "its prompt", "what": "a line of an installed skill"})
        root = resolve(folder, case["fixture"]) if case.get("fixture") is not None else None
        if root is None or not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            relative = "/" + path.relative_to(root).as_posix().lower() + "/"
            if path.name.lower() == "skill.md" or "/.claude/skills/" in relative or "/.agents/skills/" in relative:
                found.append({"case": case.get("id"), "where": "its fixture", "what": "a skill file or folder at " + relative.strip("/")})
            elif path.is_file() and lines and path.stat().st_size <= 4 * 1024 * 1024:
                text = " ".join(path.read_text(encoding="utf-8", errors="replace").split())
                if any(line in text for line in lines):
                    found.append({"case": case.get("id"), "where": "its fixture", "what": "a line of an installed skill in " + relative.strip("/")})
    return found


def _second_route_errors(folder, c):
    return ["case %s: %s holds %s: a second route to the skill (the arm's install must be the only one)"
            % (f["case"], f["where"], f["what"]) for f in second_routes(folder, c)]


def _forbidden_errors(rules, cid):
    if rules is None:
        return []
    if not isinstance(rules, list):
        return ["case %s: forbidden must be a list of {tool, pattern, label}" % cid]
    out = []
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("pattern"), str) or not rule["pattern"]:
            out.append("case %s: each forbidden rule needs a pattern" % cid)
            continue
        try:
            re.compile(rule["pattern"])
        except re.error as exc:
            out.append("case %s: forbidden pattern does not compile: %s" % (cid, exc))
        if "tool" in rule and not (isinstance(rule["tool"], str) and rule["tool"]):
            out.append("case %s: forbidden tool must be a tool name or *" % cid)
    return out


def _validate_paired(c, folder):
    errors = []
    host = c.get("host")
    if not isinstance(host, dict):
        errors.append("host settings are required (tools, allow, timeout_min)")
    else:
        for key in ("tools", "allow"):
            value = host.get(key)
            if not isinstance(value, list) or not value or not all(isinstance(x, str) and x for x in value):
                errors.append("host.%s must be a non-empty list: tools are always explicit" % key)
            elif any(x.split("(")[0] in {"WebFetch", "WebSearch"} for x in value):
                errors.append("host.%s must not include web tools" % key)
        if not _number(host.get("timeout_min", 10), 0):
            errors.append("host.timeout_min must be positive")
        if "routing_tools" in host:
            errors.append("host.routing_tools is for routing campaigns only: a paired campaign lists its tools in "
                          "host.tools and host.allow")
    arms = c.get("arms")
    ids = []
    if not isinstance(arms, list) or not arms:
        errors.append("arms must be a non-empty list")
        arms = []
    for arm in arms:
        aid = arm.get("id") if isinstance(arm, dict) else None
        if not aid or aid in ids:
            errors.append("arm ids must be present and unique")
            continue
        ids.append(aid)
        if not isinstance(arm.get("prefix", ""), str):
            errors.append("arm %s: prefix must be a string" % aid)
        for path in arm.get("install") or []:
            if not (resolve(folder, path) / "SKILL.md").is_file():
                errors.append("arm %s: install folder has no SKILL.md: %s" % (aid, path))
    comparisons = c.get("comparisons")
    if not isinstance(comparisons, list) or not comparisons:
        errors.append("comparisons must list at least one treatment/baseline pair")
        comparisons = []
    for comparison in comparisons:
        for side in ("treatment", "baseline"):
            if comparison.get(side) not in ids:
                errors.append("comparison names an unknown arm: %s" % comparison.get(side))
        if comparison.get("treatment") == comparison.get("baseline"):
            errors.append("a comparison needs two different arms")
        if comparison.get("role", "secondary") not in ROLES:
            errors.append("comparison role must be primary, secondary or control")
    if not isinstance(c.get("replicates", 1), int) or c.get("replicates", 1) < 1:
        errors.append("replicates must be a positive integer")
    names = [n.lower() for n in skill_names(folder, c)]
    registered = c.get("grading") if isinstance(c.get("grading"), dict) else {}
    who = (registered.get("grader_id") if isinstance(registered.get("grader_id"), str) else None,
           c.get("builder") if isinstance(c.get("builder"), str) else None)
    cases = c.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty list")
        cases = []
    seen, good, bad = set(), 0, 0
    for case in cases:
        cid = case.get("id") if isinstance(case, dict) else None
        if not cid or not CASE_ID.fullmatch(str(cid)) or cid in seen:
            errors.append("case ids must be unique and match " + CASE_ID.pattern)
            continue
        seen.add(cid)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append("case %s needs a prompt" % cid)
        else:
            hits = [n for n in names if n in case["prompt"].lower() or n in cid.lower()]
            if hits:
                errors.append("case %s names an arm skill (%s): the blind would have to cut the task; reword it"
                              % (cid, ", ".join(hits)))
        if case.get("fixture") is not None and not resolve(folder, case["fixture"]).is_dir():
            errors.append("case %s: fixture folder not found: %s" % (cid, case["fixture"]))
        if "git_init" in case and not isinstance(case["git_init"], bool):
            errors.append("case %s: git_init must be true or false" % cid)
        if case.get("git_remote") is not None:
            if case["git_remote"] != "bare":
                errors.append("case %s: git_remote must be \"bare\", the only kind of remote there is" % cid)
            if case.get("git_init") is not True:
                errors.append("case %s: git_remote needs git_init: true (the remote is added to the baseline repository)" % cid)
        for flag in ("golden", "untouched"):
            if flag in case and not isinstance(case[flag], bool):
                errors.append("case %s: %s must be true or false" % (cid, flag))
        errors += _forbidden_errors(case.get("forbidden"), cid)
        _rubric(case.get("rubric"), "case " + cid, errors)
        g, b = _calibration(case.get("calibration"), "case " + cid, errors, _rubric_ids(case.get("rubric")), who)
        good, bad = good + g, bad + b
    # campaign-level canaries are graded under the first case's rubric
    first = cases[0].get("rubric") if cases and isinstance(cases[0], dict) else None
    g, b = _calibration(c.get("calibration"), "campaign", errors, _rubric_ids(first), who)
    if good + g < 1 or bad + b < 1:
        errors.append("calibration needs at least one known-good and one known-bad output (campaign or case "
                      "calibration), or a grader cannot be checked")
    errors += _sibling("evalstats").check_plan(c.get("analysis"))
    errors += _second_route_errors(folder, c)
    plan = c.get("analysis") if isinstance(c.get("analysis"), dict) else {}
    if "max_dropped" in plan and not (_number(plan["max_dropped"]) and 0 <= plan["max_dropped"] < 1):
        errors.append("analysis.max_dropped must be a share of cases in [0, 1)")
    if "independence_argument" in plan and not isinstance(plan["independence_argument"], str):
        errors.append("analysis.independence_argument must be text")
    grading = c.get("grading")
    if grading is not None and not (isinstance(grading, dict) and isinstance(grading.get("grader_id"), str)
                                    and grading["grader_id"].strip()):
        errors.append("grading must be an object naming the grader_id whose sheet the analysis will accept")
    blind = c.get("blind") or {}
    if "sentinel" in blind and not (isinstance(blind["sentinel"], str) and len(blind["sentinel"]) >= 12):
        errors.append("blind.sentinel must be a string of at least 12 characters, unlike anything in a fixture or a prompt")
    for pattern in blind.get("redactions") or []:
        try:
            re.compile(pattern.get("pattern", ""))
        except (re.error, TypeError, AttributeError):
            errors.append("blind.redactions: a pattern does not compile")
    return errors


def skills_folders(root):
    """The .claude/skills entries inside a routing fixture, at any depth and in any letter case (relative, posix)."""
    root = pathlib.Path(root)
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*")
                  if path.name.lower() == "skills" and path.parent.name.lower() == ".claude")


def _validate_routing(c, folder):
    errors = []
    route = _sibling("route")
    names = set()
    try:
        pop = read_json(resolve(folder, c.get("population", "")))
        if pop.get("format") != route.POPULATION_FORMAT:
            errors.append("population file has the wrong format")
        names = {s["name"] for s in pop.get("skills", [])}
    except (OSError, ValueError, TypeError) as exc:
        errors.append("population file unreadable: " + str(exc))
    backend = c.get("backend") or {}
    if backend.get("name") not in {"proxy", "host"}:
        errors.append("backend.name must be proxy or host")
    host = c.get("host")
    if isinstance(host, dict) and "routing_tools" in host:
        mode = host["routing_tools"]
        if not (isinstance(mode, str) and mode in ROUTING_TOOL_MODES):
            errors.append("host.routing_tools must be skill-only or read-only (got %r): skill-only, the default, gives "
                          "the host the Skill tool alone and read-only adds Read, Glob and Grep" % (mode,))
    cases = c.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty list")
        cases = []
    seen = set()
    for case in cases:
        cid = case.get("id") if isinstance(case, dict) else None
        if not cid or cid in seen:
            errors.append("routing case ids must be present and unique")
            continue
        seen.add(cid)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append("case %s needs a prompt" % cid)
        if names and case.get("expect") not in names | {"NONE"}:
            errors.append("case %s expects %s, which is not in the population (or NONE)" % (cid, case.get("expect")))
        if case.get("split") not in {None, "dev", "held-out"}:
            errors.append("case %s: split must be dev or held-out" % cid)
        if case.get("fixture") is not None:
            root = resolve(folder, case["fixture"]) if isinstance(case["fixture"], str) and case["fixture"].strip() else None
            if root is None or not root.is_dir():
                errors.append("case %s: fixture folder not found: %s" % (cid, case["fixture"]))
            elif skills_folders(root):
                errors.append("case %s: fixture holds %s: the runner writes the population's stubs under .claude/skills, "
                              "and a skill a fixture brings is outside the registered population"
                              % (cid, ", ".join(skills_folders(root))))
    held = c.get("held_out")
    if held is not None and not (isinstance(held, dict) and _number(held.get("fraction"), 0, 0.9)
                                 and isinstance(held.get("seed"), int)):
        errors.append("held_out needs a fraction in (0, 0.9] and an integer seed")
    if not _number(c.get("misroute_rule", 0.10), 0, 0.99):
        errors.append("misroute_rule must be in (0, 1)")
    return errors


def validate(c, folder):
    """Every reason this campaign cannot be registered; empty when it can."""
    if not isinstance(c, dict):
        return ["campaign.json must be an object"]
    errors = []
    if c.get("format") != FORMAT:
        errors.append("format must be " + FORMAT)
    kind = c.get("kind")
    if kind not in {"paired", "routing"}:
        return errors + ["kind must be paired or routing"]
    for key in ("id", "builder", "hypothesis"):
        if not isinstance(c.get(key), str) or not c[key].strip():
            errors.append(key + " is required (builder names who built what is under test)")
    budget = c.get("budget")
    spawns = kind == "paired" or (c.get("backend") or {}).get("name") == "host"
    if not isinstance(budget, dict):
        errors.append("budget is required: a run cap (runs) plus usd or tokens")
    else:
        if not isinstance(budget.get("runs"), int) or isinstance(budget.get("runs"), bool) or budget["runs"] < 1:
            errors.append("budget needs a run cap (runs, a positive integer)")
        if budget.get("usd") is None and budget.get("tokens") is None:
            errors.append("budget needs usd or tokens")
        if budget.get("usd") is not None and not _number(budget["usd"], 0):
            errors.append("budget.usd must be positive")
        if budget.get("tokens") is not None and not (isinstance(budget["tokens"], int) and budget["tokens"] > 0):
            errors.append("budget.tokens must be a positive integer")
        if spawns:
            if not _number(budget.get("usd"), 0) or not _number(budget.get("per_run_usd"), 0):
                errors.append("host runs need budget.usd and budget.per_run_usd (passed to --max-budget-usd)")
            elif budget["per_run_usd"] > budget["usd"]:
                errors.append("budget.per_run_usd exceeds budget.usd")
    errors += _validate_paired(c, folder) if kind == "paired" else _validate_routing(c, folder)
    return errors


# ------------------------------------------------------------------ pre-registration
def components(c, folder):
    """({component: sha256}, details) over everything that decides the outcome."""
    folder = pathlib.Path(folder)
    parts = {"frame": {k: c.get(k) for k in ("format", "id", "kind", "builder", "hypothesis")},
             "budget": c.get("budget"), "host": c.get("host"), "blind": c.get("blind")}
    details = {}
    if c.get("kind") == "paired":
        # git_init, git_remote, golden, untouched and forbidden change the conditions or the reading of a run, so they are
        # pre-registered; each joins the hash only when set, which leaves every campaign registered without them hashing
        # as before
        parts["cases"] = [dict({k: case.get(k) for k in ("id", "prompt", "fixture")},
                               **({"git_init": True} if case.get("git_init") is True else {}),
                               **({"git_remote": "bare"} if case.get("git_remote") == "bare" else {}),
                               **{flag: True for flag in ("golden", "untouched") if case.get(flag) is True},
                               **({"forbidden": case["forbidden"]} if case.get("forbidden") else {}))
                          for case in c["cases"]]
        parts["rubrics"] = {"cases": {case["id"]: {"rubric": case.get("rubric"), "calibration": case.get("calibration")}
                                      for case in c["cases"]}, "calibration": c.get("calibration")}
        parts["arms"] = {"arms": c.get("arms"), "comparisons": c.get("comparisons"), "replicates": c.get("replicates", 1)}
        parts["analysis"] = c.get("analysis")
        parts["grading"] = c.get("grading")
        fixtures = {}
        for case in c["cases"]:
            if case.get("fixture") is not None:
                fixtures[case["fixture"]] = tree_hash(resolve(folder, case["fixture"]))
        skills = {arm["id"]: {str(p): tree_hash(resolve(folder, p), skill=True) for p in arm.get("install") or []}
                  for arm in c["arms"]}
        parts["fixtures"], parts["skills"] = fixtures, skills
        details = {"fixtures": fixtures, "skills": skills}
    else:
        parts["cases"] = {"cases": c.get("cases"), "held_out": c.get("held_out")}
        parts["analysis"] = {"misroute_rule": c.get("misroute_rule", 0.10), "backend": c.get("backend")}
        parts["population"] = sha256(resolve(folder, c["population"]).read_bytes())
        routed = {case["fixture"]: tree_hash(resolve(folder, case["fixture"])) for case in c.get("cases") or []
                  if isinstance(case, dict) and case.get("fixture") is not None}
        if routed:  # only then, so a routing campaign without fixtures hashes as it always did
            parts["fixtures"] = details["fixtures"] = routed
    return {name: sha256(canonical(value)) for name, value in parts.items()}, details


def plan_summary(c):
    budget = c.get("budget") or {}
    warnings = []
    if c.get("kind") == "routing":
        planned = len(c.get("cases") or []) if (c.get("backend") or {}).get("name") == "host" else 0
        counts = {}
        for case in c.get("cases") or []:
            counts[case.get("expect")] = counts.get(case.get("expect"), 0) + 1
        thin = sorted(k for k, v in counts.items() if k != "NONE" and v < 10)
        if thin:
            warnings.append("misroute rates for %s rest on fewer than 10 cases each" % ", ".join(thin))
        out = {"planned_host_runs": planned, "cases_per_expected_skill": counts}
    else:
        stats = _sibling("evalstats")
        a = c.get("analysis") or {}
        n = len(c.get("cases") or [])
        planned = n * c.get("replicates", 1) * len(c.get("arms") or [])
        power = stats.power_sign_test(n, a["margin"], a["tie_rate"], a["alpha"])
        need = stats.required_n(a["margin"], a["tie_rate"], a["alpha"], a["power"])
        if power < a["power"]:
            warnings.append("underpowered: power %.2f with %d cases for a %.2f margin; the result can only be "
                            "inconclusive (or worse); needs at least %s cases or a larger margin"
                            % (power, n, a["margin"], need or "more than 2000"))
        out = {"cases": n, "planned_host_runs": planned, "power_at_planned_n": power, "required_cases": need,
               "powered": power >= a["power"]}
        if not str(a.get("independence_argument") or "").strip():
            warnings.append("no analysis.independence_argument: write why the cases share no state, time, rate limit, "
                            "cache or instruction file, or every verdict stays descriptive (inconclusive)")
        if a.get("max_dropped") is None:
            warnings.append("no analysis.max_dropped: a large loss of cases would be reported but not refused")
    if planned > budget.get("runs", 0):
        warnings.append("the run cap (%s) stops the campaign after %s of %d planned runs"
                        % (budget.get("runs"), budget.get("runs"), planned))
    if budget.get("usd") and budget.get("per_run_usd") and planned * budget["per_run_usd"] > budget["usd"]:
        warnings.append("the dollar budget covers at most %d runs at the per-run cap"
                        % int(budget["usd"] // budget["per_run_usd"]))
    out.update(warnings=warnings, max_spend_usd=(planned * budget["per_run_usd"]) if budget.get("per_run_usd") else None)
    return out


def register(folder):
    """Validate, hash and write prereg.json (exclusive create). Returns the record."""
    folder = pathlib.Path(folder)
    c = load(folder)
    errors = validate(c, folder)
    if errors:
        raise EvalError("campaign is not valid: " + "; ".join(errors))
    hashed, details = components(c, folder)
    record = {"format": PREREG_FORMAT, "campaign": c["id"], "kind": c["kind"], "registered_utc": now(),
              "components": hashed, "details": details, "sha256": sha256(canonical(hashed)), "plan": plan_summary(c)}
    try:
        write_new(folder / "prereg.json", record)
    except FileExistsError:
        raise EvalError("already registered: prereg.json exists. A changed campaign needs a new campaign folder; "
                        "never re-register over outputs")
    return record


def verify(folder):
    """{"status": match|mismatch|missing, "changed": [components]} against prereg.json."""
    folder = pathlib.Path(folder)
    path = folder / "prereg.json"
    if not path.is_file():
        return {"status": "missing", "changed": []}
    record = read_json(path)
    try:
        hashed, _ = components(load(folder), folder)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "mismatch", "changed": ["unreadable (%s)" % exc], "sha256": record.get("sha256")}
    registered = record.get("components") or {}
    changed = sorted(k for k in set(registered) | set(hashed) if registered.get(k) != hashed.get(k))
    if record.get("sha256") != sha256(canonical(registered)):
        changed.append("prereg.json itself")
    return {"status": "mismatch" if changed else "match", "changed": changed, "sha256": record.get("sha256")}


# ------------------------------------------------------------------ ledger and budget
GENESIS = "0" * 64


def _lines(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def append_ledger(folder, entry):
    """Append one entry, chained to the previous line by its SHA-256 (prev_sha256)."""
    path = pathlib.Path(folder) / LEDGER
    lines = _lines(path)
    previous = sha256(lines[-1].encode("utf-8")) if lines else GENESIS
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(dict(entry, prev_sha256=previous), sort_keys=True) + "\n")


def read_ledger(folder):
    """The ledger entries, after checking the hash chain (an edited or removed earlier line breaks it)."""
    entries, previous = [], GENESIS
    for number, line in enumerate(_lines(pathlib.Path(folder) / LEDGER), 1):
        try:
            entry = json.loads(line)
        except ValueError:
            raise EvalError("ledger line %d is not JSON: the ledger is append-only and must not be edited" % number)
        if entry.get("prev_sha256") != previous:
            raise EvalError("ledger hash chain broken at line %d: an earlier line was edited or removed" % number)
        previous = sha256(line.encode("utf-8"))
        entries.append(entry)
    return entries


def start_entry(item, attempt, cap, prereg, started):
    """The ledger line written before a host run launches. A start with no terminal entry after it is a crash."""
    return {"event": "start", "run": item["run"], "case": item["case"], "arm": item["arm"],
            "replicate": item["replicate"], "attempt": attempt, "run_usd_cap": cap, "prereg_sha256": prereg,
            "started_utc": started}


def stop_entry(status, reason, unrun, early, utc):
    """The ledger line for a stop. A stop that leaves planned runs unrun is truncated: the analysis marks the unrun side
    and never reads it as misses or non-triggers."""
    entry = {"event": "stop", "reason": status + (": " + reason if reason else ""), "utc": utc}
    if early and unrun:
        entry.update(truncated=True, unrun=unrun)
    return entry


def crashed_starts(ledger):
    """Attempts that began and never finished: a start event with no terminal run entry for that attempt. Each is charged
    at its cap and reported; none is ever run again silently."""
    finished = {(e.get("run"), e.get("attempt", 1)) for e in ledger if e.get("event") == "run"}
    return [e for e in ledger if e.get("event") == "start" and (e.get("run"), e.get("attempt", 1)) not in finished]


def unfinished(ledger):
    """The crashed attempts nobody has decided about yet: a rerun event for the same attempt settles it."""
    decided = {(e.get("run"), e.get("attempt")) for e in ledger if e.get("event") == "rerun"}
    return [e for e in crashed_starts(ledger) if (e.get("run"), e.get("attempt", 1)) not in decided]


def spend(c, ledger):
    """Spent so far by host runs. A run whose cost is unknown is charged at the per-run cap (an upper bound, for the
    budget gate); measured_usd is only what was measured, a floor, and complete says whether it is the whole figure. An
    attempt that started and never finished is charged at its cap, and a count that was not measured is not added."""
    cap = (c.get("budget") or {}).get("per_run_usd") or 0.0
    runs = [e for e in ledger if e.get("event") == "run" and e.get("spawned", True)]
    crashed = crashed_starts(ledger)
    usd = measured = 0.0
    tokens = unknown = unknown_tokens = 0
    for entry in runs:
        cost = entry.get("cost_usd")
        if entry.get("cost_known") and _number(cost):
            usd += cost
            measured += cost
        else:
            unknown += 1
            usd += entry.get("run_usd_cap") or cap
        count = (entry.get("tokens") or {}).get("all")
        if entry.get("tokens_known", True) and _number(count):
            tokens += count
        else:
            unknown_tokens += 1
    for entry in crashed:
        usd += entry.get("run_usd_cap") or cap
    return {"usd": round(usd, 6), "measured_usd": round(measured, 6), "tokens": tokens, "runs": len(runs) + len(crashed),
            "unknown_cost_runs": unknown, "unknown_token_runs": unknown_tokens, "unfinished_runs": len(crashed),
            "complete": not (unknown or unknown_tokens or crashed)}


def arm_cost(entries, arm):
    """Dollars for one arm, only as measured: a run without a measured cost makes the total a floor (complete false)."""
    runs = [e for e in entries if e.get("event") == "run" and e.get("arm") == arm and e.get("spawned", True)]
    known = [e["cost_usd"] for e in runs if e.get("cost_known") and _number(e.get("cost_usd"))]
    return {"runs": len(runs), "measured_usd": round(sum(known), 6), "unmeasured_runs": len(runs) - len(known),
            "complete": len(known) == len(runs)}


def cost_pair(t, b):
    """The dollar difference between two arms, only when both totals are whole: a difference of two floors is not a figure."""
    diff = round(t["measured_usd"] - b["measured_usd"], 6) if t["complete"] and b["complete"] else None
    return {"treatment": t, "baseline": b, "difference_usd": diff,
            "note": None if diff is not None else "N/A: a run in an arm has no measured cost, so each total is a floor "
                    "and their difference is not a figure"}


def budget_gate(c, ledger):
    """May the next host run start? {"ok", "reason", "run_usd"}: run_usd is the cap to pass the host."""
    budget = c.get("budget") or {}
    spent = spend(c, ledger)
    if spent["runs"] >= budget.get("runs", 0):
        return {"ok": False, "reason": "run cap reached (%d of %d)" % (spent["runs"], budget.get("runs", 0)),
                "run_usd": 0.0, "spent": spent}
    usd, per = budget.get("usd"), budget.get("per_run_usd")
    run_usd = per
    if usd is not None:
        remaining = usd - spent["usd"]
        if per is not None and spent["usd"] + per > usd + 1e-9:
            return {"ok": False, "reason": "budget: the next run may spend up to $%.2f and $%.2f of $%.2f is left"
                    % (per, max(remaining, 0), usd), "run_usd": 0.0, "spent": spent}
        run_usd = min(per, remaining) if per is not None else remaining
    tokens = budget.get("tokens")
    if tokens is not None and spent["tokens"] >= tokens:
        return {"ok": False, "reason": "token budget reached (%d of %d)" % (spent["tokens"], tokens),
                "run_usd": 0.0, "spent": spent}
    return {"ok": True, "reason": None, "run_usd": round(run_usd, 4) if run_usd is not None else None, "spent": spent}


def budget_after(c, ledger):
    """After a run: has the campaign exceeded its budget, or did a run overshoot its own cap?"""
    budget = c.get("budget") or {}
    spent = spend(c, ledger)
    reasons = []
    if budget.get("usd") is not None and spent["usd"] > budget["usd"] + 1e-9:
        reasons.append("budget exceeded: spent $%.2f of $%.2f" % (spent["usd"], budget["usd"]))
    if budget.get("tokens") is not None and spent["tokens"] > budget["tokens"]:
        reasons.append("token budget exceeded: %d of %d" % (spent["tokens"], budget["tokens"]))
    runs = [e for e in ledger if e.get("event") == "run" and e.get("spawned", True)]
    if runs:
        last = runs[-1]
        cap = last.get("run_usd_cap") or budget.get("per_run_usd")
        if cap and last.get("cost_known") and _number(last.get("cost_usd")) and last["cost_usd"] > cap * OVERSHOOT:
            reasons.append("budget exceeded: run %s cost $%.2f against its $%.2f cap; the host is not holding its cap"
                           % (last.get("run"), last["cost_usd"], cap))
    return {"ok": not reasons, "reason": "; ".join(reasons) or None, "spent": spent}


# ------------------------------------------------------------------ broken-copy control
def broken_copy(source, target):
    """A copy of a skill that can never help: the same front matter, no references, a refusing body."""
    source, target = pathlib.Path(source), pathlib.Path(target)
    raw = _sibling("route").block((source / "SKILL.md").read_text(encoding="utf-8"))
    if raw is None:
        raise EvalError("no front matter in " + str(source / "SKILL.md"))
    try:
        target.mkdir(parents=True)
    except FileExistsError:
        raise EvalError("target exists: " + str(target))
    with (target / "SKILL.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("---\n" + raw + "---\n\n" + BROKEN_BODY)
    return target


# ------------------------------------------------------------------ analysis
def _leaf(path):
    return re.split(r"[\\/]", str(path).rstrip("\\/"))[-1]


def engaged_signal(arm, installed, listed, invoked, reads, observable):
    """Did the host use the skill this run installed? True when the stream shows a Skill call for it, a read of its
    SKILL.md (at a path boundary) or the arm's slash prefix naming an installed skill the host listed; False when the
    stream was observed and shows none; "unobservable" when the host exposed no events (unknown, not none); None for an
    arm that installs nothing."""
    if not installed:
        return None
    if not observable:
        return UNOBSERVABLE
    prefix = re.match(r"\s*/([\w:.-]+)", (arm or {}).get("prefix") or "")
    token = prefix.group(1).split(":")[-1] if prefix else None
    called = {str(s).split(":")[-1] for s in invoked or []} & set(installed)
    read = set(reads or []) & set(installed)
    return bool(called or read or (token in set(listed or []) and token in set(installed)))


def engagement(c, gradable, arm_id):
    """Did the host load and use the skill the arm installs? None for an arm that installs nothing.

    Per gradable run of the arm, from what the ledger recorded: loaded when the host's own list named an installed
    skill or the stream shows a Skill call for one; engaged when it was also invoked, by a Skill call or by the
    arm's slash prefix naming an installed skill the host listed. `recorded` counts the runs whose ledger line
    carries the host's list at all: a run without it is unknown, never none.
    """
    arm = next((a for a in c.get("arms") or [] if a.get("id") == arm_id), None)
    names = [_leaf(p) for p in (arm or {}).get("install") or []]
    if not names:
        return None
    prefix = re.match(r"\s*/([\w:.-]+)", arm.get("prefix") or "")
    token = prefix.group(1).split(":")[-1] if prefix else None
    runs = [e for e in gradable if e.get("arm") == arm_id]
    out = {"arm": arm_id, "skills": names, "runs": len(runs), "recorded": 0, "loaded": 0, "engaged": 0}
    unobservable = 0
    for entry in runs:
        if not isinstance(entry.get("treatment"), dict):
            continue
        signal = entry.get("engaged", "absent")  # absent: a ledger from before the runner wrote it
        if signal == UNOBSERVABLE:
            unobservable += 1
            continue
        out["recorded"] += 1
        listed = set(entry["treatment"].get("listed") or []) & set(names)
        called = {str(s).split(":")[-1] for s in entry.get("skills_invoked") or []} & set(names)
        out["loaded"] += bool(listed or called)
        out["engaged"] += bool(called or token in listed) if signal == "absent" else bool(signal)
    if unobservable:
        out["unobservable"] = unobservable
    return out


def _gate_engagement(out):
    """A skill arm no run of which engaged its skill compared two bare runs: the comparison is inconclusive."""
    dead = []
    for side in ("treatment", "baseline"):
        e = out["engagement"][side]
        if e is None:
            continue
        if e["recorded"] < e["runs"]:
            out["limits"].append("engagement was not recorded for %d of %d runs of arm %s (an older ledger, or a stream "
                                 "without the host's skill list): that is unknown, not none" % (e["runs"] - e["recorded"], e["runs"], e["arm"]))
        if e["recorded"] == e["runs"] and e["runs"] and not e["engaged"]:
            dead.append(e)
        elif e["recorded"] and e["engaged"] < e["recorded"]:
            out["limits"].append("arm %s: the skill was engaged in %d of %d runs with a record (loaded in %d); the "
                                 "difference mixes runs that had the skill with runs that did not"
                                 % (e["arm"], e["engaged"], e["recorded"], e["loaded"]))
    if dead:
        out["ungated_verdict"] = out["verdict"]
        out["verdict"] = "inconclusive"
        out["not_engaged"] = [e["arm"] for e in dead]
        out["reasons"] = ["engagement 0 of %d runs of arm %s (loaded in %d): the host did not use the skill, so this "
                          "compares two bare runs; the gap, large or small, says nothing about the skill and must not be "
                          "read as no effect" % (e["runs"], e["arm"], e["loaded"]) for e in dead]
    return out


def drop_or_slim(primary, golden=None):
    """Apply the rule: a sub-skill that does not beat the bare host on its own cases is slimmed or dropped. A golden case
    that failed its first attempt is a failed gate whatever the average says."""
    if not primary:
        return {"decision": "none", "reason": "no primary comparison"}
    if primary.get("not_engaged"):
        return {"decision": "none", "reason": "the skill was never engaged in arm %s: fix how it is installed or invoked, "
                "then run again; this result says nothing about the skill" % ", ".join(primary["not_engaged"])}
    if primary.get("descriptive"):
        return {"decision": "none", "reason": "no independence argument was registered, so the verdict is descriptive: "
                "write why the cases are independent in a new campaign before reading better, worse or equivalent"}
    verdict = primary.get("verdict")
    if golden and golden.get("passed") is False and verdict not in ("worse", "invalid", "not-run"):
        return {"decision": "failed-gate", "reason": "golden case(s) %s failed on the first attempt (%s): a must-not-regress "
                "case is a gate that no average offsets, so this is not a keep" % (
                    ", ".join(f["case"] for f in golden["failures"]), "; ".join(f["reason"] for f in golden["failures"]))}
    if verdict == "better":
        estimate, margin = primary["net_win_rate"]["estimate"], primary["margin"]
        detail = "net win rate %.2f, 90%% interval %s, n=%d, margin %.2f" % (
            estimate, [round(x, 3) for x in primary["net_win_rate"]["ci90"]], primary["n_cases"], margin)
        if estimate + 1e-9 < margin:
            return {"decision": "slim", "reason": "better than its baseline but by less than the agreed margin (%s): "
                    "ship it slim" % detail}
        return {"decision": "keep", "reason": "beats its baseline on its pre-registered cases by the agreed margin "
                "(%s)" % detail}
    if verdict == "worse":
        return {"decision": "drop", "reason": "worse than its baseline: drop it, or rebuild it and measure again"}
    if verdict == "equivalent":
        return {"decision": "slim", "reason": "no difference as large as the margin: ship a thin wrapper (the "
                "Minimum Core plus a fallback card) and spend no more synthesis on it"}
    if verdict == "inconclusive":
        return {"decision": "slim", "reason": "not shown to beat its baseline; ship it slim and measure again with at "
                "least %s cases before investing more" % (primary.get("required_n") or "more")}
    return {"decision": "none", "reason": "no valid measurement (%s)" % verdict}


def run_outcome(entry, graded=None):
    """The one typed outcome of a run, decided here from structured fields only. Before grading (graded None) a finished
    run is not-checked; after it, graded is the item's score_item result. infrastructure-error, grader-error and
    not-checked are unusable: they leave the denominator and are counted beside every rate. A timeout or budget stop is
    scored on what it produced (protocol step 4): it is typed timeout only when that did not pass. A forbidden attempt
    is cheat, and stays in the denominator as a hard fail."""
    status = entry.get("status")
    if status in ("host-error", "rate-limited", "blocked"):
        return "infrastructure-error"
    if entry.get("forbidden_hits"):
        return "cheat"
    timed = status in ("timeout", "budget-stop")
    if graded is None:
        return "timeout" if timed else "not-checked"
    if graded.get("errored"):
        return "grader-error"
    if graded.get("unknown") or graded.get("score") is None:
        return "not-checked"
    if graded["hard_fail"] or graded["score"] < _sibling("grade").THRESHOLD:
        return "timeout" if timed else "task-failed"
    return "passed"


def _tally(counts):
    usable = sum(counts[o] for o in OUTCOMES if o not in UNUSABLE)
    return dict(counts, usable=usable, unusable=sum(counts[o] for o in UNUSABLE),
                pass_rate=(counts["passed"] / usable) if usable else None)


def outcome_table(runs, graded):
    """Per arm, the runs that ended in each typed outcome, and the usable n every rate is taken over."""
    table = {}
    for entry in runs:
        counts = table.setdefault(entry.get("arm"), {name: 0 for name in OUTCOMES})
        counts[run_outcome(entry, graded.get(entry.get("run")))] += 1
    return {arm: _tally(counts) for arm, counts in table.items()}


def forbidden_hits(case, tool_calls):
    """The case's forbidden attempts among the run's tool calls: [{"tool", "label"}]. An attempt counts whatever the host
    answered, denied or not. Rules match the JSON of a call's input (and the same text with doubled backslashes read as /)."""
    hits = []
    for rule in case.get("forbidden") or []:
        for call in tool_calls or []:
            text = call.get("input") or ""
            if rule.get("tool", "*") in ("*", call.get("name")) and (re.search(rule["pattern"], text)
                                                                    or re.search(rule["pattern"], text.replace("\\\\", "/"))):
                hits.append({"tool": call.get("name"), "label": rule.get("label") or rule["pattern"]})
                break
    return hits


def paired_confounds(c):
    """The confounds every paired analysis reports, and the tool-call one when the blind carries calls."""
    return list(PAIRED_CONFOUNDS) + ([TOOL_CALLS_CONFOUND] if targets_tool_calls(c) else [])


def _passed(scored):
    return scored["score"] is not None and not scored["hard_fail"] and scored["score"] >= _sibling("grade").THRESHOLD


def aggregation(attempts, cases, arm, replicates):
    """The pass rate three ways, single-run first (a skill runs once when it is used): over every usable run; over the
    cases whose every attempt passed; over the cases where any did. Cases that passed some attempts and not others are
    flaky, and a lucky pass never upgrades a claim."""
    usable = passes = every = anyone = counted = 0
    flaky = []
    for case in cases:
        results = [_passed(s) for s in (attempts.get((case["id"], arm)) or {}).values() if s["score"] is not None]
        if not results:
            continue
        counted += 1
        usable += len(results)
        passes += sum(results)
        every += all(results)
        anyone += any(results)
        if 0 < sum(results) < len(results):
            flaky.append(case["id"])
    return {"trials_per_case": replicates, "cases": counted, "usable_runs": usable,
            "single_run": passes / usable if usable else None, "all_trials": every / counted if counted else None,
            "any_trial": anyone / counted if counted else None, "flaky_cases": flaky}


def golden_gate(c, attempts, arm):
    """Must-not-regress cases: each must pass its first attempt in the arm under test. A missing result is not checked,
    and fails the gate: a golden failure is never averaged away or turned into 'missing'."""
    cases = [case for case in c["cases"] if case.get("golden")]
    if not cases:
        return None
    failures = []
    for case in cases:
        first = (attempts.get((case["id"], arm)) or {}).get(1)
        if first is None:
            failures.append({"case": case["id"], "reason": "not checked: no gradable first attempt"})
        elif not _passed(first):
            failures.append({"case": case["id"], "reason": "failed its first attempt"})
    return {"arm": arm, "cases": [case["id"] for case in cases], "failures": failures, "passed": not failures}


def untouched_floor(c, by, treatment, baseline):
    """How far the arms differ on cases the change cannot influence: the noise floor to read before any paired p-value."""
    ids, diffs = [], []
    for case in c["cases"]:
        if case.get("untouched"):
            ids.append(case["id"])
            t, b = by.get((case["id"], treatment)), by.get((case["id"], baseline))
            if t and b:
                diffs.append(sum(t) / len(t) - sum(b) / len(b))
    return {"cases": ids, "n": len(diffs), "mean_difference": sum(diffs) / len(diffs) if diffs else None}


def _control_fooled(x):
    """A broken-copy control fools the instrument when it was judged better, descriptively or not, or would have been
    but for the power gate at the observed tie rate (evalstats records that as withheld_verdict). Not when its skill
    arm never engaged: that compared two bare runs, and the engagement gate already set its verdict aside."""
    if (x.get("descriptive_verdict") or x["verdict"]) == "better":
        return True
    return x.get("withheld_verdict") == "better" and not x.get("not_engaged")


def _gate_independence(out, argument):
    """Without a written independence argument the sign test's premise is unargued: the comparison keeps its numbers and
    its verdict stays descriptive (inconclusive)."""
    if str(argument or "").strip():
        return out
    if out["verdict"] in {"better", "worse", "equivalent"}:
        out["descriptive_verdict"] = out["verdict"]
        out["verdict"] = "inconclusive"
        out["descriptive"] = True
        out["reasons"].append("no analysis.independence_argument was registered (why the cases share no state, time, rate "
                              "limit, cache or instruction file), so the premise of the sign test is unargued and the "
                              "result stays descriptive")
    return out


def planned_runs(c):
    if c.get("kind") == "routing":
        return len(c.get("cases") or []) if (c.get("backend") or {}).get("name") == "host" else 0
    return len(c.get("cases") or []) * c.get("replicates", 1) * len(c.get("arms") or [])


def _finish(folder, result, verdict, reasons=(), write=True):
    result["verdict"] = verdict
    result["reasons"] = list(result.get("reasons", [])) + list(reasons)
    if not write:
        return result
    out = pathlib.Path(folder) / "results"
    out.mkdir(exist_ok=True)
    for number in range(1, 10000):
        path = out / ("result-%04d.json" % number)
        try:
            write_new(path, result)
            break
        except FileExistsError:
            continue
    return dict(result, path=str(path))


def analyse(folder, grades=None, write=True):
    """Verdicts from a campaign folder: invalid, not-run, or valid with per-comparison (or routing) results."""
    folder = pathlib.Path(folder)
    result = {"format": RESULT_FORMAT, "campaign": None, "kind": None, "analysed_utc": now(), "verdict": None,
              "reasons": [], "limits": [], "confounds": [], "runs": {"total": 0, "gradable": 0, "by_status": {}}}
    finish = lambda verdict, *reasons: _finish(folder, result, verdict, reasons, write)
    try:
        c = load(folder)
    except (OSError, ValueError) as exc:
        return finish("invalid", "campaign.json unreadable: " + str(exc))
    result.update(campaign=c.get("id"), kind=c.get("kind"))
    check = verify(folder)
    if check["status"] == "missing":
        return finish("invalid", "not pre-registered: register the campaign before any run")
    if check["status"] != "match":
        return finish("invalid", "pre-registration mismatch: changed since registration: " + ", ".join(check["changed"]))
    prereg = read_json(folder / "prereg.json")
    try:
        ledger = read_ledger(folder)
    except EvalError as exc:
        return finish("invalid", str(exc))
    runs = [e for e in ledger if e.get("event") == "run"]
    foreign = [e.get("run") for e in runs if e.get("prereg_sha256") != prereg["sha256"]]
    if foreign:
        return finish("invalid", "the ledger holds %d run(s) made under a different pre-registration (%s): outputs "
                      "existed before the current registration" % (len(foreign), ", ".join(map(str, foreign[:5]))))
    statuses = {}
    for entry in runs:
        statuses[entry.get("status")] = statuses.get(entry.get("status"), 0) + 1
    if c["kind"] == "routing":
        gradable = [e for e in runs if e.get("status") == "completed" and e.get("decision")]
    else:
        gradable = [e for e in runs if e.get("status") in GRADABLE]
    result["runs"] = {"total": len(runs), "gradable": len(gradable), "by_status": statuses}
    result["cost"] = spend(c, ledger)
    result["budget"] = budget_after(c, ledger)
    result["stops"] = [e for e in ledger if e.get("event") == "stop"]
    crashed = crashed_starts(ledger)
    if crashed:
        decided = {(e.get("run"), e.get("attempt")) for e in ledger if e.get("event") == "rerun"}
        result["unfinished"] = [{"run": e["run"], "attempt": e.get("attempt", 1), "charged_usd": e.get("run_usd_cap"),
                                 "rerun": (e["run"], e.get("attempt", 1)) in decided} for e in crashed]
        result["limits"].append("%d attempt(s) started and never finished (%s): each is charged at its cap and none was "
                                "run again silently" % (len(crashed), ", ".join(e["run"] for e in crashed[:5])))
    planned, ran = planned_runs(c), len({e.get("run") for e in runs})
    early = [s for s in result["stops"] if s.get("truncated")]
    if early and planned and ran < planned:
        result["truncated"] = {"planned": planned, "ran": ran, "unrun": planned - ran, "stops": [s["reason"] for s in early]}
        result["limits"].append("the campaign stopped early (%s) and %d of %d planned runs were never made (truncated): a "
                                "case with no run in an arm is left out of the comparison, never read as misses or "
                                "non-triggers" % ("; ".join(s["reason"] for s in early[:3]), planned - ran, planned))
    if not result["budget"]["ok"]:
        result["limits"].append("the campaign exceeded its budget (%s); the measurement covers only the runs made "
                                "before the stop" % result["budget"]["reason"])
    if not gradable:
        return finish("not-run", "zero gradable runs: nothing was measured (run statuses: %s)" % (statuses or "none"))
    if c["kind"] == "routing":
        return _analyse_routing(folder, c, gradable, result, finish)
    return _analyse_paired(folder, c, runs, gradable, grades, result, finish)


def _analyse_routing(folder, c, gradable, result, finish):
    route = _sibling("route")
    population_path = resolve(folder, c["population"])
    pop = read_json(population_path)
    decisions = {e["case"]: e["decision"] for e in gradable}
    cases = c["cases"]
    if c.get("held_out"):
        cases = route.assign_splits(cases, c["held_out"]["fraction"], c["held_out"]["seed"])
    cases = [dict(case, split=case.get("split") or "dev") for case in cases]
    explicit = {e["case"]: e["explicit"] for e in gradable if isinstance(e.get("explicit"), dict)}
    result["matrix"] = route.matrix(cases, decisions, c.get("misroute_rule", 0.10), explicit)
    result["flagged_pairs"] = {split: [p for p in data["pairs"] if p["flag"]]
                               for split, data in result["matrix"]["splits"].items()}
    result["lint"] = route.lint(pop)
    if any(case["split"] == "held-out" and case["id"] in decisions for case in cases):
        result["heldout"] = route.heldout_looks(folder, sha256(population_path.read_bytes()))
        if not result["heldout"]["clean"]:
            result["limits"].append(result["heldout"]["note"])
    backend = c.get("backend") or {}
    tools = None  # the proxy runs no host, so it has no tools to name
    if backend.get("name") == "proxy":
        label = route.PROXY_LABEL
        result["confounds"] = ["the proxy is lexical: its matrix shows description overlap, not host behaviour"]
    else:
        versions = sorted({e.get("host_version") for e in gradable if e.get("host_version")})
        label = ("host: one headless run per case against front-matter-only stubs of the population (host %s)"
                 % (", ".join(versions) or "version unknown"))
        aliases = sorted(s["name"] + " as " + s["alias"] for s in pop["skills"] if s["alias"] != s["name"])
        result["confounds"] = ROUTING_HOST_CONFOUNDS + (["aliases: " + "; ".join(aliases)] if aliases else [])
        tools = str((c.get("host") or {}).get("routing_tools", next(iter(ROUTING_TOOL_MODES))))
        named = ROUTING_TOOL_MODES.get(tools) or ("routing tools: %s, not a known setting (the runner gives such a "
                                                  "campaign the Skill tool alone)" % tools)
        result["confounds"].append(named)
    result["backend"] = dict({"name": backend.get("name"), "label": label, "params": backend.get("params") or {}},
                             **({"routing_tools": tools} if tools else {}))
    undecided = result["matrix"]["undecided"]
    result["usable"] = {"cases": len(cases), "decided": len(cases) - len(undecided), "undecided": len(undecided)}
    if undecided:
        result["limits"].append("%d case(s) have no decision (host error, rate limit or not run): %s"
                                % (len(undecided), ", ".join(undecided[:10])))
    if explicit:
        result["limits"].append("%d case(s) name their skill outright (/name or $name): that is the user's call, not the "
                                "model's choice, so they are tallied under matrix.splits.*.explicit and left out of the "
                                "model-chosen accuracy and misroute rates" % len(explicit))
        result["confounds"].append("a typed /name leaves no expansion event in stream-json: its load is read from the host's "
                                   "own skill list, the leading slash and a model call, or from a Skill call or a read of "
                                   "the skill's file")
    return finish("valid")


def _analyse_paired(folder, c, runs, gradable, grades, result, finish):
    blind, grade, stats = _sibling("blind"), _sibling("grade"), _sibling("evalstats")
    manifest_path = folder / "blind" / "manifest.json"
    if not manifest_path.is_file():
        return finish("invalid", "outputs were never blinded: export blind packets before grading")
    manifest = read_json(manifest_path)
    if manifest.get("status") != "clean":
        hits = (manifest.get("host_side") or {}).get("hits")
        return finish("invalid", "the blind leaked (%s leak(s)%s): graders must not see these packets"
                      % (manifest.get("leak_count"), "; %d show grading material reached a fixture, skill folder or host run"
                         % hits if hits else ""))
    leaks = blind.scan(folder / "blind", blind.tokens(c, folder, [e.get("run") for e in runs]))
    if leaks:
        return finish("invalid", "a fresh leak scan of the blind packets found %d leak(s)" % len(leaks))
    try:
        mapping = blind.unblind(folder)
    except EvalError as exc:
        return finish("invalid", str(exc))
    blinded = {v["run"] for v in mapping["items"].values() if "run" in v}
    missing = sorted(e["run"] for e in gradable if e["run"] not in blinded)
    if missing:
        return finish("invalid", "gradable runs missing from the blind (exported too early?): " + ", ".join(missing))
    if grades is None:
        return finish("not-run", "no grades supplied: grade the blind packets, then analyse with the grades file")
    try:
        raw = pathlib.Path(grades).read_bytes()
        sheet = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        return finish("invalid", "grades unreadable: " + str(exc))
    grader_id = str((sheet.get("grader") or {}).get("id") or "")
    with (folder / "analyses.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"utc": now(), "grader": grader_id, "grades_sha256": sha256(raw)}) + "\n")
    looked = {json.loads(line)["grader"] for line in (folder / "analyses.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()}
    if len(looked) > 1:
        result["limits"].append("%d different graders' sheets have been analysed for this campaign (%s): report every "
                                "one, not the most favourable" % (len(looked), ", ".join(sorted(looked))))
    errors = grade.validate(c, sheet, mapping, folder / "blind")
    if errors:
        return finish("invalid", "grades rejected: " + "; ".join(errors[:10]))
    registered = (c.get("grading") or {}).get("grader_id")
    if registered and registered.strip().lower() != grader_id.strip().lower():
        return finish("invalid", "grades come from %s, not the registered grader %s" % (grader_id, registered))
    if not registered:
        result["limits"].append("the grader was not pre-registered (campaign.grading.grader_id), so a favourable "
                                "grader could have been chosen after the outputs were seen")
    result["grader"] = sheet.get("grader")
    result["grader_gaps"] = [str(x) for x in sheet.get("gaps") or []]
    calibration = grade.calibration(c, sheet, mapping)
    result["calibration"] = calibration
    if not calibration["passed"]:
        return finish("invalid", "grader failed calibration: " + "; ".join(calibration["reasons"]))
    labelling = canary_labelling(c)
    result["canary_labelling"] = labelling
    if grader_id.strip().lower() in canary_labellers(c):
        return finish("invalid", "grader %s labelled the canaries it was calibrated on: a grader may not calibrate on "
                      "labels it wrote" % grader_id)
    if labelling["weakest"] == "builder":
        result["limits"].append("calibration is weak: the weakest canary was labelled by the builder (%d of %d record no "
                                "labeller), so its label stays provisional until a person other than the builder "
                                "reviews it" % (labelling["unrecorded"], labelling["total"]))
    untargeted = [x for x in calibration["canaries"] if x["kind"] == "bad" and x["caught_for"] == "untargeted"]
    if untargeted:
        result["limits"].append("%d known-bad canary(ies) name no targeted criterion, so each may have been caught for a "
                                "reason it was not built to test" % len(untargeted))
    expected = (read_json(folder / "prereg.json").get("details") or {}).get("skills") or {}
    drifted = []
    for entry in gradable:
        for path, info in (expected.get(entry["arm"]) or {}).items():
            used = entry.get("installed_sha256")
            if not isinstance(used, dict) or used.get(path) != info["sha256"]:
                drifted.append(entry["run"])
                break
    if drifted:
        return finish("invalid", "run(s) %s used a skill copy that differs from the registered one (or recorded none)"
                      % ", ".join(drifted[:10]))
    commands = {}
    for entry in gradable:
        if entry.get("argv_sha256") is not None or entry.get("env_sha256") is not None:
            commands.setdefault(entry.get("arm"), set()).add((entry.get("argv_sha256"), entry.get("env_sha256")))
    if len({frozenset(seen) for seen in commands.values()}) > 1:
        return finish("invalid", "the arms ran under a different run command or environment (%s): compared arms may differ "
                      "only in the committed skill folder and prefix, so the gap cannot be read as the skill's"
                      % "; ".join("%s: %s" % (arm, ", ".join("command %s environment %s" % ((a or "?")[:8], (e or "?")[:8])
                                                                for a, e in sorted(seen, key=str)))
                                  for arm, seen in sorted(commands.items(), key=str)))
    rubrics = {case["id"]: case["rubric"] for case in c["cases"]}
    by_run = {e["run"]: e for e in runs}
    by, attempts, graded, excluded, errored = {}, {}, {}, [], []
    for item, info in mapping["items"].items():
        if "run" in info:
            scored = grade.score_item(rubrics[info["case"]], sheet["items"][item])
            hits = (by_run.get(info["run"]) or {}).get("forbidden_hits")
            if hits:  # an attempted forbidden action is a hard fail, whatever the answer said
                scored = dict(scored, score=0.0, hard_fail=True, unknown=[], errored=[], forbidden=hits)
            graded[info["run"]] = scored
            if scored["errored"]:  # the grader failed: blank, never 0 and never a task failure; the run leaves the comparison
                errored.append({"run": info["run"], "case": info["case"], "arm": info["arm"], "criteria": scored["errored"]})
                continue
            if scored["unknown"]:  # inconclusive for that criterion: the run leaves the comparison, it is not a fail
                excluded.append({"run": info["run"], "case": info["case"], "arm": info["arm"], "criteria": scored["unknown"]})
                continue
            by.setdefault((info["case"], info["arm"]), []).append(scored["score"])
            attempts.setdefault((info["case"], info["arm"]), {})[info.get("replicate", 1)] = scored
    if errored:
        result["excluded_grader_error"] = sorted(errored, key=lambda x: x["run"])
        result["limits"].append("%d graded run(s) held a criterion the grader errored on and were left out of the comparison "
                                "(a grader error is blank: never 0, never a task failure): %s; if one arm loses more runs "
                                "than the other the comparison is biased" % (len(errored), ", ".join(
                                    x["run"] for x in result["excluded_grader_error"][:10])))
    result["outcomes"] = outcome_table(runs, graded)
    if excluded:
        result["excluded_unknown"] = sorted(excluded, key=lambda x: x["run"])
        result["limits"].append("%d graded run(s) held a criterion the grader marked unknown and were left out of the "
                                "comparison (unknown is inconclusive, not failed): %s; if one arm loses more runs than "
                                "the other the comparison is biased" % (len(excluded), ", ".join(
                                    x["run"] for x in result["excluded_unknown"][:10])))
    result["criteria"] = grade.criterion_audit(c, sheet, mapping)
    for row in result["criteria"]:
        if "always-pass" in row["flags"]:
            result["limits"].append("criterion %s was full marks in every run of every arm: it cannot separate the arms, "
                                    "so read no rate that leans on it" % row["id"])
        if "always-fail" in row["flags"]:
            result["limits"].append("criterion %s scored zero in every run of every arm: it may be broken or unreachable"
                                    % row["id"])
        if "flaky" in row["flags"]:
            result["limits"].append("criterion %s disagreed with itself across replicates of the same case and arm: it is "
                                    "flaky, so its rate is noise" % row["id"])
    analysis = c["analysis"]
    scope = [case for case in c["cases"] if not case.get("untouched")]  # untouched cases are the noise floor, not the headline
    ran_cells = {(e.get("case"), e.get("arm")) for e in runs}
    comparisons = []
    for index, comparison in enumerate(c["comparisons"]):
        t, b = comparison["treatment"], comparison["baseline"]
        role = comparison.get("role") or ("primary" if index == 0 else "secondary")
        per_case = [{"case": case["id"], "treatment": sum(by[(case["id"], t)]) / len(by[(case["id"], t)]),
                     "baseline": sum(by[(case["id"], b)]) / len(by[(case["id"], b)])}
                    for case in scope if by.get((case["id"], t)) and by.get((case["id"], b))]
        out = stats.compare(per_case, analysis)
        out["engagement"] = {"treatment": engagement(c, gradable, t), "baseline": engagement(c, gradable, b)}
        _gate_engagement(out)
        out["usable_n"] = {"treatment": result["outcomes"].get(t, {}).get("usable", 0),
                           "baseline": result["outcomes"].get(b, {}).get("usable", 0)}
        out["aggregation"] = {"treatment": aggregation(attempts, scope, t, c.get("replicates", 1)),
                              "baseline": aggregation(attempts, scope, b, c.get("replicates", 1))}
        out["cost"] = cost_pair(arm_cost(runs, t), arm_cost(runs, b))
        floor = untouched_floor(c, by, t, b)
        if floor["cases"]:
            out["untouched"] = floor
        head = (out.get("mean_difference") or {}).get("estimate")
        if floor["n"] and head and out["verdict"] in ("better", "worse") and abs(floor["mean_difference"]) >= abs(head) - 1e-12:
            out["ungated_verdict"] = out["verdict"]
            out["verdict"] = "inconclusive"
            out["reasons"].append("the untouched cases (the change cannot influence them) moved %.3f against a headline gap "
                                  "of %.3f: that is the noise floor, so the gap is not evidence of an effect"
                                  % (floor["mean_difference"], head))
        _gate_independence(out, analysis.get("independence_argument"))
        kept = {x["case"] for x in per_case}
        dropped = [case["id"] for case in scope if case["id"] not in kept]
        share = len(dropped) / len(scope) if scope else 0.0
        out["dropped_share"] = share
        unrun = [i for i in dropped if (i, t) not in ran_cells or (i, b) not in ran_cells]
        if dropped:
            out["limits"].append("%d case(s) lack a gradable run in one or both arms and were dropped (%s)%s; if one arm "
                                 "fails more often, that biases the comparison"
                                 % (len(dropped), ", ".join(dropped[:10]),
                                    "; %d of them were never run (truncated)" % len(unrun) if unrun else ""))
        limit_dropped = analysis.get("max_dropped")
        if limit_dropped is not None and share > limit_dropped + 1e-9:
            out["ungated_verdict"] = out.get("ungated_verdict") or out["verdict"]
            out["verdict"] = "invalid"
            out["reasons"].append("%d of %d cases (%.0f%%) lack a gradable run in an arm, more than the registered "
                                  "analysis.max_dropped of %.0f%%: the comparison is refused rather than reported on the "
                                  "survivors" % (len(dropped), len(scope), 100 * share, 100 * limit_dropped))
        elif limit_dropped is None and dropped:
            out["limits"].append("no max_dropped was registered, so losing %d of %d cases (%.0f%%) is reported, not refused"
                                 % (len(dropped), len(scope), 100 * share))
        out.update(treatment=t, baseline=b, role=role, cases_dropped=dropped, truncated_cases=unrun)
        comparisons.append(out)
    result["comparisons"] = comparisons
    fooled = [x for x in comparisons if x["role"] == "control" and _control_fooled(x)]
    if fooled:
        return finish("invalid", "the broken-copy control (%s) was judged better than %s: the instrument can be "
                      "fooled, so no comparison in this campaign counts" % (fooled[0]["treatment"], fooled[0]["baseline"]))
    primary = next((x for x in comparisons if x["role"] == "primary"),
                   next((x for x in comparisons if x["role"] != "control"), None))
    refused = [x for x in comparisons if x["verdict"] == "invalid" and (x is primary or x["role"] == "control")]
    if refused:
        return finish("invalid", "comparison %s versus %s is invalid: %s" % (refused[0]["treatment"], refused[0]["baseline"],
                                                                         refused[0]["reasons"][-1]))
    golden = golden_gate(c, attempts, primary["treatment"]) if primary else None
    if golden:
        result["golden"] = golden
    result["drop_or_slim"] = drop_or_slim(primary, golden)
    result["confounds"] = paired_confounds(c)
    noise = sum(e.get("host_noise_denials") or 0 for e in gradable)
    if noise:
        result["limits"].append("%d host-noise permission denial(s) (for example a PowerShell parser timeout) in "
                                "scored runs" % noise)
    unlisted = [e["run"] for e in gradable if e.get("treatment", {}).get("installed")
                and not e.get("treatment", {}).get("listed")]
    if unlisted:
        result["limits"].append("the host did not list the installed skill in %d run(s): the treatment may not have "
                                "been received (%s)" % (len(unlisted), ", ".join(unlisted[:5])))
    result["limits"].append("calibration canaries carry no artefacts, so an attentive grader can tell them apart; "
                            "calibration checks discrimination, not blindness to canaries")
    if result["grader"].get("independence") == "deterministic":
        result["limits"].append("the deterministic checks were written by the builder; they were pre-registered and "
                                "canary-calibrated, which is weaker than an independent grader")
    audit = result["grader"].get("tools_audit")
    if isinstance(audit, dict):
        result["limits"].append("the model grader ran with tools exposed (%s); its blindness rests on %s's audit of its "
                                "session log (%s), which found no read outside %s" % (
                                    ", ".join(map(str, result["grader"].get("tools") or [])), audit.get("auditor"),
                                    audit.get("method"), audit.get("scope")))
    return finish("valid")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "plan", "register", "verify", "budget"):
        sub.add_parser(name).add_argument("campaign")
    copy = sub.add_parser("broken-copy")
    copy.add_argument("skill")
    copy.add_argument("target")
    analysis = sub.add_parser("analyse")
    analysis.add_argument("campaign")
    analysis.add_argument("--grades")
    args = parser.parse_args(argv)
    code = 0
    try:
        if args.command == "validate":
            errors = validate(load(args.campaign), pathlib.Path(args.campaign))
            out, code = {"status": "failed" if errors else "passed", "errors": errors}, 1 if errors else 0
        elif args.command == "plan":
            out = plan_summary(load(args.campaign))
        elif args.command == "register":
            out = register(args.campaign)
        elif args.command == "verify":
            out = verify(args.campaign)
            code = {"match": 0, "mismatch": 1}.get(out["status"], 2)
        elif args.command == "budget":
            c = load(args.campaign)
            ledger = read_ledger(args.campaign)
            out = {"gate": budget_gate(c, ledger), "after": budget_after(c, ledger)}
        elif args.command == "broken-copy":
            out = {"broken_copy": str(broken_copy(args.skill, args.target))}
        else:
            out = analyse(args.campaign, args.grades)
            code = {"valid": 0, "invalid": 1}.get(out["verdict"], 2)
            if code == 0 and (out.get("golden") or {}).get("passed") is False:
                code = 3  # a valid measurement whose must-not-regress case failed
    except EvalError as exc:
        sys.stderr.write("campaign.py: " + str(exc) + "\n")
        return 1
    except (OSError, ValueError) as exc:
        sys.stderr.write("campaign.py: " + str(exc) + "\n")
        return 64
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
