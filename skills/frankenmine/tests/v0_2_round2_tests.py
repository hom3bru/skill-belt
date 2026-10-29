"""Frankenmine 0.2.0 round-2 review: byte-bound records, rights against routes, lite checking, helpers.

Each case was written before the behaviour it tests and run red against the earlier helper.
Only authored fixtures and this package's helpers run; no donor code is imported or executed,
and every write stays under the caller's results directory.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import fixture_builder
from fixture_builder import make_run, fm, PACKAGE

LITE_FIXTURE = PACKAGE / "tests" / "fixtures" / "lite"
SCRIPT = PACKAGE / "scripts" / "frankenmine.py"


def _review_fallback(record, root):
    """Pre-round-2 helpers have no review artifact; keep the base ready so each case shows its own gap."""
    record["review"].update(author="Synthetic builder", reviewer="Fresh reviewer subagent",
                            independence="fresh-context-same-model", disposition="accepted",
                            findings=["Minor: synthetic positive control only"], adjudication="Accepted for the fixture")
    record["review"].pop("independent", None)


def run_tests(test, scratch):
    root = scratch / "round2"
    authored = make_run(root)
    base = copy.deepcopy(authored)
    if hasattr(fm, "CODE_ROUTES"):
        fixture_builder.accept_review(base, root)
    else:
        # Red run against the pre-round-2 helper: its schema knows neither basis nor review.report.
        _review_fallback(base, root)
        for c in base["candidates"]:
            c.pop("basis", None)
    base["unresolved"] = []

    def cand(record, ident):
        return next(c for c in record["candidates"] if c["id"] == ident)

    def errors_of(mutate, start=None):
        record = copy.deepcopy(start or base)
        mutate(record)
        return fm.check(record, root)

    def expect(mutate, *texts, start=None):
        errors = errors_of(mutate, start)
        for text in texts:
            assert any(text in item for item in errors), (text, errors)
        return errors

    def clean(mutate, start=None):
        errors = errors_of(mutate, start)
        assert errors == [], errors
        return "no readiness errors"

    def cli(*parts, cwd=None):
        command = [sys.executable, "-B", str(SCRIPT), *map(str, parts)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, cwd=cwd)
        payload = result.stdout or result.stderr
        try:
            data = json.loads(payload)
        except ValueError:
            data = {"raw": payload}
        return result.returncode, data

    def unique(name):
        target = scratch / "round2-out" / name
        assert not target.exists(), target
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def write_record(record, name):
        path = root / name
        if path.exists():
            path.unlink()
        path.write_text(fm.encode(record), encoding="utf-8")
        return path

    test("round-2 positive control is design-ready", lambda: clean(lambda r: None))

    # --- 1. rights against the reuse route ------------------------------------------------------
    def code_route(route, category="open-source", basis="licensed-reuse", closure=None):
        def mutate(r):
            c = cand(r, "component-math")
            c["route"] = route
            c.pop("basis", None)
            c["rights"].update(category=category, route=basis, license="MIT",
                               obligations=["Keep the MIT notice in NOTICE"], rationale="Copied source keeps its notice")
            c["closure"] = closure or ["none: the unit imports nothing beyond the language runtime"]
            if route in ("process", "rpc"):
                c["protocol"] = dict(version_rejection="Reject any frame whose version is not 1",
                                     authentication="Child process over pipes; no listener",
                                     idempotency="Requests carry the event identity",
                                     reordering_duplicates="Single ordered pipe; the ledger resolves duplicates",
                                     backpressure="One request in flight", shutdown_restart_identity="Stateless child",
                                     performance_budget="Under 50 ms per 1,000 events")
        return mutate

    test("narrow-port of proprietary code under idea-only rights is rejected", lambda: expect(
        code_route("narrow-port", category="proprietary", basis="idea-only"), "reuses donor code"))
    test("dependency route under idea-only rights is rejected", lambda: expect(
        code_route("dependency", basis="idea-only"), "reuses donor code"))
    test("source-available code needs a permission rights basis", lambda: expect(
        code_route("narrow-port", category="source-available"), "permission"))
    test("source-available code with explicit permission passes", lambda: clean(
        code_route("narrow-port", category="source-available", basis="permission")))
    test("open-source narrow-port with a licensed-reuse basis passes", lambda: clean(code_route("narrow-port")))
    test("a 1.1 selected unit needs a rights category", lambda: expect(
        lambda r: cand(r, "component-game")["rights"].pop("category"), "rights.category"))
    test("selected reimplementation must declare its basis", lambda: expect(
        lambda r: cand(r, "component-math").pop("basis", None), "basis"))

    def code_basis_idea_rights(r):
        cand(r, "component-math")["basis"] = "code"
    test("reimplementation from code needs code-reuse rights, not idea-only", lambda: expect(
        code_basis_idea_rights, "reuses donor code"))
    test("reimplementation from the idea may rest on idea-only rights", lambda: clean(
        lambda r: cand(r, "component-math").update(basis="idea")))
    test("a code route cannot describe retained dependencies as free text", lambda: expect(
        code_route("dependency", closure=["left-pad and big-dep"]), "structured closure"))

    retained = dict(name="left-pad", pin="1.3.0", category="open-source", disposition="retain",
                    license="MIT", obligations=["Keep the MIT notice"], evidence=["ev-math"])
    test("a structured retained dependency passes", lambda: clean(code_route("dependency", closure=[dict(retained)])))
    for name, change, text in (
            ("unknown licence category", dict(category="unknown"), "licence category"),
            ("unresolved disposition", dict(disposition="unresolved"), "unresolved"),
            ("floating version range", dict(pin="^1.3.0"), "exact pin"),
            ("proprietary dependency without permission", dict(category="proprietary"), "permission")):
        test("retained dependency rejects " + name, lambda c=change, t=text: expect(
            code_route("dependency", closure=[dict(retained, **c)]), t))

    # --- 2. receipts bound to product bytes -------------------------------------------------------
    product_rel = "product/replay_total.py"

    def implemented(r):
        target = root / product_rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((PACKAGE / "examples/synthetic/replay_total.py").read_bytes())
        sha = fm.digest(target.read_bytes())
        r["mode"] = "implementation"
        r["artifacts"] = [dict(path=product_rel, sha256=sha, origin="authored",
                               candidates=["component-game", "component-math"])]
        r["receipts"] = []
        for t in r["tests"]:
            t["status"] = "pass"
            raw = root / "r2-raw" / (t["id"] + ".txt")
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text("authored receipt fixture for " + t["id"] + "\n", encoding="utf-8")
            r["receipts"].append(dict(id="r2-" + t["id"], test=t["id"], command="python -B oracle.py",
                environment="authored fixture", raw_output="r2-raw/" + raw.name, raw_sha256=fm.digest(raw.read_bytes()),
                exit_code=0, cases=4, passed=4, failed=0, skipped=0,
                control_detected=t["purpose"] == "negative-control",
                artifacts=[dict(path=product_rel, sha256=sha)]))
        for c in r["candidates"]:
            c["implementation"] = "tested"

    test("tested parts with artifact-bound receipts pass", lambda: clean(implemented))

    def no_artifacts(r):
        implemented(r)
        r.pop("artifacts", None)
        for receipt in r["receipts"]:
            receipt.pop("artifacts", None)
    test("tested claims need receipts that list product artifacts", lambda: expect(no_artifacts, "artifact"))

    def stale(r):
        implemented(r)
        for receipt in r["receipts"]:
            receipt["artifacts"][0]["sha256"] = "0" * 64
    test("a receipt whose artifact bytes changed is stale", lambda: expect(stale, "stale"))

    def unlisted(r):
        implemented(r)
        r["receipts"][0]["artifacts"] = [dict(path="oracle.py", sha256=fm.digest((root / "oracle.py").read_bytes()))]
    test("a receipt artifact must be in the artifact manifest", lambda: expect(unlisted, "artifact manifest"))

    def shared_raw(declared):
        def mutate(r):
            implemented(r)
            first = r["receipts"][0]
            for receipt in r["receipts"][1:]:
                receipt.update(raw_output=first["raw_output"], raw_sha256=first["raw_sha256"])
                if declared:
                    receipt["raw_shared"] = "One oracle run printed every case into one log"
            if declared:
                first["raw_shared"] = "One oracle run printed every case into one log"
        return mutate
    test("receipts cannot silently share one raw output", lambda: expect(shared_raw(False), "raw output"))
    test("declared raw-output sharing is accepted", lambda: clean(shared_raw(True)))

    def reused_from_idea(r):
        implemented(r)
        r["artifacts"][0].update(origin="reused", unit="donors/exact_math/total.js")
    test("reused product code cannot come from idea-only parts", lambda: expect(reused_from_idea, "reused"))

    def reused_without_unit(r):
        implemented(r)
        r["artifacts"][0].update(origin="adapted")
        r["artifacts"][0].pop("unit", None)
    test("reused or adapted artifacts name their donor unit", lambda: expect(reused_without_unit, "unit"))

    test("an oracle may not be a donor file", lambda: expect(
        lambda r: r["tests"][0].update(oracle="donors/exact_math/total.js",
                                       oracle_sha256=fm.digest((root / "donors/exact_math/total.js").read_bytes())),
        "donor"))

    def oracle_in_snapshot_folder(r):
        target = root / "donors/exact_math/oracle_copy.py"
        target.write_bytes((root / "oracle.py").read_bytes())
        r["tests"][0].update(oracle="donors/exact_math/oracle_copy.py", oracle_sha256=fm.digest(target.read_bytes()))
    test("an oracle may not sit inside a donor snapshot folder", lambda: expect(oracle_in_snapshot_folder, "donor"))

    # --- 4. interactions ---------------------------------------------------------------------------
    def independent_empty(r):
        for c in r["candidates"]:
            c["touches"] = []
        r["interactions"] = [dict(components=["component-game", "component-math"], status="independent",
                                  rationale="They share nothing at all")]
    test("independent needs non-empty touches on both sides", lambda: expect(independent_empty, "non-empty touches"))

    def third_part(r):
        donor = copy.deepcopy(next(d for d in r["donors"] if d["id"] == "game"))
        donor["id"] = "game2"
        r["donors"].append(donor)
        ev = copy.deepcopy(next(e for e in r["evidence"] if e["id"] == "ev-game"))
        ev.update(id="ev-game2", donor="game2")
        r["evidence"].append(ev)
        for d in [x for x in r["discoveries"] if x["donor"] == "game"]:
            twin = copy.deepcopy(d)
            twin.update(id=d["id"] + "-2", donor="game2", evidence=["ev-game2"])
            r["discoveries"].append(twin)
        c = copy.deepcopy(cand(r, "component-game"))
        c.update(id="component-audit", donor="game2", evidence=["ev-game2"],
                 discovery=["game-target-led-2", "game-donor-led-2"], touches=["state:entries"])
        c["seam"]["evidence"] = ["ev-game2"]
        c["rights"]["evidence"] = ["ev-game2"]
        r["candidates"].append(c)
        for other in ("component-game", "component-math"):
            r["interactions"].append(dict(components=[other, "component-audit"], status="resolved",
                                          rationale="Pairwise ordering through ReplayTotal", evidence=["ev-game2"],
                                          test="integrate-game-math"))

    test("a key touched by three parts needs a group interaction", lambda: expect(third_part, "group interaction"))

    def group(purpose):
        def mutate(r):
            third_part(r)
            r["tests"].append(dict(copy.deepcopy(r["tests"][-1]), id="integrate-all-three", purpose=purpose,
                                   spec="All three parts in one replay: identity, audit and arithmetic"))
            r["interactions"].append(dict(components=["component-game", "component-math", "component-audit"],
                                          status="resolved", rationale="ReplayTotal sequences all three on one ledger",
                                          evidence=["ev-game", "ev-math", "ev-game2"], test="integrate-all-three"))
        return mutate
    test("a group interaction verified by an integration test passes", lambda: clean(group("integration")))
    test("a group interaction cannot rest on a pairwise interaction test", lambda: expect(
        group("interaction"), "integration test"))

    # --- 5. the review is an artifact ----------------------------------------------------------------
    test("an accepted review needs a saved report", lambda: expect(
        lambda r: r["review"].pop("report", None), "review report"))
    test("the review report is hash-checked", lambda: expect(
        lambda r: r["review"].update(report=dict(r["review"].get("report", {"path": "review/design-review.md"}),
                                                 sha256="0" * 64)), "hash mismatch"))

    def report_wrong_reviewer(r):
        target = root / "review" / "other-review.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Reviewer: Someone else\nIndependence: human\nFindings:\n- none\n", encoding="utf-8")
        r["review"]["report"] = dict(path="review/other-review.md", sha256=fm.digest(target.read_bytes()))
    test("the review report must name the recorded reviewer and level", lambda: expect(
        report_wrong_reviewer, "review report"))
    test("an accepted review records at least one finding", lambda: expect(
        lambda r: r["review"].update(findings=[]), "finding"))

    def packet():
        record = copy.deepcopy(base)
        record["decision"]["rationale"] = "SECRET-RATIONALE-MARKER chosen because it is best"
        source = write_record(record, "packet-run.json")
        out = unique("packet")
        code, data = cli("review-packet", source, "--output", out)
        assert code == 0, data
        text = (out / "PACKET.md").read_text(encoding="utf-8")
        assert "SECRET-RATIONALE-MARKER" not in text and "Decision:" not in text, text[:400]
        assert record["brief"]["outcome"] in text
        copied = out / "files" / "donors/exact_math/total.js"
        assert fm.digest(copied.read_bytes()) == fm.digest((root / "donors/exact_math/total.js").read_bytes())
        assert (out / "files" / "oracle.py").exists() and (out / "REVIEW-TEMPLATE.md").exists()
        again, _ = cli("review-packet", source, "--output", out)
        assert again == 2, "packet output directory must not be reused"
        inside, _ = cli("review-packet", source, "--output", PACKAGE / "review-packet-should-not-exist")
        assert inside == 2 and not (PACKAGE / "review-packet-should-not-exist").exists()
        return "packet withholds the decision and rationale; copies evidence and oracles; never reuses a folder"
    test("review-packet writes a conclusion-free packet", packet)

    # --- 6. authoring helpers ---------------------------------------------------------------------------
    def stamp():
        record = copy.deepcopy(base)
        implemented(record)
        record["evidence"][0].pop("sha256")
        record["evidence"][1].pop("revision")
        record["tests"][0]["oracle_sha256"] = ""
        record["receipts"][0].pop("raw_sha256")
        record["receipts"][0]["artifacts"][0].pop("sha256")
        record["artifacts"][0].pop("sha256")
        record["review"]["report"].pop("sha256", None)
        source = write_record(record, "stamp-in.json")
        before = source.read_bytes()
        out = unique("stamped.json")
        code, data = cli("stamp", source, "--output", out)
        assert code == 0, data
        assert source.read_bytes() == before, "stamp must never edit in place"
        stamped = fm.load_json(out)
        assert fm.check(stamped, root) == [], fm.check(stamped, root)
        again, _ = cli("stamp", source, "--output", out)
        assert again == 2, "stamp must not replace an existing output"
        wrong = copy.deepcopy(record)
        wrong["tests"][1]["oracle_sha256"] = "0" * 64
        source2 = write_record(wrong, "stamp-wrong.json")
        out2 = unique("stamped-wrong.json")
        code2, data2 = cli("stamp", source2, "--output", out2)
        assert code2 == 2 and fm.load_json(out2)["tests"][1]["oracle_sha256"] == "0" * 64, data2
        return "missing hashes filled into a new file; a recorded hash that disagrees is reported, never rewritten"
    test("stamp fills missing hashes without rewriting recorded ones", stamp)

    def scaffold():
        source = write_record(copy.deepcopy(base), "scaffold-in.json")
        assert fm.check(fm.load_json(source), root) == []
        out = unique("scaffolded.json")
        code, data = cli("scaffold", source, "--donor", "math", "--unit", "donors/exact_math/total.js",
                         "--route", "narrow-port", "--id", "component-port", "--output", out)
        assert code == 0, data
        record = fm.load_json(out)
        new = cand(record, "component-port")
        assert sorted(d["dimension"] for d in new["deltas"]) == sorted(fm.SEMANTIC_DIMENSIONS)
        assert fm.check(record, root), "scaffolding must never make a record pass"
        selected = copy.deepcopy(record)
        cand(selected, "component-port")["phase"] = "selected"
        assert any("placeholder" in e or "scaffold" in e for e in fm.check(selected, root))
        return "scaffolded candidate carries 13 placeholder deltas and blocks readiness"
    test("scaffold adds a blocking candidate stub", scaffold)

    def scaffold_before_stamp():
        record = copy.deepcopy(base)
        for e in record["evidence"]:
            e.pop("sha256")
            e.pop("revision")
        record["tests"][0].pop("oracle_sha256")
        source = write_record(record, "scaffold-unstamped.json")
        out = unique("scaffolded-unstamped.json")
        code, data = cli("scaffold", source, "--donor", "game", "--unit", "donors/game_save/checkpoint.py",
                         "--route", "pattern-only", "--id", "component-lesson", "--output", out)
        assert code == 0, data
        bad = copy.deepcopy(record)
        bad["evidence"][0]["start_line"] = "one"
        source2 = write_record(bad, "scaffold-malformed.json")
        code2, _ = cli("scaffold", source2, "--donor", "game", "--unit", "x", "--route", "pattern-only",
                       "--id", "component-x", "--output", unique("scaffolded-malformed.json"))
        assert code2 == 2, "a record malformed beyond missing hashes is refused"
        return "scaffold works before stamp; other schema errors still refuse"
    test("scaffold accepts a record that only lacks stampable hashes", scaffold_before_stamp)

    def slim_delta(r):
        for d in cand(r, "component-math")["deltas"]:
            if d["status"] == "not-applicable":
                for key in ("donor_semantics", "target_semantics", "conversion", "test"):
                    d.pop(key, None)
                d["reason"] = "n/a: " + d["reason"]
    test("a not-applicable delta needs only its reason", lambda: clean(slim_delta))
    test("a mapped delta still needs its conversion", lambda: expect(
        lambda r: next(d for d in cand(r, "component-math")["deltas"] if d["status"] == "mapped").pop("conversion"),
        "conversion"))
    test("an honest none: <reason> is content", lambda: clean(
        lambda r: cand(r, "component-math")["seam"].update(permissions_effects="none: pure in-memory computation")))
    for text in ("None", "To do", "WIP", "Not yet known"):
        test("placeholder " + repr(text) + " blocks readiness", lambda t=text: expect(
            lambda r: cand(r, "component-math").update(recovery=t), "placeholder"))

    # --- 7. language identity -------------------------------------------------------------------------
    def js_as_python(r):
        c = cand(r, "component-math")
        c.update(source_language="Python", deltas=[])
        next(d for d in r["donors"] if d["id"] == "math")["languages"] = ["JavaScript", "Python"]
    test("a .js unit declared as Python is flagged", lambda: expect(js_as_python, "extension"))

    # --- 8. coverage under every decision -----------------------------------------------------------------
    def fresh_unmapped(r):
        r["decision"].update(choice="minimal-fresh", rationale="A fresh class is simpler")
        cand(r, "component-math").update(route="pattern-only", deltas=[])
        cand(r, "component-math").pop("basis", None)
        r["brief"]["requirements"].append(dict(id="audit", criterion="Operators can export an audit log"))
    test("minimal-fresh must map every requirement", lambda: expect(fresh_unmapped, "audit"))

    def best_existing_mapped(r):
        r["decision"].update(choice="best-existing", rationale="An existing ledger tool meets both needs")
        for c in r["candidates"]:
            c.update(route="pattern-only", deltas=[])
            c.pop("basis", None)
        r["requirement_coverage"] = [dict(requirement="once", by=["existing:Ledger tool"]),
                                     dict(requirement="exact", by=["existing:Ledger tool"])]
    test("best-existing may map requirements to existing:<product>", lambda: clean(best_existing_mapped))

    # --- 10/11. donor searches and licence scans -----------------------------------------------------------
    search = dict(id="search-1", source="PyPI and GitHub", query="exact decimal ledger replay", date="2026-10-28",
                  considered=["ledgerlib", "exact_math"], chosen=["exact_math"], rejected=["ledgerlib"],
                  reason="ledgerlib rounds through floats; exact_math keeps strings")

    def with_search(r):
        r["discovery_searches"] = [dict(search)]
        r["alternatives"][0]["evidence"].append("search-1")
    test("donor search records are accepted and citable", lambda: clean(with_search))
    test("a donor search needs a real reason", lambda: expect(
        lambda r: (with_search(r), r["discovery_searches"][0].update(reason="TBD")), "placeholder"))

    def license_scan(tool_version="32.0.8"):
        def mutate(r):
            target = root / "scans" / "math-scancode.json"
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('{"files": [{"path": "total.js", "licenses": []}]}\n', encoding="utf-8")
            item = dict(id="scan-math", kind="license-scan", donor="math", tool="ScanCode Toolkit",
                        snapshot="scans/math-scancode.json", sha256=fm.digest(target.read_bytes()),
                        scope="ScanCode output for the math donor snapshot", limitations="Detection, not a legal ruling")
            if tool_version:
                item["tool_version"] = tool_version
            r.setdefault("supporting_evidence", []).append(item)
            cand(r, "component-math")["rights"]["evidence"].append("scan-math")
        return mutate
    test("licence-scan output can support rights", lambda: clean(license_scan()))
    test("licence-scan evidence names the tool version", lambda: expect(license_scan(None), "tool_version"))

    # --- 12. Pareto view --------------------------------------------------------------------------------
    def dims(values):
        def mutate(r):
            for alt in r["alternatives"]:
                cost, outcome = values[alt["kind"]]
                alt["dimensions"] = [dict(name="cost", value=cost, direction="lower"),
                                     dict(name="user outcome", value=outcome, direction="higher")]
        return mutate

    def pareto():
        record = copy.deepcopy(base)
        dims({"best-existing": (3, 2), "minimal-fresh": (1, 3), "fusion": (2, 3)})(record)
        errors = fm.check(record, root)
        assert errors == [], errors
        text = fm.report(record, errors)
        assert "Pareto set" in text and "dominated" in text, text
        line = next(x for x in text.splitlines() if "Pareto set" in x)
        assert "minimal" in line and "best" not in line, line
        assert "chooses a dominated alternative" in text
        return "non-dominated set computed; a dominated decision is flagged in the report"
    test("report computes the Pareto set from structured dimensions", pareto)

    def mixed_direction(r):
        dims({"best-existing": (3, 2), "minimal-fresh": (1, 3), "fusion": (2, 3)})(r)
        r["alternatives"][0]["dimensions"][0]["direction"] = "higher"
    test("a dimension keeps one direction across alternatives", lambda: expect(mixed_direction, "direction"))

    # --- 9. handoff ----------------------------------------------------------------------------------------
    def handoff_design():
        from synthesis_handoff import build_index
        record = copy.deepcopy(base)
        index = build_index(record, root / "run.json", fm.check(record, root))
        contract = next(c for c in index["contracts"] if c["id"] == "component-game")
        assert contract["integration"]["status"] == "declared", contract["integration"]
        assert not any(p["kind"] == "test" and p["state"] == "not-run" for p in index["pending"]), index["pending"]
        assert index["next"]["kind"] == "authorization", index["next"]
        implementation = copy.deepcopy(record)
        implementation["mode"] = "implementation"
        index = build_index(implementation, root / "run.json", fm.check(implementation, root))
        assert any(p["kind"] == "test" and p["state"] == "not-run" for p in index["pending"]), index["pending"]
        return "design mode: integration declared, not-run tests expected, next step is implementation authority"
    test("handoff reports declared integration and respects design mode", handoff_design)

    # --- 3. lite path: the slim lite tier is tested in v0_2_lite_tests.py ---------------------------------------

    # --- fooling regressions from the round-2 review ----------------------------------------------------------
    def simulated_review(r):
        r["review"].update(reviewer="SIMULATED fresh subagent (not actually run)", adjudication="SIMULATED")
    test("a review that names a reviewer its report does not carry is rejected", lambda: expect(
        simulated_review, "review report"))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not __debug__:
        parser.error("Tests require assertions; remove -O/PYTHONOPTIMIZE")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    results = []

    def test(name, fn):
        try:
            results.append(dict(name=name, status="pass", detail=fn()))
        except Exception:
            results.append(dict(name=name, status="fail", raw=traceback.format_exc()))
    run_tests(test, out)
    summary = dict(total=len(results), passed=sum(r["status"] == "pass" for r in results),
                   failed=sum(r["status"] == "fail" for r in results))
    (out / "results.json").write_text(json.dumps(dict(summary, tests=results), indent=2, ensure_ascii=False, default=str)
                                      + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    raise SystemExit(1 if summary["failed"] else 0)
