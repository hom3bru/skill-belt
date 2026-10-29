"""Frankenmine 0.2.0 behaviour tests: schema 1.1, readiness gates, report, examples.

Only authored fixtures and this package's helpers run; no donor code is imported or executed.
All writes stay under the caller's results directory. On pre-0.2 helpers the positive base is
the 1.0 control used by run_tests.py, so a red run shows each behavioural gap directly.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import fixture_builder
from fixture_builder import make_run, fm, PACKAGE

NEW = hasattr(fm, "SCHEMAS")
LEGACY = PACKAGE / "tests" / "fixtures" / "schema-1.0"
SCHEMA_1_0_SHA256 = "3300aec48b685d99b17f4fb16c88f65f144467d852b284adfc9e340fbe81ba40"
PROTOCOL_KEYS = ("version_rejection", "authentication", "idempotency", "reordering_duplicates",
                 "backpressure", "shutdown_restart_identity", "performance_budget")
PIN_HINT = "(full commit hash, or <immutable-tag>@sha256:<64-hex digest>)"
UNRESOLVED = "unresolved items remain; resolve or scope out blockers before readiness"
LEGACY_REVIEW = ("independent design review not accepted: disposition not-run; record review.independence "
                 "(self | fresh-context-same-model | different-model | human; schema 1.1); "
                 "record review.author (schema 1.1)")
LEGACY_COMMON = {
    "game: donor-led discovery game-donor-led duplicates target-led game-target-led; "
    "record a genuinely donor-led lesson (or a bounded no-gain search)",
    "math: donor-led discovery math-donor-led duplicates target-led math-target-led; "
    "record a genuinely donor-led lesson (or a bounded no-gain search)",
    UNRESOLVED, LEGACY_REVIEW}
LEGACY_SELECTED = LEGACY_COMMON | {
    "component-game: selected donor game needs a real pin, not 'game-v1' " + PIN_HINT,
    "component-math: selected donor math needs a real pin, not 'math-v1' " + PIN_HINT,
    "component-game: seam lacks evidence links (add seam.evidence; schema 1.1)",
    "component-math: seam lacks evidence links (add seam.evidence; schema 1.1)",
    "interaction component-game / component-math: test accept-game has purpose product; verify with an "
    "interaction or integration test (a negative control cannot verify an interaction)"}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_tests(test, scratch):
    root = scratch / "v0-2"
    authored = make_run(root)
    base = copy.deepcopy(authored)
    if NEW:
        fixture_builder.accept_review(base, root, reviewer="Synthetic positive-control reviewer")
    else:
        base["review"].update(reviewer="Synthetic positive-control reviewer", disposition="accepted",
                              findings=[], adjudication="Artificial validator fixture only", independent=True)
    base["unresolved"] = []

    def cand(record, ident):
        return next(c for c in record["candidates"] if c["id"] == ident)

    def errors_of(mutate):
        record = copy.deepcopy(base)
        mutate(record)
        return fm.check(record, root)

    def expect(mutate, *texts):
        errors = errors_of(mutate)
        for text in texts:
            assert any(text in item for item in errors), (text, errors)
        return errors

    def clean(mutate):
        errors = errors_of(mutate)
        assert errors == [], errors
        return "no readiness errors"

    test("0.2 positive control is design-ready", lambda: clean(lambda r: None))

    # --- one placeholder rule everywhere -------------------------------------------------
    def brief_placeholders(r):
        r["brief"].update(outcome="TODO", users="TBD", write_scope="TODO: isolated output root",
                          authorization="pending")
    test("brief placeholders block readiness", lambda: expect(
        brief_placeholders, "brief.outcome", "brief.users", "brief.write_scope", "brief.authorization"))

    def target_todo(r):
        r["brief"]["target_language"] = "TODO"
        for c in r["candidates"]:
            c["target_language"] = "TODO"
    test("placeholder target language blocks even when candidates agree",
         lambda: expect(target_todo, "brief.target_language"))

    for text in ("TODO: verify init order", "TBD", "N/A.", "?", "unknown.", "Unknown", "pending review",
                 "Not applicable: in-process", "n/a", "n/a: x"):
        test("seam placeholder " + repr(text) + " blocks readiness", lambda t=text: expect(
            lambda r: cand(r, "component-game")["seam"].update(initialization=t),
            "unexplained seam field initialization"))
    test("not-applicable seam text must use the n/a: <reason> form", lambda: expect(
        lambda r: cand(r, "component-game")["seam"].update(initialization="Not applicable: in-process"),
        "n/a: <reason>"))
    for text in ("n/a: the slice has no registry or import-time effects",
                 "Pending writes are flushed before restore returns",
                 "Unknown callers are rejected by the batch importer before add()"):
        test("explained seam text " + repr(text[:24]) + " is accepted", lambda t=text: clean(
            lambda r: cand(r, "component-game")["seam"].update(initialization=t)))

    placeholder_sites = [
        ("interaction rationale", lambda r: r["interactions"][0].update(rationale="TODO")),
        ("alternative tradeoffs", lambda r: r["alternatives"][0].update(tradeoffs="TBD")),
        ("decision rationale", lambda r: r["decision"].update(rationale="pending")),
        ("test spec", lambda r: r["tests"][0].update(spec="TODO: write cases")),
        ("ownership rationale", lambda r: r["ownership"][0].update(rationale="?")),
        ("candidate contract", lambda r: cand(r, "component-math").update(contract="TBD")),
        ("discovery falsifier", lambda r: r["discoveries"][0].update(falsifier="unknown")),
        ("donor reason", lambda r: r["donors"][0].update(reason="TODO")),
    ]
    for name, mutate in placeholder_sites:
        test("placeholder in " + name + " blocks readiness",
             lambda m=mutate: expect(m, "placeholder text in"))

    # --- real pins for selected donors ----------------------------------------------------
    def pin(revision):
        def mutate(r):
            for donor in r["donors"]:
                donor["revision"] = revision
            for item in r["evidence"]:
                item["revision"] = revision
        return mutate
    for revision in ("unpinned", "main", "HEAD", "game-v1", "v1.2.0", "1234567", "latest@sha256:" + "a" * 64):
        test("selected donor revision " + repr(revision[:20]) + " is not a real pin",
             lambda v=revision: expect(pin(v), "needs a real pin"))
    for revision in ("a" * 40, "v1.2.0@sha256:" + "b" * 64):
        test("selected donor revision " + repr(revision[:20]) + " is a real pin", lambda v=revision: clean(pin(v)))

    # --- ownership keys and touched surfaces ----------------------------------------------
    for key in ("State:Entries", "state:entries ", "state.entries", "STATE / entries"):
        test("ownership key variant " + repr(key) + " still conflicts", lambda k=key: expect(
            lambda r: r["ownership"].append(dict(key=k, owner="OtherLoop", rationale="Competing loop")),
            "ownership conflict"))
    test("a touched key needs an ownership entry", lambda: expect(
        lambda r: cand(r, "component-game").update(touches=["state:entries", "resource:checkpoint-file"]),
        "no ownership entry"))

    # --- review independence --------------------------------------------------------------
    def same_author(r):
        r["review"]["author"] = "Builder"
        r["review"]["reviewer"] = " builder "
    test("reviewer cannot be the author", lambda: expect(same_author, "reviewer is the author"))
    test("self independence blocks readiness", lambda: expect(
        lambda r: r["review"].update(independence="self"), "independence is self"))
    test("missing independence level blocks readiness", lambda: expect(
        lambda r: r["review"].pop("independence", None), "review.independence"))
    test("independent flag cannot contradict the level", lambda: expect(
        lambda r: r["review"].update(independence="self", independent=True), "contradicts"))

    # --- outcomes: lessons, composition and requirement coverage ---------------------------
    def fresh_with_lesson(choice):
        def mutate(r):
            cand(r, "component-math").update(route="defer", phase="deferred")
            r["interactions"] = []
            # Every decision maps every requirement; deferred parts cannot be cited.
            r["requirement_coverage"] = [dict(requirement="once", by=["component-game", "new:Fresh ledger"]),
                                         dict(requirement="exact", by=["new:Fresh ledger"])]
            r["decision"].update(choice=choice, rationale="A fresh class applies the game identity lesson")
        return mutate
    for choice in ("minimal-fresh", "best-existing"):
        test(choice + " may keep a selected pattern-only lesson", lambda c=choice: clean(fresh_with_lesson(c)))
    test("non-fusion choice still rejects a selected reuse route", lambda: expect(
        lambda r: r["decision"].update(choice="minimal-fresh"), "non-fusion choice must defer/reject"))

    def fusion_one_reuse(r):
        cand(r, "component-game").update(route="defer", phase="deferred")
        r["interactions"] = []
        r["requirement_coverage"] = [dict(requirement="once", by=["new:ReplayTotal identity ledger"]),
                                     dict(requirement="exact", by=["component-math"])]
    test("fusion with one reuse unit and new glue code is design-ready", lambda: clean(fusion_one_reuse))
    test("fusion of lessons alone needs a reuse route", lambda: expect(
        lambda r: cand(r, "component-math").update(route="pattern-only"), "reuse route"))

    def glue_requirement(r):
        r["brief"]["requirements"].append(dict(id="report", criterion="Emit a CSV summary"))
    test("unmapped glue requirement blocks fusion", lambda: expect(
        glue_requirement, "selected fusion does not account for every requirement", "report"))

    def glue_mapped(r):
        glue_requirement(r)
        r.setdefault("requirement_coverage", []).append(dict(requirement="report", by=["new:CSV summary writer"]))
    test("glue requirement mapped to new:<component> passes", lambda: clean(glue_mapped))
    coverage_errors = [
        ("unknown requirement", [dict(requirement="ghost", by=["new:Ledger"])], "unknown requirement ghost"),
        ("unknown candidate", [dict(requirement="once", by=["component-nope"])], "unknown candidate component-nope"),
        ("empty new component", [dict(requirement="once", by=["new:"])], "new:<component>"),
    ]
    for name, value, text in coverage_errors:
        test("requirement coverage rejects " + name, lambda v=value, t=text: expect(
            lambda r: r.update(requirement_coverage=v), t))
    test("a candidate need may be a list", lambda: clean(
        lambda r: cand(r, "component-game").update(need=["once"])))
    test("a listed need must be established", lambda: expect(
        lambda r: cand(r, "component-game").update(need=["once", "ghost"]), "unestablished target requirement"))

    # --- route-conditional deltas and protocol ---------------------------------------------
    def pattern_cross_language(r):
        cand(r, "component-game").update(route="reimplementation", basis="idea")
        cand(r, "component-math").update(route="pattern-only", deltas=[])
        cand(r, "component-math").pop("basis", None)
    test("cross-language pattern-only lesson needs no semantic deltas", lambda: clean(pattern_cross_language))
    test("protocol is optional outside process/rpc routes", lambda: clean(
        lambda r: [c.pop("protocol", None) for c in r["candidates"]]))

    def process_route(protocol):
        def mutate(r):
            item = cand(r, "component-math")
            item["route"] = "process"
            item.pop("basis", None)
            # A process route runs donor code, so its rights must permit code reuse.
            item["rights"].update(route="licensed-reuse")
            item["closure"] = ["none: the unit imports nothing beyond the language runtime"]
            if protocol is None:
                item.pop("protocol", None)
            else:
                item["protocol"] = dict(protocol)
        return mutate
    all_na = {k: "n/a: in-process value API; no transport" for k in PROTOCOL_KEYS}
    real = dict(version_rejection="Reject any frame whose version is not 1 before parsing",
                authentication="Local child process over pipes; parent spawns it, no network listener",
                idempotency="Each request carries the event identity; repeats return the stored result",
                reordering_duplicates="Single ordered pipe; duplicate identities resolved by the ledger",
                backpressure="Parent sends one request at a time and waits for the reply",
                shutdown_restart_identity="Child is stateless; restart re-sends the unacknowledged request",
                performance_budget="Under 50 ms per batch of 1,000 events on the reference laptop")
    test("process route cannot be entirely n/a", lambda: expect(
        process_route(all_na), "protocol cannot be entirely n/a"))
    test("process route needs a protocol contract", lambda: expect(
        process_route(None), "needs a protocol contract"))
    test("process route with a real protocol passes", lambda: clean(process_route(real)))

    # --- interactions -------------------------------------------------------------------------
    for test_id, purpose in (("control-game", "negative-control"), ("accept-game", "product")):
        test("interaction cannot be verified by a " + purpose + " test", lambda t=test_id, p=purpose: expect(
            lambda r: r["interactions"][0].update(test=t), "has purpose " + p))

    def independent(game_touches, math_touches):
        def mutate(r):
            for ident, touches in (("component-game", game_touches), ("component-math", math_touches)):
                if touches is None:
                    cand(r, ident).pop("touches", None)
                else:
                    cand(r, ident)["touches"] = touches
            r["interactions"][0] = dict(components=["component-game", "component-math"], status="independent",
                                        rationale="Game owns duplicate policy; math owns error policy; no shared key")
        return mutate
    test("independent pair with disjoint touches needs no test", lambda: clean(
        independent(["policy:duplicate"], ["policy:error"])))
    test("independent pair cannot share a touched key", lambda: expect(
        independent(["state:entries"], ["State.Entries"]), "both touch"))
    test("independent disposition needs declared touches", lambda: expect(
        independent(None, None), "declared touches"))
    test("resolved interaction still needs a test", lambda: expect(
        lambda r: r["interactions"][0].pop("test", None), "needs an interaction or integration test"))

    # --- seam evidence ------------------------------------------------------------------------
    test("seam must link evidence", lambda: expect(
        lambda r: [c["seam"].pop("evidence", None) for c in r["candidates"]], "seam lacks evidence"))
    test("seam evidence must include the candidate's donor source", lambda: expect(
        lambda r: cand(r, "component-game")["seam"].update(evidence=["ev-math"]),
        "seam evidence lacks matching donor source"))

    # --- supporting (non-snapshot) evidence -----------------------------------------------------
    doc = dict(id="doc-existing", kind="documentation", url="https://example.invalid/docs/exact-totals",
               retrieved="2026-10-27", scope="Vendor documentation for an existing exact-total tool",
               limitations="Documentation claim only; behaviour not observed")

    def doc_alternative(r):
        r.setdefault("supporting_evidence", []).append(dict(doc))
        r["alternatives"][0]["evidence"] = ["doc-existing"]
    test("an alternative may cite documentation evidence", lambda: clean(doc_alternative))

    def doc_without_date(r):
        doc_alternative(r)
        r["supporting_evidence"][-1].pop("retrieved")
    test("documentation evidence needs a retrieval date", lambda: expect(doc_without_date, "retrieved"))
    test("supporting evidence cannot stand in for donor source provenance", lambda: expect(
        lambda r: (doc_alternative(r), cand(r, "component-game").update(evidence=["doc-existing"])),
        "unknown evidence doc-existing"))
    png = b"\x89PNG\r\n\x1a\n" + bytes(range(256))
    (root / "shot.png").write_bytes(png)

    def screenshot(digest):
        def mutate(r):
            r.setdefault("supporting_evidence", []).append(dict(
                id="shot-ui", kind="screenshot", snapshot="shot.png", sha256=digest, retrieved="2026-10-27",
                scope="Screenshot of an existing tool's replay screen", limitations="Image only; no source"))
            r["alternatives"][0]["evidence"].append("shot-ui")
        return mutate
    test("a binary screenshot can support an alternative", lambda: clean(screenshot(fm.digest(png))))
    test("screenshot bytes are hash-checked", lambda: expect(screenshot("0" * 64), "hash mismatch"))

    def graph_evidence(revision_override=None):
        def mutate(r):
            donor = next(d for d in r["donors"] if d["id"] == "game")
            revision = revision_override or donor["revision"]
            name = "graph-game-" + hashlib.sha256(revision.encode()).hexdigest()[:8] + ".json"
            target = root / name
            if not target.exists():
                fm.write_new(target, fm.encode(fm.inspect_python(root / "donors/game_save", revision)))
            r.setdefault("supporting_evidence", []).append(dict(
                id="graph-game", kind="static-graph", donor="game", revision=donor["revision"], snapshot=name,
                sha256=fm.digest(target.read_bytes()), scope="python-ast inventory of the game donor",
                limitations="Syntax-level imports and calls only"))
            cand(r, "component-game")["seam"]["evidence"] = ["ev-game", "graph-game"]
        return mutate
    test("a seam can cite a static graph of its donor", lambda: clean(graph_evidence()))
    test("a static graph must match its donor revision", lambda: expect(
        graph_evidence("other-revision@sha256:" + "c" * 64), "graph revision"))

    # --- receipt history -------------------------------------------------------------------------
    def history(outcomes, status, sequences=True):
        def mutate(r):
            target = r["tests"][0]
            target["status"] = status
            r["receipts"] = []
            for index, ok in enumerate(outcomes, start=1):
                raw = root / ("history-" + str(index) + ("-pass" if ok else "-fail") + ".txt")
                raw.write_text(("8 passed" if ok else "7 passed, 1 failed") + "\n", encoding="utf-8")
                receipt = dict(id="receipt-history-" + str(index), test=target["id"], command="python oracle.py",
                               environment="synthetic authored fixture", raw_output=raw.name,
                               raw_sha256=fm.digest(raw.read_bytes()), exit_code=0 if ok else 1, cases=8,
                               passed=8 if ok else 7, failed=0 if ok else 1, skipped=0, control_detected=False)
                if sequences:
                    receipt["sequence"] = index
                r["receipts"].append(receipt)
        return mutate
    test("a failed receipt can stay in history before a passing one", lambda: clean(history([False, True], "pass")))
    test("status pass must match the latest receipt", lambda: expect(history([True, False], "pass"), "cannot pass"))
    def fail_latest():
        # A failed required acceptance still blocks readiness, but the history itself is consistent.
        errors = errors_of(history([True, False], "fail"))
        assert errors == ["component-game acceptance: required test is fail"], errors
        return errors
    test("status fail matching the latest receipt is consistent", fail_latest)
    test("several receipts need sequence numbers", lambda: expect(
        history([False, True], "pass", sequences=False), "sequence"))

    # --- dual discovery copy -----------------------------------------------------------------------
    def copied_discovery(r):
        target = next(d for d in r["discoveries"] if d["id"] == "game-target-led")
        donor = next(d for d in r["discoveries"] if d["id"] == "game-donor-led")
        for key in ("problem", "mechanism", "invariant", "assumptions", "target_need", "falsifier", "rationale"):
            donor[key] = target[key]
    test("a donor-led record copied from target-led is rejected",
         lambda: expect(copied_discovery, "duplicates target-led"))

    # --- exploratory framing and schema versions --------------------------------------------------
    def exploratory(r):
        r["brief"]["question"] = "exploratory"
        r["brief"]["requirements"] = []
        r["candidates"], r["interactions"] = [], []
        r.pop("requirement_coverage", None)
        for item in r["discoveries"]:
            item["target_need"] = "hypothesis: " + item["mechanism"][:40]
        r["decision"]["choice"] = "minimal-fresh"
    test("an exploratory question may start without requirements", lambda: clean(exploratory))
    test("a product-led question still needs requirements", lambda: expect(
        lambda r: (exploratory(r), r["brief"].update(question="product-led")), "requirements must have"))
    test("an unsupported schema version is named", lambda: expect(
        lambda r: r.update(schema_version="9.9"), "unsupported schema_version"))
    test("unknown rights category blocks selection", lambda: expect(
        lambda r: cand(r, "component-game")["rights"].update(category="unknown"), "rights category unknown"))

    # --- report is the dossier --------------------------------------------------------------------
    def report_sections():
        record = copy.deepcopy(base)
        text = fm.report(record, fm.check(record, root))
        for heading in ("## Brief", "## Lesson ledger", "## Contracts", "## Requirement coverage", "## Ownership",
                        "## Interactions", "## Alternatives and decision", "## Tests and receipts", "## Review"):
            assert heading in text, heading
        assert "## Full portable record" not in text
        assert "donor\\-led" in text and "Seam" in text and "Rights" in text
        full = fm.report(record, fm.check(record, root), include_record=True)
        assert "## Full portable record" in full
        return "dossier sections rendered; raw record only on request"
    test("report renders the dossier and keeps raw JSON opt-in", report_sections)

    def implementation_not_run():
        record = copy.deepcopy(base)
        record["mode"] = "implementation"
        for item in record["candidates"]:
            item["implementation"] = "implemented"
        errors = fm.check(record, root)
        assert errors == [], errors
        text = fm.report(record, errors)
        assert "Implementation: unverified" in text, text[:600]
        assert "Decision state: design-ready" not in text
        path = root / "implementation-not-run.json"
        if not path.exists():
            fm.write_new(path, fm.encode(record))
        result = subprocess.run([sys.executable, "-B", str(PACKAGE / "scripts/frankenmine.py"), "check", str(path)],
                                capture_output=True, text=True, timeout=20)
        status = json.loads(result.stdout)["status"]
        assert result.returncode == 0 and status == "design-ready; implementation-unverified", (result, status)
        return status
    test("implementation run with tests not-run is not reported as done", implementation_not_run)

    def report_flag():
        record = copy.deepcopy(base)
        path = root / "report-flag.json"
        if not path.exists():
            fm.write_new(path, fm.encode(record))
        outputs = []
        for extra in ([], ["--include-record"]):
            out = root / ("report-flag" + ("-full" if extra else "") + ".md")
            result = subprocess.run([sys.executable, "-B", str(PACKAGE / "scripts/frankenmine.py"), "report",
                                     str(path), "--output", str(out)] + extra,
                                    capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, result
            outputs.append(out.read_text(encoding="utf-8"))
        assert "## Full portable record" not in outputs[0] and "## Full portable record" in outputs[1]
        return "--include-record adds the raw record"
    test("report CLI adds raw JSON only with --include-record", report_flag)

    # --- no writes into the skill folder ------------------------------------------------------------
    def refuse_package_writes():
        copy_root = scratch / "v0-2-package-copy" / "frankenmine"
        if not copy_root.exists():
            shutil.copytree(PACKAGE / "scripts", copy_root / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copytree(PACKAGE / "schemas", copy_root / "schemas")
        script = str(copy_root / "scripts/frankenmine.py")
        inside = copy_root / "runs" / "run.json"
        result = subprocess.run([sys.executable, "-B", script, "init", str(inside)], capture_output=True, text=True, timeout=20)
        assert result.returncode == 2 and not inside.exists(), (result.stdout, result.stderr)
        assert "inside the Frankenmine package root" in result.stderr, result.stderr
        relative = subprocess.run([sys.executable, "-B", script, "init", "runs/relative.json"], cwd=copy_root,
                                  capture_output=True, text=True, timeout=20)
        assert relative.returncode == 2 and not (copy_root / "runs/relative.json").exists(), relative.stderr
        outside = copy_root.parent / "outside-run" / "run.json"
        ok = subprocess.run([sys.executable, "-B", script, "init", str(outside)], capture_output=True, text=True, timeout=20)
        assert ok.returncode == 0 and outside.exists(), ok.stderr
        return "writes inside the package root refused (absolute and relative); outside allowed"
    test("helper refuses to write inside its own package root", refuse_package_writes)

    # --- inspect-python imported names ---------------------------------------------------------------
    def inventory_names():
        source = scratch / "v0-2-inventory"
        source.mkdir(exist_ok=True)
        (source / "mod.py").write_text("from . import helpers\nfrom .utils import parse, render as draw\nimport json as j\n",
                                       encoding="utf-8")
        graph = fm.inspect_python(source, "inventory-1")
        imports = {e["target"]: e for e in graph["edges"] if e["relation"] == "import"}
        assert imports["."].get("names") == ["helpers"], imports
        assert imports[".utils"].get("names") == ["parse", "render"], imports
        return "relative imports keep their imported names"
    test("inspect-python records imported names", inventory_names)

    # --- schema 1.0 compatibility -----------------------------------------------------------------------
    def legacy_records():
        schema = PACKAGE / "schemas/run-1.0.schema.json"
        assert hashlib.sha256(schema.read_bytes()).hexdigest() == SCHEMA_1_0_SHA256, "1.0 contract changed"
        schema = fm.load_json(schema)
        cases = [(LEGACY / "synthetic-run.json", LEGACY, LEGACY_SELECTED),
                 (LEGACY / "no-fusion-run.json", LEGACY, LEGACY_COMMON),
                 (PACKAGE / "evidence/synthetic-run/worked-run.json", PACKAGE / "evidence/synthetic-run", LEGACY_SELECTED)]
        for path, folder, expected in cases:
            record = fm.load_json(path)
            assert record["schema_version"] == "1.0", path
            assert fm.schema_errors(record, schema) == [], path
            errors = fm.check(record, folder)
            assert set(errors) == expected and len(errors) == len(expected), (path.name, sorted(set(errors) ^ expected))
            missing = copy.deepcopy(record)
            missing["candidates"][0].pop("protocol")
            assert any("missing protocol" in e for e in fm.check(missing, folder)), "1.0 still requires protocol"
            newer = dict(copy.deepcopy(record), requirement_coverage=[])
            assert any("unknown field requirement_coverage" in e for e in fm.check(newer, folder))
        return "1.0 records parse unchanged; stricter readiness gates name the 1.1 field to add"
    test("shipped schema 1.0 records still load with clear readiness messages", legacy_records)

    # --- shipped 1.1 examples -------------------------------------------------------------------------
    def shipped_examples():
        builder = getattr(fixture_builder, "make_no_fusion", None)
        assert builder is not None, "fixture_builder.make_no_fusion missing"
        review = "independent design review not accepted: disposition not-run; independence is self"
        for name, build in (("synthetic", make_run), ("no-fusion", builder)):
            path = PACKAGE / "examples" / name / "run.json"
            shipped = fm.load_json(path)
            assert shipped["schema_version"] == "1.1", name
            assert shipped == build(scratch / ("v0-2-built-" + name)), name + " example differs from its builder"
            errors = fm.check(shipped, path.parent)
            assert errors == [UNRESOLVED, review], (name, errors)
        no_fusion = fm.load_json(PACKAGE / "examples/no-fusion/run.json")
        assert no_fusion["decision"]["choice"] == "minimal-fresh"
        assert {c["route"] for c in no_fusion["candidates"] if c["phase"] == "selected"} == {"pattern-only"}
        return "both examples are 1.1, match their builders, and are blocked only by honest review/unresolved gates"
    test("shipped examples are schema 1.1 and blocked only by review", shipped_examples)

    # --- the flagship slice and oracle ---------------------------------------------------------------------
    product = load("v0_2_product", PACKAGE / "examples/synthetic/replay_total.py")
    oracle = load("v0_2_oracle", PACKAGE / "examples/synthetic/oracle.py")

    def caught(factory):
        try:
            oracle.acceptance(factory)
        except AssertionError as exc:
            return "control detected: " + str(exc)
        raise AssertionError("frozen oracle survived a broken contribution")

    def slice_rejects():
        ledger = product.ReplayTotal()
        for bad in ("-0", "", "  ", " 12", "12 ", "0x10", "٣", "1_000", "+1", "007"):
            try:
                ledger.add("x", bad)
            except ValueError:
                continue
            raise AssertionError("slice accepted " + repr(bad))
        assert ledger.entries == {}
        return "noncanonical, permissive and non-ASCII amounts rejected without state change"
    test("slice rejects -0 and permissive integer spellings", slice_rejects)

    class PermissiveParse(product.ReplayTotal):
        """Mutant mirroring BigInt('') == 0n plus Python int() leniency."""
        def add(self, identity, amount):
            if isinstance(amount, str):
                text = amount.strip()
                try:
                    amount = str(int(text, 0)) if text else "0"
                except ValueError:
                    pass
            return super().add(identity, amount)

    class LenientDigits(product.ReplayTotal):
        """Mutant trusting Python int(): accepts '٣', '1_000', ' 12' and '-0' but still rejects ''."""
        def add(self, identity, amount):
            if isinstance(amount, str):
                try:
                    amount = str(int(amount))
                except ValueError:
                    pass
            return super().add(identity, amount)

    class AcceptsNegativeZero(product.ReplayTotal):
        def add(self, identity, amount):
            return super().add(identity, "0" if amount == "-0" else amount)

    test("oracle detects BigInt-style empty-as-zero parsing", lambda: caught(PermissiveParse))
    test("oracle detects Python int() digit leniency", lambda: caught(LenientDigits))
    test("oracle detects silent -0 canonicalization", lambda: caught(AcceptsNegativeZero))

    # --- handoff stays usable with 1.1 records ---------------------------------------------------------------
    def handoff_cases():
        from synthesis_handoff import build_index
        record = copy.deepcopy(base)
        independent(["policy:duplicate"], ["policy:error"])(record)
        index = build_index(record, root / "run.json", fm.check(record, root))
        assert not any(item["kind"] == "interaction" for item in index["pending"]), index["pending"]
        record = copy.deepcopy(base)
        record["ownership"].append(dict(key="State.Entries", owner="OtherOwner", rationale="Competing loop"))
        index = build_index(record, root / "run.json", fm.check(record, root))
        assert index["next"]["kind"] == "ownership", index["next"]
        return "independent pairs need no interaction receipt; normalized ownership conflicts lead the queue"
    test("handoff supports independent pairs and normalized ownership keys", handoff_cases)


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
                   failed=sum(r["status"] == "fail" for r in results), helper_version="0.2" if NEW else "pre-0.2")
    (out / "results.json").write_text(json.dumps(dict(summary, tests=results), indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    print(json.dumps(summary, indent=2))
    raise SystemExit(1 if summary["failed"] else 0)
