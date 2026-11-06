"""westack-eval pooled studies: one analysis across several paired campaigns, planned before any member ran, so a
stack-wide claim ("the skills beat the bare host") is not chosen after the results are seen.

  python pool.py register POOL_DIR CAMPAIGN_DIR... --margin M --tie-rate T --seed S [--alpha 0.05] [--power 0.8]
                 [--bootstrap 10000] [--treatment skill] [--baseline bare] [--grades grades/deterministic.json]
                 [--independence TEXT] [--id ID] [--post-hoc]
  python pool.py verify POOL_DIR
  python pool.py analyse POOL_DIR

`register` writes POOL_DIR/pool-prereg.json once: the sha256 of each member's prereg.json, the primary comparison, the
unit, the test, alpha, the margin, the cases needed and the secondary metrics. It refuses a member whose ledger already
holds a run or a started one. --post-hoc registers such a pool anyway; every output then says POST-HOC and the pooled
verdict stays descriptive. `analyse` refuses when a member's prereg.json changed, the member no longer matches its own
registration, a run started before the pool, or its newest result is not valid. It re-scores each member's runs from
the sealed mapping and the registered grades sheet as campaign.py does, checks that this reproduces the member's own
wins, losses, ties and mean difference, then pools the cases and writes POOL_DIR/results/result-NNNN.json.

Exit codes: analyse 0 valid, 1 invalid, 2 not-run; verify 0 match, 1 mismatch, 2 missing; register 0 ok, 1 refused;
64 unreadable input. Standard library only; spawns nothing, no network.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import sys

FORMAT = "westack-eval-pool-prereg-1"
RESULT_FORMAT = "westack-eval-pool-result-1"
PREREG = "pool-prereg.json"
GRADES = "grades/deterministic.json"
EPS = 1e-9
PLAN_KEYS = ("alpha", "power", "margin", "tie_rate", "seed", "bootstrap")
POST_HOC = ("POST-HOC: registered after member runs existed, so the pool was chosen with results in view; its verdict "
            "is descriptive and backs no stack-wide claim")
UNIT = ("the case: each arm's replicates are averaged within a case first, as campaign.py does, and untouched cases stay "
        "out; each member case with a usable run in both arms counts once")
TEST = ("an exact one-sided sign test on per-case outcomes (wins against losses; ties stay in n and leave only the "
        "test), and a seeded case-level percentile bootstrap of the mean difference and the net win rate (evalstats.py)")
SECONDARY = [
    {"id": "hard_fail_rate", "better": "lower",
     "definition": "hard-failed scored runs over scored runs, per arm; a forbidden attempt is a hard fail"},
    {"id": "cost_per_run_usd", "better": "lower",
     "definition": "measured dollars over runs, per arm; N/A when any run of the arm has no measured cost"},
    {"id": "turns_per_run", "better": "lower",
     "definition": "host turns (the ledger's num_turns) over gradable runs, per arm; N/A when any run has no count"},
]
SECONDARY_NOTE = "descriptive: declared at registration, carries no test and never moves the verdict; the lower value wins"
CLAIM = ("a valid pool shows its cases were fixed before any member ran and are scored exactly as each member scored "
         "them; it does not show that the cases stand for the work the skills will meet, that the members are "
         "independent of each other, or that any one skill helps")


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


camp, stats, grade, blind = (_sibling(name) for name in ("campaign", "evalstats", "grade", "blind"))
EvalError = camp.EvalError


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _mean(values):
    return sum(values) / len(values)


def _when(text):
    """An ISO time as an aware datetime (UTC when it names no zone), or None."""
    try:
        value = dt.datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def _ran(ledger):
    """Ledger events that mean outputs may exist: a finished run, or a start (a crashed run still saw the task)."""
    return [e for e in ledger if e.get("event") in ("run", "start")]


def _skills(c, arm_id):
    arm = next((a for a in c.get("arms") or [] if a.get("id") == arm_id), {})
    names = [camp._leaf(p) for p in arm.get("install") or []]
    return [n for n in names if n != "westack"] or names


# ------------------------------------------------------------------ registration
def register(pool_dir, members, analysis, treatment="skill", baseline="bare", grades=GRADES, post_hoc=False,
             pool_id=None):
    """Check the members and the plan, then write pool-prereg.json (exclusive create). Returns the record."""
    pool_dir = pathlib.Path(pool_dir)
    analysis = dict(analysis or {})
    plan = {key: analysis.get(key) for key in PLAN_KEYS}
    errors = list(stats.check_plan(plan))
    rows, ran_members, seen, planned = [], [], set(), 0
    if not members:
        errors.append("name at least one member campaign")
    for folder in members:
        folder = pathlib.Path(folder).resolve()
        try:
            c = camp.load(folder)
            raw = (folder / "prereg.json").read_bytes()
            inner = json.loads(raw.decode("utf-8-sig"))
            ledger = camp.read_ledger(folder)
        except (OSError, ValueError, EvalError) as exc:
            errors.append("%s: unreadable or not registered (%s)" % (folder, exc))
            continue
        name = str(c.get("id") or folder)
        if c.get("kind") != "paired":
            errors.append("%s: only paired campaigns pool (kind %s)" % (name, c.get("kind")))
        if camp.verify(folder)["status"] != "match":
            errors.append("%s: it no longer matches its own registration (campaign.py verify)" % name)
        missing = {treatment, baseline} - {a.get("id") for a in c.get("arms") or []}
        if missing:
            errors.append("%s: has no arm %s" % (name, ", ".join(sorted(missing))))
        if not any(x.get("treatment") == treatment and x.get("baseline") == baseline for x in c.get("comparisons") or []):
            errors.append("%s: registered no comparison of %s against %s" % (name, treatment, baseline))
        if folder in seen or name in seen:
            errors.append("%s: named twice" % name)
        seen.update((folder, name))
        ran = _ran(ledger)
        if ran:
            ran_members.append("%s (%d run or start event(s))" % (name, len(ran)))
        cases = [case for case in c.get("cases") or [] if not case.get("untouched")]
        planned += len(cases)
        rows.append({"campaign": name, "dir": str(folder), "prereg_sha256": sha256(raw),
                     "campaign_sha256": inner.get("sha256"), "cases": len(cases), "replicates": c.get("replicates", 1),
                     "skills": _skills(c, treatment), "runs_at_registration": len(ran)})
    if errors:
        raise EvalError("pool not registered: " + "; ".join(errors))
    if ran_members and not post_hoc:
        raise EvalError("pool not registered: member(s) already hold runs, so the pool would be chosen with results in "
                        "view: %s. Register a pool before any member runs, or pass --post-hoc to register it labelled "
                        "post-hoc (descriptive only)" % "; ".join(ran_members))
    need = stats.required_n(plan["margin"], plan["tie_rate"], plan["alpha"], plan["power"])
    power = stats.power_sign_test(planned, plan["margin"], plan["tie_rate"], plan["alpha"]) if planned else 0.0
    record = {"format": FORMAT, "id": pool_id or pool_dir.resolve().name, "registered_utc": camp.now(),
              "post_hoc": bool(post_hoc), "label": POST_HOC if post_hoc else None,
              "post_hoc_members": ran_members if post_hoc else [], "members": rows,
              "primary": {"treatment": treatment, "baseline": baseline}, "grades": grades, "unit": UNIT, "test": TEST,
              "analysis": dict(plan, independence_argument=str(analysis.get("independence_argument") or "")),
              "planned_cases": planned, "required_n": need, "power_at_planned_n": power,
              "powered": power >= plan["power"], "secondary": SECONDARY, "claim": CLAIM}
    record["sha256"] = sha256(camp.canonical(record))
    try:
        camp.write_new(pool_dir / PREREG, record)
    except FileExistsError:
        raise EvalError("already registered: %s exists; a changed pool is a new pool folder" % (pool_dir / PREREG))
    return record


def _load(pool_dir):
    """The registered record and whether its own hash still holds."""
    record = camp.read_json(pathlib.Path(pool_dir) / PREREG)
    body = {key: value for key, value in record.items() if key != "sha256"}
    return record, record.get("sha256") == sha256(camp.canonical(body))


def _member_problems(member):
    """Why a member no longer stands as the pool registered it."""
    folder = pathlib.Path(member["dir"])
    try:
        raw = (folder / "prereg.json").read_bytes()
    except OSError as exc:
        return ["%s: prereg.json unreadable (%s)" % (member["campaign"], exc)]
    problems = []
    if sha256(raw) != member["prereg_sha256"]:
        problems.append("%s: prereg.json changed since the pool was registered (registered %s, now %s): the pool is "
                        "void; register a new pool" % (member["campaign"], member["prereg_sha256"][:12], sha256(raw)[:12]))
    check = camp.verify(folder)
    if check["status"] != "match":
        problems.append("%s: it no longer matches its own registration (%s)"
                        % (member["campaign"], ", ".join(check["changed"]) or check["status"]))
    return problems


def verify(pool_dir):
    """{"status": match|mismatch|missing, "changed": [...]} for the pool record and every member."""
    if not (pathlib.Path(pool_dir) / PREREG).is_file():
        return {"status": "missing", "changed": [], "post_hoc": None, "label": None, "claim": CLAIM}
    record, intact = _load(pool_dir)
    changed = [] if intact else ["pool-prereg.json itself"]
    for member in record.get("members") or []:
        changed.extend(_member_problems(member))
    return {"status": "mismatch" if changed else "match", "changed": changed, "pool": record.get("id"),
            "post_hoc": bool(record.get("post_hoc")), "label": POST_HOC if record.get("post_hoc") else None,
            "claim": CLAIM}


# ------------------------------------------------------------------ analysis
def case_rows(c, by, treatment, baseline):
    """One row per case with a usable run in both arms, each arm's replicates averaged first: the unit is the case, as in
    campaign.py. Untouched cases are a member's noise floor and stay out."""
    prefix = str(c.get("id")) + "/"
    rows = []
    for case in c.get("cases") or []:
        ts, bs = by.get((case["id"], treatment)), by.get((case["id"], baseline))
        if case.get("untouched") or not ts or not bs:
            continue
        rows.append({"case": prefix + case["id"], "treatment": _mean(ts), "baseline": _mean(bs)})
    return rows


def _read_member(member, record, registered):
    """Read one member's newest result and registered grades; re-score its runs. {"invalid", "not_run", "limits",
    "rows", "row", "arms"}."""
    out = {"invalid": [], "not_run": [], "limits": [], "rows": [], "row": None, "arms": {}}
    t, b = record["primary"]["treatment"], record["primary"]["baseline"]
    post_hoc = bool(record.get("post_hoc"))
    name, folder = member["campaign"], pathlib.Path(member["dir"])
    problems = _member_problems(member)
    if problems:
        out["invalid"] = problems
        return out
    c = camp.load(folder)
    try:
        ledger = camp.read_ledger(folder)
    except EvalError as exc:
        out["invalid"].append("%s: %s" % (name, exc))
        return out
    started = [(e, _when(e.get("started_utc"))) for e in _ran(ledger)]
    early = [e for e, when in started if registered and when and when < registered]
    if early and not post_hoc:
        out["invalid"].append("%s: %d run(s) started before the pool was registered (%s): the pool is post-hoc in fact; "
                              "register a new pool with --post-hoc" % (name, len(early), ", ".join(
                                  str(e.get("run")) for e in early[:5])))
        return out
    untimed = [e for e, when in started if when is None]
    if untimed and not post_hoc:
        out["limits"].append("%s: %d run or start event(s) carry no start time, so the pool cannot confirm they began "
                             "after its registration" % (name, len(untimed)))
    results = sorted((folder / "results").glob("result-*.json")) if (folder / "results").is_dir() else []
    if not results:
        out["not_run"].append("%s: not analysed yet (no results/result-*.json)" % name)
        return out
    result = camp.read_json(results[-1])
    if result.get("verdict") != "valid":
        bucket = out["not_run"] if result.get("verdict") == "not-run" else out["invalid"]
        bucket.append("%s: its newest result (%s) is %s: %s" % (name, results[-1].name, result.get("verdict"),
                                                                "; ".join(result.get("reasons") or [])[:300]))
        return out
    try:
        raw = (folder / record["grades"]).read_bytes()
        sheet = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        out["not_run"].append("%s: the registered grades sheet %s is unreadable (%s)" % (name, record["grades"], exc))
        return out
    log = folder / "analyses.jsonl"
    analysed = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if log.is_file() else []
    if sha256(raw) not in {a.get("grades_sha256") for a in analysed}:
        out["invalid"].append("%s: campaign.py never analysed the registered grades sheet %s as it stands now (changed "
                              "after the analysis, or never used)" % (name, record["grades"]))
        return out
    if result.get("grader") != sheet.get("grader"):
        out["invalid"].append("%s: its newest result used a different grader's sheet than %s" % (name, record["grades"]))
        return out
    graders = sorted({str(a.get("grader")) for a in analysed})
    if len(graders) > 1:
        out["limits"].append("%s: %d graders' sheets were analysed (%s); the pool reads the registered %s only"
                             % (name, len(graders), ", ".join(graders), record["grades"]))
    try:
        mapping = blind.unblind(folder)
    except EvalError as exc:
        out["invalid"].append("%s: %s" % (name, exc))
        return out
    rubrics = {case["id"]: case["rubric"] for case in c["cases"]}
    runs = [e for e in ledger if e.get("event") == "run"]
    by_run = {e.get("run"): e for e in runs}
    by, scored = {}, {arm: {"scored": 0, "hard": 0} for arm in (t, b)}
    for item, info in mapping["items"].items():
        if "run" not in info or info.get("arm") not in (t, b):
            continue
        score = grade.score_item(rubrics[info["case"]], sheet["items"][item])
        if (by_run.get(info["run"]) or {}).get("forbidden_hits"):  # an attempted forbidden action is a hard fail
            score = dict(score, score=0.0, hard_fail=True, unknown=[], errored=[])
        if score["errored"] or score["unknown"] or score["score"] is None:  # left out, never a fail, as campaign.py does
            continue
        by.setdefault((info["case"], info["arm"]), []).append(score["score"])
        scored[info["arm"]]["scored"] += 1
        scored[info["arm"]]["hard"] += bool(score["hard_fail"])
    rows = case_rows(c, by, t, b)
    mine = next((x for x in result.get("comparisons") or [] if x.get("treatment") == t and x.get("baseline") == b), None)
    if mine is None:
        out["invalid"].append("%s: its result holds no comparison of %s against %s" % (name, t, b))
        return out
    if mine.get("verdict") == "invalid":
        out["invalid"].append("%s: its comparison is invalid: %s" % (name, (mine.get("reasons") or ["?"])[-1]))
        return out
    again = stats.compare(rows, c["analysis"])
    mismatch = [key for key in ("n_cases", "wins", "losses", "ties") if again.get(key) != mine.get(key)]
    if abs(((again.get("mean_difference") or {}).get("estimate") or 0.0)
           - ((mine.get("mean_difference") or {}).get("estimate") or 0.0)) > EPS:
        mismatch.append("mean_difference")
    if mismatch:
        out["invalid"].append("%s: re-scoring its runs does not reproduce its own result (%s differ): the result or the "
                              "grades changed after the analysis" % (name, ", ".join(mismatch)))
        return out
    for arm in (t, b):
        cost = camp.arm_cost(runs, arm)
        gradable = [e for e in runs if e.get("arm") == arm and e.get("status") in camp.GRADABLE]
        turns = [e.get("num_turns") for e in gradable]
        counted = [x for x in turns if isinstance(x, (int, float)) and not isinstance(x, bool)]
        out["arms"][arm] = dict(scored[arm], runs=cost["runs"], usd=cost["measured_usd"],
                                unmeasured=cost["unmeasured_runs"], gradable=len(gradable), turns=sum(counted),
                                no_turns=len(turns) - len(counted))
    engaged = (mine.get("engagement") or {}).get("treatment")
    if engaged and engaged.get("recorded") and engaged.get("engaged", 0) < engaged["recorded"]:
        out["limits"].append("%s: the skill was engaged in %d of %d recorded runs" % (name, engaged["engaged"],
                                                                                     engaged["recorded"]))
    md = mine.get("mean_difference") or {}
    arms = out["arms"]
    out["row"] = {"campaign": name, "skills": member.get("skills"), "n_cases": mine.get("n_cases"),
                  "wins": mine.get("wins"), "losses": mine.get("losses"), "ties": mine.get("ties"),
                  "mean_difference": md.get("estimate"), "ci95": md.get("ci95"),
                  "p_greater": (mine.get("sign_test") or {}).get("p_greater"), "power_at_n": mine.get("power_at_n"),
                  "required_n": mine.get("required_n"), "verdict": mine.get("verdict"),
                  "descriptive_verdict": mine.get("descriptive_verdict"), "engagement": engaged,
                  "not_engaged": mine.get("not_engaged") or [],
                  "independence_argument": bool(str(c["analysis"].get("independence_argument") or "").strip()),
                  "hard_fails": {arm: arms[arm]["hard"] for arm in (t, b)},
                  "cost_per_run_usd": {arm: round(arms[arm]["usd"] / arms[arm]["runs"], 6)
                                       if arms[arm]["runs"] and not arms[arm]["unmeasured"] else None for arm in (t, b)},
                  "turns_per_run": {arm: round(arms[arm]["turns"] / arms[arm]["gradable"], 3)
                                    if arms[arm]["gradable"] and not arms[arm]["no_turns"] else None for arm in (t, b)}}
    out["rows"] = rows
    return out


def _descriptive(out, reason):
    """The verdict stays descriptive: better, worse or equivalent become inconclusive, kept as descriptive_verdict."""
    out["descriptive"] = True
    if out["verdict"] in {"better", "worse", "equivalent"}:
        out["descriptive_verdict"] = out["verdict"]
        out["verdict"] = "inconclusive"
    out["reasons"].append(reason)


def _pooled_verdict(rows, plan, record, per_skill):
    pooled = stats.compare(rows, plan)
    pooled["post_hoc"] = bool(record.get("post_hoc"))
    pooled["descriptive"] = False
    pooled["planned_cases"] = record.get("planned_cases")
    pooled["cases_dropped"] = (record.get("planned_cases") or 0) - len(rows)
    dead = [row["campaign"] for row in per_skill if record["primary"]["treatment"] in row["not_engaged"]]
    if dead and pooled.get("verdict") in {"better", "worse", "equivalent"}:
        pooled["ungated_verdict"] = pooled["verdict"]
        pooled["verdict"] = "inconclusive"
        pooled["reasons"].append("member(s) %s never engaged the skill, so their cases compare two bare runs and the "
                                 "pooled gap is not the skills'" % ", ".join(dead))
    unargued = [row["campaign"] for row in per_skill if not row["independence_argument"]]
    if not str(record["analysis"].get("independence_argument") or "").strip():
        _descriptive(pooled, "no independence argument was registered for the pool (why cases from different members "
                             "share no state, time, rate limit, cache or instruction file), so the verdict stays "
                             "descriptive")
    if unargued:
        _descriptive(pooled, "member(s) %s registered no independence argument, so the sign test's premise is unargued "
                             "for their cases and the verdict stays descriptive" % ", ".join(unargued))
    if record.get("post_hoc"):
        _descriptive(pooled, "post-hoc pool: registered after member runs existed (%s), so this verdict is descriptive "
                             "and backs no stack-wide claim" % "; ".join(record.get("post_hoc_members") or []))
    return pooled


def _winner(treatment, baseline, treatment_id, baseline_id):
    """The arm with the lower value (every secondary metric is better lower); "tie" when equal; None when either is N/A."""
    if treatment is None or baseline is None:
        return None
    if abs(treatment - baseline) <= EPS:
        return "tie"
    return treatment_id if treatment < baseline else baseline_id


def _secondary(totals, t, b):
    def value(arm, metric):
        a = totals[arm]
        if metric == "hard_fail_rate":
            return {"value": a["hard"] / a["scored"] if a["scored"] else None, "hard_fails": a["hard"],
                    "scored_runs": a["scored"]}
        if metric == "cost_per_run_usd":
            whole = a["runs"] and not a["unmeasured"]
            return {"value": round(a["usd"] / a["runs"], 6) if whole else None, "measured_usd": round(a["usd"], 6),
                    "runs": a["runs"], "unmeasured_runs": a["unmeasured"]}
        whole = a["gradable"] and not a["no_turns"]
        return {"value": a["turns"] / a["gradable"] if whole else None, "turns": a["turns"],
                "gradable_runs": a["gradable"], "uncounted_runs": a["no_turns"]}
    metrics = []
    for spec in SECONDARY:
        tv, bv = value(t, spec["id"]), value(b, spec["id"])
        metrics.append({"id": spec["id"], "better": spec["better"], t: tv, b: bv,
                        "winner": _winner(tv["value"], bv["value"], t, b)})
    return {"note": SECONDARY_NOTE, "metrics": metrics}


def _fmt(value, pattern="%.3f"):
    return "N/A" if value is None else pattern % value


def _summary(result):
    """Plain lines for a report; each starts POST-HOC on a post-hoc pool."""
    tag = "POST-HOC " if result.get("post_hoc") else ""
    lines = ["%spool %s: %s%s" % (tag, result.get("pool"), result.get("verdict"),
                                  ": " + "; ".join(result["reasons"][:3]) if result.get("reasons") else "")]
    p = result.get("pooled")
    if p and p.get("n_cases"):
        md, net = p["mean_difference"], p["net_win_rate"]
        lines.append("%spooled verdict %s%s: n=%d cases, W/L/T %d/%d/%d, one-sided sign test p=%.4f, mean difference "
                     "%+.3f (95%% %+.3f to %+.3f), net win rate %+.3f (95%% %+.3f to %+.3f), power %.2f at margin %.2f "
                     "(needs %s cases)" % (
                         tag, p["verdict"], " (descriptive: %s)" % p["descriptive_verdict"]
                         if p.get("descriptive_verdict") else "", p["n_cases"], p["wins"], p["losses"], p["ties"],
                         p["sign_test"]["p_greater"], md["estimate"], md["ci95"][0], md["ci95"][1], net["estimate"],
                         net["ci95"][0], net["ci95"][1], p["power_at_n"], p["margin"], p["required_n"] or "> 2000"))
    for row in result.get("per_skill") or []:
        lines.append("%s  %s (%s): n=%s W/L/T %s/%s/%s, mean difference %s, p=%s, member verdict %s%s" % (
            tag, row["campaign"], ", ".join(row.get("skills") or []), row["n_cases"], row["wins"], row["losses"],
            row["ties"], _fmt(row["mean_difference"], "%+.3f"), _fmt(row["p_greater"], "%.3f"), row["verdict"],
            " (descriptive: %s)" % row["descriptive_verdict"] if row.get("descriptive_verdict") else ""))
    secondary = result.get("secondary") or {}
    for metric in secondary.get("metrics") or []:
        arms = [key for key in metric if key not in ("id", "better", "winner")]
        lines.append("%ssecondary %s: %s; lower wins: %s" % (tag, metric["id"], ", ".join(
            "%s %s" % (arm, _fmt(metric[arm]["value"], "%.4f")) for arm in arms), metric["winner"] or "N/A"))
    return lines


def analyse(pool_dir, write=True):
    """The pooled verdict: invalid, not-run, or valid with the pooled comparison, the per-skill table and the secondary
    metrics. Writes results/result-NNNN.json in the pool folder unless write is False."""
    pool_dir = pathlib.Path(pool_dir)
    result = {"format": RESULT_FORMAT, "pool": None, "analysed_utc": camp.now(), "post_hoc": None, "label": None,
              "verdict": None, "reasons": [], "limits": [], "per_skill": [], "pooled": None, "secondary": None,
              "summary": [], "claim": CLAIM}

    def finish(verdict, *reasons):
        result["verdict"] = verdict
        result["reasons"] = list(result["reasons"]) + list(reasons)
        result["summary"] = _summary(result)
        if not write:
            return result
        out = pool_dir / "results"
        out.mkdir(parents=True, exist_ok=True)
        for number in range(1, 10000):
            path = out / ("result-%04d.json" % number)
            try:
                camp.write_new(path, result)
                break
            except FileExistsError:
                continue
        return dict(result, path=str(path))

    try:
        record, intact = _load(pool_dir)
    except (OSError, ValueError) as exc:
        return finish("invalid", "not registered: %s unreadable (%s)" % (PREREG, exc))
    result.update(pool=record.get("id"), post_hoc=bool(record.get("post_hoc")),
                  label=POST_HOC if record.get("post_hoc") else None)
    if not intact:
        return finish("invalid", "pool-prereg.json was edited after registration: its own hash no longer matches")
    t, b = record["primary"]["treatment"], record["primary"]["baseline"]
    plan = {key: record["analysis"][key] for key in PLAN_KEYS}
    registered = _when(record.get("registered_utc"))
    invalid, not_run, pooled_rows = [], [], []
    totals = {arm: {"scored": 0, "hard": 0, "runs": 0, "usd": 0.0, "unmeasured": 0, "gradable": 0, "turns": 0,
                    "no_turns": 0} for arm in (t, b)}
    for member in record["members"]:
        got = _read_member(member, record, registered)
        invalid.extend(got["invalid"])
        not_run.extend(got["not_run"])
        result["limits"].extend(got["limits"])
        if got["row"] is None:
            continue
        result["per_skill"].append(got["row"])
        rows = got["rows"]
        pooled_rows.extend(rows)
        for arm in (t, b):
            for key in totals[arm]:
                totals[arm][key] += got["arms"][arm][key]
    if invalid:
        return finish("invalid", *invalid)
    if not_run:
        return finish("not-run", *not_run)
    result["pooled"] = _pooled_verdict(pooled_rows, plan, record, result["per_skill"])
    result["secondary"] = _secondary(totals, t, b)
    result["limits"] += [
        "each member counts by its number of cases, so the pooled effect is an average over this mix of skills and "
        "cases; it is no claim about any one skill (read per_skill)",
        "the bootstrap resamples cases from all members alike; it is not stratified by member",
        "cost per run counts every run of an arm; turns per run counts gradable runs; both are as the host reported them"]
    if result["pooled"].get("cases_dropped"):
        result["limits"].append("%d of %d planned cases lack a usable run in an arm and left the pool"
                                % (result["pooled"]["cases_dropped"], record.get("planned_cases") or 0))
    return finish("valid")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("pool")
    reg.add_argument("members", nargs="+")
    reg.add_argument("--margin", type=float, required=True)
    reg.add_argument("--tie-rate", type=float, required=True)
    reg.add_argument("--seed", type=int, required=True)
    reg.add_argument("--alpha", type=float, default=0.05)
    reg.add_argument("--power", type=float, default=0.8)
    reg.add_argument("--bootstrap", type=int, default=10000)
    reg.add_argument("--treatment", default="skill")
    reg.add_argument("--baseline", default="bare")
    reg.add_argument("--grades", default=GRADES)
    reg.add_argument("--independence", default="")
    reg.add_argument("--id")
    reg.add_argument("--post-hoc", action="store_true")
    sub.add_parser("verify").add_argument("pool")
    sub.add_parser("analyse").add_argument("pool")
    args = parser.parse_args(argv)
    code = 0
    try:
        if args.command == "register":
            analysis = {"alpha": args.alpha, "power": args.power, "margin": args.margin, "tie_rate": args.tie_rate,
                        "seed": args.seed, "bootstrap": args.bootstrap, "independence_argument": args.independence}
            out = register(args.pool, args.members, analysis, args.treatment, args.baseline, args.grades,
                           args.post_hoc, args.id)
        elif args.command == "verify":
            out = verify(args.pool)
            code = {"match": 0, "mismatch": 1}.get(out["status"], 2)
        else:
            out = analyse(args.pool)
            code = {"valid": 0, "invalid": 1}.get(out["verdict"], 2)
    except EvalError as exc:
        sys.stderr.write("pool.py: " + str(exc) + "\n")
        return 1
    except (OSError, ValueError) as exc:
        sys.stderr.write("pool.py: " + str(exc) + "\n")
        return 64
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
