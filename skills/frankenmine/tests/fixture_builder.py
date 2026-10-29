"""Reproducible authored development fixture (schema 1.1); no third-party donor execution.

`make_run` builds examples/synthetic/run.json and `make_no_fusion` builds
examples/no-fusion/run.json; tests compare the shipped files with these builders.
"""
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
import frankenmine as fm

DONOR_FILES = ("donors/game_save/checkpoint.py", "donors/exact_math/total.js")
DELTAS = [
    # (dimension, status, donor semantics, target semantics, conversion, reason)
    ("numeric", "mapped", "BigInt arbitrary-precision integers; Number would round above 2**53",
     "Python int, arbitrary precision", "Sum Python ints; serialize totals as decimal strings",
     "Frozen oracle sums values above 2**53"),
    ("null_missing", "mapped", "BigInt('') and BigInt('  ') return 0n, so empty input silently counts as zero",
     "Empty, whitespace-only and None amounts raise ValueError before any state change",
     "Reject; never default a missing amount to zero", "Oracle feeds '', '  ' and None and expects rejection"),
    ("unicode_regex", "mapped",
     "BigInt accepts surrounding whitespace and 0x/0o/0b prefixes; it rejects non-ASCII digits and underscores",
     "Python int() accepts non-ASCII digits (int('٣') is 3), underscores ('1_000') and whitespace",
     "Validate with the ASCII-only pattern 0|-?[1-9][0-9]* before int()",
     "Oracle feeds ' 12', '0x10', '٣', '1_000', '+1', '007' and '-0' and expects rejection"),
    ("equality_order", "same", "Integer addition is order-independent", "Same for Python int addition",
     "No conversion; totals are recomputed from stored entries", "Oracle compares two insertion orders"),
    ("time_units", "not-applicable", "No clocks, time zones or units in the unit", "No time handling retained",
     "No conversion required", "Amounts are unitless integer minor units"),
    ("errors", "mapped", "BigInt throws SyntaxError on malformed text and reduce stops midway",
     "ValueError raised before mutation; the ledger is unchanged on failure",
     "Validate each event completely before mutating", "Oracle checks state is unchanged after rejected input"),
    ("async_cancellation", "not-applicable", "Synchronous reduce", "Synchronous method calls",
     "No conversion required", "Neither side schedules or cancels work"),
    ("ownership", "not-applicable", "Strings are immutable values", "Strings are immutable values",
     "No conversion required", "No shared mutable object crosses the boundary"),
    ("memory_threads", "not-applicable", "Single-threaded event loop", "Single-threaded calls; caller serializes access",
     "No conversion required", "No concurrent access in the slice contract"),
    ("persistence_transactions", "not-applicable", "The donor unit persists nothing",
     "Checkpointing is new product behaviour", "No conversion required",
     "Covered by the product oracle rather than donor parity"),
    ("abi_layout", "not-applicable", "No native boundary", "Pure-language reimplementation",
     "No conversion required", "Nothing crosses an ABI"),
    ("serialization", "mapped", "Returns the total as a decimal string via toString()",
     "Totals and checkpoint amounts are decimal strings; checkpoints carry version 1",
     "str(int) for output; strict parsing on restore", "Oracle restores a snapshot and rejects version 2"),
    ("initialization", "same", "reduce starts from 0n", "An empty ledger totals '0'",
     "No conversion; the derived total starts from zero", "Oracle checks a fresh ledger totals '0'"),
]


def _pin(tag, data):
    return tag + "@sha256:" + fm.digest(data)


def make_run(root):
    source = PACKAGE / "examples/synthetic"
    root.mkdir(parents=True, exist_ok=True)
    for rel in DONOR_FILES + ("oracle.py",):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((source / rel).read_bytes())
    run = fm.skeleton()
    run.update(id="synthetic-replay-total", synthetic=True)
    run["brief"] = dict(outcome="New resumable exact batch total", users="Batch import operator",
        question="product-led", non_goals=["No database, service, deployment or donor execution"],
        requirements=[dict(id="once", criterion="Replay/resume must apply each identity once and reject conflicts"),
                      dict(id="exact", criterion="Exact decimal string arithmetic beyond 2**53")],
        constraints=["Task-authored disposable fixtures only", "No implicit approvals or network"],
        target_language="Python", write_scope="This disposable run directory",
        authorization="Local package/example tests only; donor source is data")
    raw = {path: (root / path).read_bytes() for path in DONOR_FILES}
    game_path, math_path = DONOR_FILES
    revisions = {"game": _pin("game-v1", raw[game_path]), "math": _pin("math-v1", raw[math_path])}
    run["donors"] = [
        dict(id="game", url="fixture://game", revision=revisions["game"], languages=["Python"], status="reviewed",
             reason="Authored fixture source inspected; not executed", scope=game_path + " complete file",
             blind_spots=["No production donor/environment coverage"]),
        dict(id="math", url="fixture://math", revision=revisions["math"], languages=["JavaScript"], status="reviewed",
             reason="Authored fixture source inspected; not executed", scope=math_path + " complete file",
             blind_spots=["No production donor/environment coverage"])]
    run["evidence"] = [
        dict(id="ev-" + donor, donor=donor, revision=revisions[donor], path=path, start_line=1,
             end_line=len(raw[path].splitlines()), kind="present", scope="Complete authored fixture",
             limitations="Source inspection only; synthetic evidence, no current external donor inspection",
             snapshot=path, sha256=fm.digest(raw[path]))
        for donor, path in (("game", game_path), ("math", math_path))]
    run["discoveries"] = [
        dict(id="game-target-led", donor="game", direction="target-led",
             problem="A batch import replayed after interruption applies the same event twice",
             mechanism="Membership set checked before mutation; remember() refuses a seen checkpoint",
             invariant="Each identity is applied at most once", assumptions="Callers supply identities that are stable across restarts",
             target_need="once", evidence=["ev-game"], falsifier="Replaying a completed batch changes the total",
             stage="candidate", disposition="promising", rationale="Directly serves the replay requirement"),
        dict(id="game-donor-led", donor="game", direction="donor-led",
             problem="Unlock flows need to know whether an unlock was new, not just record it",
             mechanism="remember() returns a first-seen boolean, so one call both records and reports novelty",
             invariant="The caller learns whether this call changed state without a second lookup",
             assumptions="Callers act on the signal instead of discarding it",
             target_need="hypothesis: expose a replay counter so operators see how much of a resumed batch was already applied",
             evidence=["ev-game"], falsifier="Operators never use the count, or counting still needs a second lookup",
             stage="hypothesis", disposition="promising",
             rationale="Beyond the donor's purpose: the return value is an observability hook, not only deduplication"),
        dict(id="math-target-led", donor="math", direction="target-led",
             problem="Totals above 2**53 lose precision with binary floats",
             mechanism="Exact BigInt reduction over decimal strings", invariant="No rounding at any magnitude",
             assumptions="Inputs are integer minor units written as strings", target_need="exact", evidence=["ev-math"],
             falsifier="2**53 + 1 sums incorrectly", stage="candidate", disposition="promising",
             rationale="Directly serves the exact-arithmetic requirement"),
        dict(id="math-donor-led", donor="math", direction="donor-led",
             problem="Values crossing a JSON or JavaScript boundary silently become floats",
             mechanism="Amounts and totals stay decimal strings at every interface; exact integers exist only inside",
             invariant="Serialized state never holds a binary float amount",
             assumptions="Every consumer parses strings rather than JSON numbers",
             target_need="hypothesis: checkpoint files stay exact when another runtime reads them",
             evidence=["ev-math"], falsifier="A consumer that reads the checkpoint as JSON numbers loses digits",
             stage="lesson", disposition="promising",
             rationale="Beyond arithmetic: a representation rule for the checkpoint format")]
    seams = {
        "game": dict(exports_consumers="Donor remember(seen, checkpoint) has one caller shape; ReplayTotal.add re-expresses it",
            closure="Donor unit uses only a built-in set; nothing is imported from the fixture",
            initialization="Donor relies on a caller-created set; ReplayTotal creates its ledger in __init__",
            state_transactions="Donor mutates the caller's set; ReplayTotal owns entries and validates before mutating",
            resources_lifetime="No files, sockets or handles in either side",
            concurrency_cancellation="Single-threaded calls; caller serializes access; no async",
            errors_retries="Donor never raises; product raises ValueError before mutation and returns False on a same-value retry",
            serialization="Donor keeps no format; product snapshots a versioned dictionary",
            permissions_effects="In-memory computation only; checkpoint I/O belongs to the caller",
            tests="Frozen independent oracle plus disconnected-dedupe control",
            licensing="Locally authored fixture; no external source copied", evidence=["ev-game"]),
        "math": dict(exports_consumers="Donor total(decimalStrings) reduces an array; ReplayTotal.total derives the sum",
            closure="Donor uses only BigInt; the Python slice uses only int",
            initialization="Donor starts from 0n; an empty ledger totals '0'",
            state_transactions="Donor is stateless; ReplayTotal owns entries",
            resources_lifetime="No files, sockets or handles in either side",
            concurrency_cancellation="Synchronous on both sides; no async",
            errors_retries="Donor throws SyntaxError midway; product validates every event before mutation",
            serialization="Decimal strings at every interface; versioned checkpoint",
            permissions_effects="In-memory computation only",
            tests="Frozen independent oracle plus lossy-numeric control",
            licensing="Locally authored fixture; no external source copied", evidence=["ev-math"])}
    common = dict(phase="selected", implementation="not-started",
        closure=["No third-party dependencies; built-in set or integer arithmetic"],
        target_language="Python", owner="ReplayTotal", caller="Batch importer",
        contract="Canonical decimal-string integer events applied once; conflicting duplicates reject",
        approval_boundary="Local authored example only; no donor execution, publication, credentials or host mutation",
        recovery="Atomic in-memory validation; versioned checkpoint restore; caller persists checkpoint",
        maintenance="Example maintainer owns the Python slice and frozen product oracle",
        update_strategy="Review source changes against pinned snapshots; rerun oracle and controls",
        falsifier="Frozen oracle accepts a disconnected contribution",
        alternative="A tiny fresh implementation may be simpler than reuse; no measured superiority claim")
    rights = lambda donor, path: dict(status="reviewed", route="idea-only", category="task-authored",
        license="Task-authored synthetic fixture", unit=path, evidence=["ev-" + donor],
        obligations=["Preserve synthetic provenance"],
        rationale="Original fixture and new implementation authored for this task; no third-party reuse")
    run["candidates"] = [
        dict(common, id="component-game", donor="game", evidence=["ev-game"],
             discovery=["game-target-led", "game-donor-led"], need=["once"], unit=game_path, route="pattern-only",
             touches=["state:entries", "policy:duplicate"], seam=seams["game"], rights=rights("game", game_path),
             source_language="Python", deltas=[],
             intentional_changes="Conflicting duplicates raise instead of returning False; identities must be nonempty strings",
             acceptance="accept-game", negative_control="control-game"),
        dict(common, id="component-math", donor="math", evidence=["ev-math"],
             discovery=["math-target-led", "math-donor-led"], need=["exact"], unit=math_path, route="reimplementation",
             basis="idea",
             touches=["state:entries", "policy:error"], seam=seams["math"], rights=rights("math", math_path),
             source_language="JavaScript",
             deltas=[dict(dimension=d, status=s, donor_semantics=ds, target_semantics=ts, conversion=cv,
                          test="not-applicable" if s == "not-applicable" else "accept-math", reason=why)
                     for d, s, ds, ts, cv, why in DELTAS],
             intentional_changes="Reject booleans, floats, empty and noncanonical strings; no permissive BigInt or int() coercion",
             acceptance="accept-math", negative_control="control-math")]
    run["requirement_coverage"] = [dict(requirement="once", by=["component-game", "new:ReplayTotal"]),
                                   dict(requirement="exact", by=["component-math", "new:ReplayTotal"])]
    run["ownership"] = [dict(key=key, owner="ReplayTotal", rationale="Single ledger; derived totals and one public API") for key in
                        ("state:entries", "policy:duplicate", "policy:error", "transition:add", "interface:batch")]
    run["interactions"] = [dict(components=["component-game", "component-math"], status="resolved",
        rationale="Both touch state:entries: the identity check runs before amount parsing, so a conflicting duplicate is rejected before arithmetic",
        evidence=["ev-game", "ev-math"], test="integrate-game-math")]
    run["global_review"] = dict(cycles="Acyclic one-class slice; no controller loops",
        shared_versions="Version 1 checkpoint schema rejects unknown versions",
        resource_budget="Linear memory in unique identities; bounded example only",
        higher_order="Two donors only; no higher-order set beyond the pair")
    run["alternatives"] = [
        dict(kind="best-existing", name="Exact-math donor alone", evidence=["ev-math"],
             tradeoffs="Exact totals but no identity/restart contract; a production alternative search is out of fixture scope"),
        dict(kind="minimal-fresh", name="One fresh ledger class", evidence=["ev-game", "ev-math"],
             tradeoffs="Likely equally simple; mechanism-level inspiration only; no demonstrated fusion advantage"),
        dict(kind="fusion", name="Game identity lesson + reimplemented exact decimal boundary", evidence=["ev-game", "ev-math"],
             tradeoffs="Small new authored slice, one owner, no extra runtime; demonstrates method not superiority")]
    run["decision"] = dict(choice="fusion", rationale="Teaching fixture: reimplements one donor's exact arithmetic and applies "
                           "another's identity lesson in one new class; production choice remains unevaluated")
    sha = fm.digest((root / "oracle.py").read_bytes())
    specs = {"accept-": "Run frozen >2**53/replay/conflict/malformed/canonical-spelling/order/restart cases",
             "control-game": "Disconnect duplicate protection", "control-math": "Introduce floating-point rounding"}
    run["tests"] = [dict(id=prefix + donor, purpose="product" if prefix == "accept-" else "negative-control",
        spec=specs["accept-"] if prefix == "accept-" else specs[prefix + donor],
        oracle="oracle.py", oracle_sha256=sha, frozen=True, status="not-run")
        for donor in ("game", "math") for prefix in ("accept-", "control-")]
    run["tests"].append(dict(id="integrate-game-math", purpose="integration",
        spec="Identity check precedes amount parsing: a conflicting replay is rejected and the exact total is unchanged",
        oracle="oracle.py", oracle_sha256=sha, frozen=True, status="not-run"))
    run["review"] = dict(author="Example builder", reviewer="Builder self-review", independence="self", disposition="not-run",
        findings=["Independent design reviewer has not evaluated this authored example"],
        adjudication="Leave blocked; no independent review or live-agent qualification claimed")
    run["unresolved"] = ["Independent design review and production baseline comparison not run"]
    return run


def make_no_fusion(root):
    """Minimal fresh build that keeps both donor lessons as selected pattern-only provenance."""
    run = make_run(root)
    run["id"] = "minimal-fresh-wins"
    math = run["candidates"][1]
    math.pop("basis")
    math.update(route="pattern-only", deltas=[],
                intentional_changes="Only the decimal-string representation lesson is applied; no donor code or behaviour is reimplemented")
    run["requirement_coverage"] = [dict(requirement="once", by=["component-game", "new:Fresh ledger class"]),
                                   dict(requirement="exact", by=["component-math", "new:Fresh ledger class"])]
    run["decision"] = dict(choice="minimal-fresh", rationale="For this tiny fixture a new class is cheaper than carrying "
                           "transplanted code; both donor lessons stay selected as pattern-only with provenance.")
    return run


def accept_review(run, root, reviewer="Fresh reviewer subagent", independence="fresh-context-same-model"):
    """Test-only positive control: a saved review report whose bytes the record cites. Not a real review."""
    text = ("Reviewer: " + reviewer + "\nIndependence: " + independence + "\n"
            "Findings:\n- Minor: synthetic positive-control fixture; no design was actually reviewed.\n")
    path = Path(root) / "review" / "design-review.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    run["review"] = dict(author="Synthetic builder", reviewer=reviewer, independence=independence,
                         disposition="accepted", findings=["Minor: synthetic positive-control fixture only"],
                         adjudication="Accepted for the validator fixture; not a real review",
                         report=dict(path="review/design-review.md", sha256=fm.digest(path.read_bytes())))
    return run


if __name__ == "__main__":
    dest = Path(sys.argv[1])
    variant = sys.argv[2] if len(sys.argv) > 2 else "synthetic"
    record = (make_no_fusion if variant == "no-fusion" else make_run)(dest)
    fm.write_new(dest / "run.json", fm.encode(record))
