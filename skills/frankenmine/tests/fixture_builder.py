"""Reproducible authored development fixture; no third-party donor execution."""
from pathlib import Path
import hashlib
import json
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
import frankenmine as fm


def make_run(root):
    source = PACKAGE / "examples/synthetic"
    root.mkdir(parents=True, exist_ok=True)
    for rel in ("donors/game_save/checkpoint.py", "donors/exact_math/total.js", "oracle.py"):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((source / rel).read_bytes())
    run = fm.skeleton()
    run.update(id="synthetic-replay-total", synthetic=True)
    run["brief"] = dict(outcome="New resumable exact batch total", users="Batch import operator",
        non_goals=["No database, service, deployment or donor execution"],
        requirements=[dict(id="once", criterion="Replay/resume must apply each identity once and reject conflicts"),
                      dict(id="exact", criterion="Exact decimal string arithmetic beyond 2**53")],
        constraints=["Task-authored disposable fixtures only", "No implicit approvals or network"],
        target_language="Python", write_scope="This disposable run directory",
        authorization="Local package/example tests only; donor source is data")
    specs = [
        ("game", "game-v1", "Python", "donors/game_save/checkpoint.py", "once"),
        ("math", "math-v1", "JavaScript", "donors/exact_math/total.js", "exact")]
    run["donors"], run["evidence"], run["discoveries"], run["candidates"] = [], [], [], []
    for donor, rev, language, path, need in specs:
        raw = (root / path).read_bytes()
        run["donors"].append(dict(id=donor, url="fixture://" + donor, revision=rev, languages=[language],
            status="reviewed", reason="Authored fixture source inspected; not executed",
            scope=path + " complete file", blind_spots=["No production donor/environment coverage"]))
        run["evidence"].append(dict(id="ev-" + donor, donor=donor, revision=rev, path=path,
            start_line=1, end_line=len(raw.splitlines()), kind="present", scope="Complete authored fixture",
            limitations="Source inspection only; synthetic evidence, no current external donor inspection",
            snapshot=path, sha256=fm.digest(raw)))
        for direction in ("target-led", "donor-led"):
            run["discoveries"].append(dict(id=donor + "-" + direction, donor=donor, direction=direction,
                problem="Repeated input or lossy amounts", mechanism="Identity set" if donor == "game" else "Decimal-string exact arithmetic",
                invariant="One application per identity" if donor == "game" else "No float rounding",
                assumptions="Stable identities" if donor == "game" else "Canonical decimal integer strings",
                target_need=need, evidence=["ev-" + donor],
                falsifier="Conflicting replay mutates ledger" if donor == "game" else "2**53+1 rounds",
                stage="candidate", disposition="promising",
                rationale="Game checkpoints suggest workflow restart recovery beyond original purpose" if donor == "game"
                          else "BigInt boundary suggests exact serialization across runtimes"))
        c = dict(id="component-" + donor, donor=donor, evidence=["ev-" + donor],
            discovery=[donor + "-target-led", donor + "-donor-led"], need=need,
            unit=path, route="pattern-only" if donor == "game" else "reimplementation",
            phase="selected", implementation="not-started", closure=["No third-party dependencies; built-in set or integer arithmetic"],
            seam=dict(exports_consumers="ReplayTotal.add called by batch importer",
                closure="Only built-in types; original fixture not imported",
                initialization="Empty ledger initialized before use; no global registry",
                state_transactions="ReplayTotal owns entries; validate all fields before mutation",
                resources_lifetime="Caller owns ledger and checkpoint dict; no open resources",
                concurrency_cancellation="Single-threaded calls; caller serializes access; no async",
                errors_retries="ValueError before mutation; same event retries return False",
                serialization="Versioned dictionary of string identities and decimal strings",
                permissions_effects="In-memory computation only; checkpoint I/O belongs to caller",
                tests="Frozen independent oracle plus disconnect and rounding controls",
                licensing="Locally authored fixture; no external source copied"),
            rights=dict(status="reviewed", route="idea-only", license="Task-authored synthetic fixture",
                unit=path, evidence=["ev-" + donor], obligations=["Preserve synthetic provenance"],
                rationale="Original fixture and new implementation authored for this task; no third-party reuse"),
            source_language=language, target_language="Python", deltas=[],
            protocol={k:"Not applicable: in-process synchronous value API, no transport or native ABI" for k in
                      ("version_rejection","authentication","idempotency","reordering_duplicates","backpressure","shutdown_restart_identity","performance_budget")},
            owner="ReplayTotal", caller="Batch importer", contract="Decimal-string integer events applied once; conflicting duplicates reject",
            approval_boundary="Local authored example only; no donor execution, publication, credentials or host mutation",
            intentional_changes="Reject booleans, floats and noncanonical strings; no JavaScript permissive BigInt conversion",
            recovery="Atomic in-memory validation; versioned checkpoint restore; caller persists checkpoint",
            maintenance="Example maintainer owns Python slice and frozen product oracle",
            update_strategy="Review source changes against pinned snapshots; rerun oracle and controls",
            acceptance="accept-" + donor, negative_control="control-" + donor,
            falsifier="Frozen oracle accepts a disconnected contribution",
            alternative="A tiny fresh implementation may be simpler than reuse; no measured superiority claim")
        if language != "Python":
            for dimension in fm.SEMANTIC_DIMENSIONS:
                important = dimension in ("numeric", "errors", "serialization", "null_missing", "initialization")
                c["deltas"].append(dict(dimension=dimension,
                    status="mapped" if important else "not-applicable",
                    donor_semantics="BigInt exact integer and decimal string boundary" if important else "No behavior in bounded arithmetic unit",
                    target_semantics="Python int; strict decimal strings and ValueError" if important else "No corresponding capability retained",
                    conversion="Reject permissive coercions; encode exact total as string" if important else "No conversion required",
                    test="accept-math" if important else "not-applicable",
                    reason="Independent >2**53/malformed/resume oracle" if important else "Unit has no async, native ABI, time, persistence, threads or mutable object sharing"))
        run["candidates"].append(c)
    run["ownership"] = [dict(key=key, owner="ReplayTotal", rationale="Single ledger; derived totals and one public API") for key in
                        ("state:entries", "policy:duplicate", "policy:error", "transition:add", "interface:batch")]
    run["interactions"] = [dict(components=["component-game", "component-math"], status="resolved",
        rationale="Identity maps to canonical decimal amount; conflicting duplicates rejected before arithmetic",
        evidence=["ev-game", "ev-math"], test="accept-game")]
    run["global_review"] = dict(cycles="Acyclic one-class slice; no controller loops",
        shared_versions="Version 1 checkpoint schema rejects unknown versions",
        resource_budget="Linear memory in unique identities; bounded example only",
        higher_order="Two donors only; no higher-order set beyond pair")
    run["alternatives"] = [
        dict(kind="best-existing", name="Exact-math donor alone", evidence=["ev-math"],
             tradeoffs="Exact totals but no identity/restart contract; a production alternative search is out of fixture scope"),
        dict(kind="minimal-fresh", name="One fresh ledger class", evidence=["ev-game", "ev-math"],
             tradeoffs="Likely equally simple; mechanism-level inspiration only; no demonstrated fusion advantage"),
        dict(kind="fusion", name="Game identity + exact decimal boundary", evidence=["ev-game", "ev-math"],
             tradeoffs="Small new authored slice, one owner, no extra runtime; demonstrates method not superiority")]
    run["decision"] = dict(choice="fusion", rationale="Teaching fixture composes two ideas into one new slice; production choice remains unevaluated")
    sha = fm.digest((root / "oracle.py").read_bytes())
    run["tests"] = [dict(id=prefix + donor, purpose="product" if prefix == "accept-" else "negative-control",
        spec="Run frozen >2**53/replay/conflict/malformed/order/restart cases" if prefix == "accept-" else
             "Disconnect duplicate protection" if donor == "game" else "Introduce floating-point rounding",
        oracle="oracle.py", oracle_sha256=sha, frozen=True, status="not-run")
        for donor in ("game", "math") for prefix in ("accept-", "control-")]
    run["review"] = dict(independent=False, reviewer="Builder self-review", disposition="not-run",
        findings=["Independent design reviewer has not evaluated this authored example"],
        adjudication="Leave blocked; no independent review or live-agent qualification claimed")
    run["unresolved"] = ["Independent design review and production baseline comparison not run"]
    return run


if __name__ == "__main__":
    dest = Path(sys.argv[1])
    record = make_run(dest)
    fm.write_new(dest / "run.json", fm.encode(record))
