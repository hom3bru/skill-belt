"""Slim lite tier: check-lite, scaffold-lite, stamp on a lite dossier, escalation to the full tier.

Each case was written before the behaviour it tests and run red against the earlier helper.
Only authored fixtures and this package's helper run; every write stays under the results directory.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

PACKAGE = Path(__file__).resolve().parents[1]
FIXTURE = PACKAGE / "tests" / "fixtures" / "lite"
SCRIPT = PACKAGE / "scripts" / "frankenmine.py"
OLD_LITE_WORDS = 2437  # SKILL.md plus the lite template before round 2 (CHANGELOG size table)


def run_tests(test, scratch):
    base = scratch / "lite"

    def cli(*parts):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, parts)], capture_output=True, text=True,
                                timeout=30)
        try:
            return result.returncode, json.loads(result.stdout or result.stderr)
        except ValueError:
            return result.returncode, {"raw": result.stdout + result.stderr}

    def fresh(name):
        target = base / name
        assert not target.exists(), target
        shutil.copytree(FIXTURE, target)
        return target

    def edited(name, *pairs):
        folder = fresh(name)
        path = folder / "DOSSIER.md"
        body = path.read_text(encoding="utf-8")
        for old, new in pairs:
            assert old in body, old
            body = body.replace(old, new, 1)
        path.write_text(body, encoding="utf-8")
        return path

    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def complete():
        code, data = cli("check-lite", fresh("ok") / "DOSSIER.md")
        assert code == 0 and data.get("status") == "lite-complete", data
        assert data.get("not_checked"), "lite-complete must name the full-tier checks it skipped"
        return data["not_checked"]
    test("check-lite accepts a complete slim dossier and names what it skipped", complete)

    def seam_note_with_comma():
        path = edited("seam-comma", ("errors: never raises |", "errors: never raises, never retries |"))
        code, data = cli("check-lite", path)
        assert code == 0 and data["status"] == "lite-complete", data
        return "a comma inside a seam note stays inside that note"
    test("check-lite splits material seams on semicolons only", seam_note_with_comma)

    def blank():
        folder = base / "blank"
        folder.mkdir(parents=True)
        (folder / "DOSSIER.md").write_bytes((PACKAGE / "examples/lite-dossier.md").read_bytes())
        code, data = cli("check-lite", folder / "DOSSIER.md")
        assert code == 2 and data.get("status") == "lite-incomplete" and len(data.get("problems", [])) > 10, data
        return str(len(data["problems"])) + " problems"
    test("check-lite rejects the blank template", blank)

    review_row = "| Fresh reviewer subagent | fresh-context-same-model |"
    p1 = "| P1 | D1 | seen.py remember | pattern-only | idea-only | state:entries |"
    p2 = "| P2 | D2 | canon.go Canon | reimplementation from idea | idea-only | policy:canonical-url |"
    d2 = ("| D2 | https://example.invalid/canon | 2222222222222222222222222222222222222222 | Go | task-authored | "
          "reviewed: canon.go read, not run; port handling absent |")
    flagged = [
        ("an unticked readiness item", [("- [x] No design blocker", "- [ ] No design blocker")], "unticked"),
        ("a self review", [(review_row, "| Fresh reviewer subagent | self |")], "self"),
        ("a review row written off as none", [(review_row, "| none: no reviewer was run | n/a: not run |")],
         "needs real rows"),
        ("a review report that names another reviewer",
         [("| Fresh reviewer subagent |", "| Someone else |")], "review report"),
        ("a missing donor-led lesson", [("| L4 | D2 | donor-led |", "| L4 | D2 | target-led |")], "donor-led"),
        ("an empty cell", [("| E1 | D1 | seen.py:1-5 |", "| E1 | D1 |  |")], "empty"),
        ("a snapshot hash mismatch",
         [("285b1d80ec33c157c72899744e0a7c35cd9680284cda26df4b035df848c0a06e", "0" * 64)], "hash"),
        ("a reimplementation without its basis",
         [("| reimplementation from idea |", "| reimplementation |")], "from code"),
        ("a requirement met by an unknown part", [("| P2 |\n\n## Donors", "| P9 |\n\n## Donors")], "R2"),
        ("a deferred decision", [("- **Decision:** fusion", "- **Decision:** defer")], "defer"),
        ("fusion without a reused unit", [(p2, p2.replace("reimplementation from idea", "pattern-only"))], "fusion"),
        ("a missing option", [("| Minimal fresh | One fresh module | E1, E2 | Simplicity | No import count |\n", "")],
         "Minimal fresh"),
        ("a language that disagrees with its snapshot", [(d2, d2.replace("| Go |", "| Python |"))], "extension"),
        ("a code route under idea-only rights", [(p1, p1.replace("pattern-only", "narrow-port"))], "reuses donor code"),
        ("source-available code without permission",
         [(p1, p1.replace("pattern-only | idea-only", "narrow-port | licensed-reuse")),
          ("| Python | task-authored | reviewed: seen.py", "| Python | source-available | reviewed: seen.py")],
         "permission"),
        ("a code route without its dependency table",
         [(p1, p1.replace("pattern-only | idea-only", "narrow-port | licensed-reuse"))], "dependency"),
        ("an oracle that is a donor snapshot",
         [("| T1 | P1 | product | Spec item 1 | oracles/spec.md | b090013107979171e655eb8673ee6341a4b16fce38335b0a45f8c2f85f68ae2b |",
           "| T1 | P1 | product | Spec item 1 | snapshots/d1/seen.py | "
           "285b1d80ec33c157c72899744e0a7c35cd9680284cda26df4b035df848c0a06e |")], "donor"),
        ("an independent pair that shares a key", [(p2, p2.replace("policy:canonical-url", "state:entries"))],
         "both touch"),
        ("implementation claimed without receipts", [("- **Implementation:** not-started", "- **Implementation:** tested")],
         "receipt"),
    ]
    for name, pairs, text in flagged:
        def bad(name=name, pairs=pairs, text=text):
            path = edited("bad-" + re.sub(r"\W+", "-", name), *pairs)
            code, data = cli("check-lite", path)
            assert code == 2 and data.get("status") == "lite-incomplete", data
            assert any(text in p for p in data.get("problems", [])), (text, data)
            return data["problems"]
        test("check-lite flags " + name, bad)

    escalations = [
        ("more than three donors", [(d2 + "\n", d2 + "\n" + d2.replace("D2", "D3") + "\n" + d2.replace("D2", "D4") + "\n")],
         "more than three donors"),
        ("a process route", [(p2, p2.replace("reimplementation from idea", "process"))], "process"),
        ("cross-language code reuse",
         [(p2, p2.replace("reimplementation from idea | idea-only", "reimplementation from code | licensed-reuse"))],
         "cross-language"),
        ("three parts sharing one key",
         [(p2, p2.replace("policy:canonical-url", "state:entries")),
          ("| P2 | D2 | canon.go Canon", "| P3 | D1 | seen.py remember | pattern-only | idea-only | state:entries | Store | "
           "state: shared | E1 |\n| P2 | D2 | canon.go Canon")], "three or more parts"),
    ]
    for name, pairs, text in escalations:
        def escalate(name=name, pairs=pairs, text=text):
            path = edited("escalate-" + re.sub(r"\W+", "-", name), *pairs)
            code, data = cli("check-lite", path)
            assert code == 2 and data.get("status") == "escalate-to-full", data
            assert any(text in reason for reason in data.get("escalate", [])), (text, data)
            return data["escalate"]
        test("check-lite escalates " + name + " to the full tier", escalate)

    def receipts(product_bytes_changed=False):
        def run():
            path = edited("receipts" + ("-stale" if product_bytes_changed else ""),
                          ("- **Implementation:** not-started", "- **Implementation:** tested"))
            folder = path.parent
            (folder / "product").mkdir()
            (folder / "product" / "linkkeep.py").write_text("# authored product stand-in\n", encoding="utf-8")
            product = sha(folder / "product" / "linkkeep.py")
            rows = ["", "| Test | Result | Raw output | SHA-256 | Product file | Product SHA-256 |",
                    "| --- | --- | --- | --- | --- | --- |"]
            for test_id in ("T1", "T2", "T3", "T4"):
                raw = folder / "raw" / (test_id + ".txt")
                raw.parent.mkdir(exist_ok=True)
                raw.write_text(test_id + ": 4 passed\n", encoding="utf-8")
                rows.append("| " + test_id + " | pass | raw/" + test_id + ".txt | " + sha(raw) + " | product/linkkeep.py | " +
                            product + " |")
            body = path.read_text(encoding="utf-8").replace("## Readiness", "\n".join(rows) + "\n\n## Readiness")
            path.write_text(body, encoding="utf-8")
            if product_bytes_changed:
                (folder / "product" / "linkkeep.py").write_text("# changed after the receipts\n", encoding="utf-8")
            code, data = cli("check-lite", path)
            if product_bytes_changed:
                assert code == 2 and any("hash" in p for p in data["problems"]), data
            else:
                assert code == 0 and data["status"] == "lite-complete", data
            return data["status"]
        return run
    test("implemented lite work with artifact-bound receipts passes", receipts())
    test("a lite receipt whose product file changed is rejected", receipts(product_bytes_changed=True))

    def scaffold():
        out = base / "scaffolded" / "DOSSIER.md"
        code, data = cli("scaffold-lite", "--output", out, "--donors", "2", "--parts", "2", "--requirements", "3")
        assert code == 0, data
        body = out.read_text(encoding="utf-8")
        for row in ("| L1 | D1 | target-led |", "| L2 | D1 | donor-led |", "| L4 | D2 | donor-led |",
                    "| T2 | P1 | negative-control |", "| T3 | P2 | product |", "| P1 / P2 |", "| R3 |", "| E2 | D2 |"):
            assert row in body, row
        code2, check = cli("check-lite", out)
        assert code2 == 2 and check["status"] != "lite-complete", "scaffolding never makes a dossier pass"
        again, _ = cli("scaffold-lite", "--output", out, "--donors", "2", "--parts", "2", "--requirements", "3")
        inside, _ = cli("scaffold-lite", "--output", PACKAGE / "lite-should-not-exist.md", "--donors", "1",
                        "--parts", "1", "--requirements", "1")
        assert again == 2 and inside == 2 and not (PACKAGE / "lite-should-not-exist.md").exists()
        return "numbered rows prefilled; the dossier stays incomplete; no replacement, no package writes"
    test("scaffold-lite writes numbered rows that still block", scaffold)

    def stamp():
        path = edited("stamp-in", ("285b1d80ec33c157c72899744e0a7c35cd9680284cda26df4b035df848c0a06e", "&lt;stamp&gt;"),
                      ("3f6c00c54a961dfe11aa9ab7b204db1734d12d5800150059cb8777950de7a9b7 |", " |"))
        before = path.read_bytes()
        out = path.parent / "STAMPED.md"
        code, data = cli("stamp", path, "--output", out)
        assert code == 0 and path.read_bytes() == before, data
        code2, check = cli("check-lite", out)
        assert code2 == 0 and check["status"] == "lite-complete", check
        wrong = edited("stamp-wrong", ("d11debf10e133c17b84c7917cd45931415de53154e15117b903ef0c3215ea6df", "0" * 64))
        out2 = wrong.parent / "STAMPED.md"
        code3, data3 = cli("stamp", wrong, "--output", out2)
        assert code3 == 2 and "0" * 64 in out2.read_text(encoding="utf-8"), data3
        return "missing hashes filled into a new dossier; a recorded wrong hash is reported, never rewritten"
    test("stamp fills a lite dossier's missing hashes", stamp)

    def budget():
        skill = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
        template = (PACKAGE / "examples/lite-dossier.md").read_text(encoding="utf-8")
        words = len(skill.split()) + len(template.split())
        assert words <= OLD_LITE_WORDS, words
        boxes = len(re.findall(r"^- \[ \]", template, re.M))
        assert 6 <= boxes <= 9, boxes
        assert "Other seam dimensions" in template and "| numeric |" not in template
        for name in ("scaffold-lite", "check-lite", "stamp"):
            assert name in skill, name
        return str(words) + " words for SKILL.md plus the template; " + str(boxes) + " checklist items"
    test("lite reading cost stays within the old budget", budget)


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
    raise SystemExit(1 if summary["failed"] else 0)
