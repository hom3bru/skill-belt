"""Speed round (2026-11-03): less hand-written record for the same checks.

A large full-tier run (Palette, 2026-11-03: 20 selected parts) wrote 194 interaction records, 169 of them
"independent" pairs whose declared touches were disjoint, a fact `check` already computes. Its 19
pattern-only parts each filled eleven seam dimensions that describe a code boundary no pattern crosses.

1. Derived pairs: a selected pair whose declared, non-empty touches share no key (after key normalisation)
   needs no interaction record. A pair that shares a key, or whose touches are missing or empty, still needs one.
   `report` lists the derived pairs so a reader still sees every pair's disposition.
2. Short seam: a selected pattern-only part needs seam.evidence plus seam.adaptation (the assumptions the
   pattern relied on in the donor, and why they hold in the product); the full eleven-dimension seam stays
   valid. Every other route keeps the full seam. Schema 1.0 stays frozen. `scaffold` writes the short stub
   for pattern-only.

Written red first against cae8888. Only this package's helpers run, on authored fixtures; every write stays
under the results directory.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import traceback

import fixture_builder
from fixture_builder import make_run, make_no_fusion, fm, PACKAGE

SCRIPT = PACKAGE / "scripts" / "frankenmine.py"
LEGACY = PACKAGE / "tests" / "fixtures" / "schema-1.0" / "no-fusion-run.json"
PAIR = "component-game / component-math"
ADAPTATION = ("The donor assumed a caller-owned in-memory set; the product keeps one ledger that owns identities, "
              "so the membership check runs inside the owner before any mutation")


def run_tests(test, scratch):
    root = scratch / "speed-round"
    fusion = make_run(root)
    fixture_builder.accept_review(fusion, root, reviewer="Synthetic positive-control reviewer")
    fusion["unresolved"] = []
    nf_root = scratch / "speed-round-no-fusion"
    no_fusion = make_no_fusion(nf_root)
    fixture_builder.accept_review(no_fusion, nf_root, reviewer="Synthetic positive-control reviewer")
    no_fusion["unresolved"] = []

    def cand(record, ident):
        return next(c for c in record["candidates"] if c["id"] == ident)

    def errors_of(base, where, mutate):
        record = copy.deepcopy(base)
        mutate(record)
        return fm.check(record, where)

    def clean(base, where, mutate):
        errors = errors_of(base, where, mutate)
        assert errors == [], errors
        return "no readiness errors"

    def expect(base, where, mutate, text):
        errors = errors_of(base, where, mutate)
        assert any(text in e for e in errors), (text, errors)
        return [e for e in errors if text in e]

    # --- 1. derived independent pairs ------------------------------------------------------------
    def disjoint(r):
        cand(r, "component-math")["touches"] = ["policy:error"]  # game keeps state:entries, policy:duplicate
        r["interactions"] = []

    test("speed round: a pair with disjoint declared touches needs no interaction record",
         lambda: clean(fusion, root, disjoint))

    test("speed round: a pair that shares a key still needs an interaction record", lambda: expect(
        fusion, root, lambda r: r.update(interactions=[]), "missing interaction review: " + PAIR))

    def normalised_overlap(r):
        cand(r, "component-math")["touches"] = ["State : Entries", "policy:error"]
        r["interactions"] = []
    test("speed round: keys that differ only in case or separators still count as shared",
         lambda: expect(fusion, root, normalised_overlap, "missing interaction review: " + PAIR))

    def empty_touches(r):
        cand(r, "component-math")["touches"] = []
        r["interactions"] = []

    def undeclared_touches(r):
        cand(r, "component-math").pop("touches")
        r["interactions"] = []

    def unproven_disjoint():
        found = expect(fusion, root, empty_touches, "missing interaction review: " + PAIR)
        found += expect(fusion, root, undeclared_touches, "missing interaction review: " + PAIR)
        return found
    test("speed round: empty or undeclared touches never derive independence", unproven_disjoint)

    def report_lists_derived():
        record = copy.deepcopy(fusion)
        disjoint(record)
        text = fm.report(record, fm.check(record, root))
        # report escapes Markdown punctuation (component\-game); read the line without the escapes.
        line = next((x for x in text.replace("\\", "").splitlines() if x.startswith("- " + PAIR + ":")), None)
        assert line and "independent" in line and "derived" in line and "disjoint" in line, (line, text[-1500:])
        return line
    test("speed round: report shows each derived pair as independent", report_lists_derived)

    # Packet claims must reach a fresh reviewer without disclosing the decision rationale.
    def packet_text(record, where, name):
        import authoring
        record["decision"]["rationale"] = "PRIVATE_PACKET_DECISION_SENTINEL"
        source = where / (name + ".json")
        fm.write_new(source, fm.encode(record))
        out = scratch / ("packet-" + name)
        authoring.review_packet(source, out)
        text = (out / "PACKET.md").read_text(encoding="utf-8")
        assert "PRIVATE_PACKET_DECISION_SENTINEL" not in text, "decision rationale leaked"
        return text

    def packet_short_seam():
        import authoring
        record = copy.deepcopy(no_fusion)
        seam = dict(adaptation="PACKET_ADAPTATION_SENTINEL <claim>\n& assumption", evidence=["ev-game"])
        cand(record, "component-game")["seam"] = seam
        text = packet_text(record, nf_root, "short-seam")
        part = text.split("- component-game:", 1)[1].split("- component-math:", 1)[0]
        seam_block = part.split("  - Seam claims (author; check against evidence):", 1)[-1]
        for key, value in seam.items():
            expected = authoring.inert(", ".join(value) if isinstance(value, list) else value)
            assert "    - " + key + ": " + expected in seam_block.splitlines(), "missing short seam field: " + key
        assert "<claim>" not in text, "seam claim was not inert"
        return "short seam fields and evidence rendered inertly; rationale withheld"
    test("speed round: packet includes short seam claims", packet_short_seam)

    def packet_full_seam():
        import authoring
        record = copy.deepcopy(fusion)
        seam = cand(record, "component-math")["seam"]
        for key in seam:
            if key != "evidence":
                seam[key] = "PACKET_FULL_SEAM_" + key + " <claim>\n& assumption"
        text = packet_text(record, root, "full-seam")
        part = text.split("- component-math:", 1)[1].split("## Ownership and interactions", 1)[0]
        seam_block = part.split("  - Seam claims (author; check against evidence):", 1)[-1]
        for key, value in seam.items():
            expected = authoring.inert(", ".join(value) if isinstance(value, list) else value)
            assert "    - " + key + ": " + expected in seam_block.splitlines(), "missing full seam field: " + key
        assert "<claim>" not in text, "seam claim was not inert"
        return "every full seam field and evidence rendered; rationale withheld"
    test("speed round: packet includes full seam claims", packet_full_seam)

    def packet_pairs(explicit):
        record = copy.deepcopy(fusion)
        disjoint(record)
        third = copy.deepcopy(cand(record, "component-game"))
        third.update(id="component-third", owner="ThirdOwner", touches=["state:third"])
        record["candidates"].append(third)
        record["ownership"].append(dict(key="state:third", owner="ThirdOwner",
                                        rationale="Separate state owned only by the third part"))
        record["interactions"] = [dict(components=["component-game", "component-math"], status="independent",
                                       rationale="Declared touches are disjoint")]
        expected = fm.derived_independent_pairs(record)
        assert len(expected) == 2, "fixture must exercise multiple derived pairs alongside an explicit pair"
        if explicit:
            record["interactions"] += [dict(components=list(pair), status="independent",
                rationale="Declared touches are disjoint") for pair in expected]
        errors = fm.check(record, root)
        assert errors == [], errors
        text = packet_text(record, root, "explicit-pairs" if explicit else "derived-pairs")
        section = text.split("## Ownership and interactions", 1)[1].split("## Alternatives", 1)[0]
        derived_lines = [line for line in section.splitlines() if "derived" in line]
        assert len(derived_lines) == (0 if explicit else len(expected)), "wrong derived pair count: " + repr(derived_lines)
        for a, b in expected:
            lines = [line for line in section.splitlines() if line.startswith("- " + a + " / " + b + ":")]
            assert len(lines) == 1, "pair missing or duplicated: " + repr((a, b, lines))
            assert ("derived" in lines[0]) == (not explicit), lines
        for interaction in record["interactions"]:
            a, b = interaction["components"]
            lines = [line for line in section.splitlines() if line.startswith("- " + a + " / " + b + ":")]
            assert len(lines) == 1, "explicit pair missing or duplicated: " + repr((a, b, lines))
            assert "derived" not in lines[0], lines
        return dict(explicit=explicit, pairs=len(expected), derived=len(derived_lines))
    test("speed round: packet lists every derived pair once", lambda: packet_pairs(False))
    test("speed round: packet never derives an explicitly recorded pair", lambda: packet_pairs(True))

    # --- 2. short seam for pattern-only parts ----------------------------------------------------
    def short_seams(adaptation=ADAPTATION, ids=("component-game", "component-math")):
        def mutate(r):
            for ident in ids:
                c = cand(r, ident)
                c["seam"] = dict(evidence=list(c["seam"]["evidence"]))
                if adaptation is not None:
                    c["seam"]["adaptation"] = adaptation
        return mutate

    test("speed round: the full seam stays valid for pattern-only parts",
         lambda: clean(no_fusion, nf_root, lambda r: None))
    test("speed round: a pattern-only part passes with seam evidence and adaptation only",
         lambda: clean(no_fusion, nf_root, short_seams()))
    test("speed round: a short pattern-only seam needs adaptation",
         lambda: expect(no_fusion, nf_root, short_seams(adaptation=None), "component-game: pattern-only seam needs adaptation"))
    def partial_seam(r):
        c = cand(r, "component-game")
        c["seam"] = dict(tests=c["seam"]["tests"], evidence=list(c["seam"]["evidence"]))
    test("speed round: a partial pattern-only seam without adaptation still needs adaptation",
         lambda: expect(no_fusion, nf_root, partial_seam, "component-game: pattern-only seam needs adaptation"))
    test("speed round: a placeholder adaptation blocks readiness",
         lambda: expect(no_fusion, nf_root, short_seams(adaptation="TBD"), "unexplained seam field adaptation"))

    def code_route_short(r):
        cand(r, "component-math")["seam"] = dict(adaptation=ADAPTATION, evidence=["ev-math"])
    test("speed round: a reimplementation still needs every seam dimension",
         lambda: expect(fusion, root, code_route_short, "exports_consumers"))

    def unselected_code_route_short(r):
        code_route_short(r)
        cand(r, "component-math")["phase"] = "rejected"
    test("speed round: a non-pattern-only candidate keeps the full seam even when unselected",
         lambda: expect(fusion, root, unselected_code_route_short, "exports_consumers"))

    def legacy_frozen():
        record = fm.load_json(LEGACY)
        assert record["schema_version"] == "1.0"
        target = record["candidates"][0]  # the 1.0 no-fusion record defers its parts; make one pattern-only
        target.update(route="pattern-only", phase="selected", seam=dict(adaptation=ADAPTATION))
        errors = fm.record_schema_errors(record)
        assert any("missing exports_consumers" in e for e in errors), errors
        return [e for e in errors if "seam" in e]
    test("speed round: schema 1.0 keeps its frozen full seam", legacy_frozen)

    def scaffold_short_stub():
        folder = scratch / "speed-round-scaffold"
        folder.mkdir(parents=True, exist_ok=True)
        record_root = scratch / "speed-round"
        source = record_root / "speed-scaffold-in.json"
        fm.write_new(source, fm.encode(fusion))

        def scaffold(route, ident):
            out = folder / (ident + ".json")
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "scaffold", str(source), "--donor", "game",
                                     "--unit", "donors/game_save/checkpoint.py", "--route", route, "--id", ident,
                                     "--output", str(out)], capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, (result.stdout, result.stderr)
            return fm.load_json(out)
        lesson = scaffold("pattern-only", "component-lesson")
        port = scaffold("narrow-port", "component-port")
        short = cand(lesson, "component-lesson")["seam"]
        full = cand(port, "component-port")["seam"]
        assert set(short) == {"adaptation", "evidence"}, sorted(short)
        assert short["adaptation"].startswith(fm.SCAFFOLD_MARK), short
        assert set(full) == set(fm.SEAM_DIMENSIONS) | {"evidence"}, sorted(full)
        selected = copy.deepcopy(lesson)
        cand(selected, "component-lesson")["phase"] = "selected"
        assert fm.check(selected, record_root), "a scaffolded stub must never make a record pass"
        return dict(pattern_only=sorted(short), narrow_port=len(full))
    test("speed round: scaffold writes the short seam stub for pattern-only", scaffold_short_stub)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
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
    (out / "results.json").write_text(json.dumps(dict(summary, tests=results), indent=2, default=str) + "\n",
                                      encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for r in results:
        print(r["status"].upper(), "-", r["name"])
    raise SystemExit(1 if summary["failed"] else 0)
