"""Fix round after the 2026-10-28 blind comparison: proportionality as package mechanics.

The comparison found side files and process ceremony on small tasks, one write outside the named folder,
and an untested claim about code behaviour stated as fact. The package can check four things about that:
the reading budget, the wording of the default-on proportionality rules, that no instruction makes a
helper-checked record or a side file the default, and that the lite stamp cannot write its dossier away
from the folder whose files it hashes. Written red first against e8d5718. Only this package's helper runs,
on authored fixtures; every write stays under the results directory.

Round 3 (after the 2026-10-29 comparison): the snippet rule sent a check file to the host's scratchpad, outside
the named folder, and left unrequested check files inside it. The round-3 test pins the clarified wording:
snippets run inline, a file only inside the named folder, the host's scratchpad and temp folders count as
outside, and a denied run leaves the claim untested. Written red first against 65546d6.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "scripts" / "frankenmine.py"
FIXTURE = PACKAGE / "tests" / "fixtures" / "lite"
# Whitespace-separated words, counted as the lite budget test counts them.
BEFORE_SKILL_WORDS = 1698   # SKILL.md at e8d5718
BEFORE_READ_WORDS = 3140    # SKILL.md + lite template + evidence vocabulary at e8d5718 (its default path)
BEFORE_TEMPLATE_WORDS = 726
# Ratchet: growth needs a reason in the CHANGELOG. Round 3 raised both counts by the measured 53 words
# (write rule +9, snippet rule +44) for the snippet clarification; SKILL.md was 1617 and the set 3059 at 65546d6.
SKILL_WORDS = 1670
READ_WORDS = 3112           # ratchet for the same three files
READ_SET = ("SKILL.md", "examples/lite-dossier.md", "references/evidence-vocabulary.md")
HELPERS = ("frankenmine.py", "scaffold", "stamp", "check-lite", "init ", "report ", "review-packet")


def words(rel):
    return len((PACKAGE / rel).read_text(encoding="utf-8").split())


def flat(text):
    return " ".join(text.split()).casefold()


def section(text, heading_pattern):
    """Body of the first '## ' section whose heading matches, up to the next '## '."""
    match = re.search(r"^## (" + heading_pattern + r")[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S | re.I)
    return (match.group(1), match.group(2), match.start()) if match else (None, "", -1)


def run_tests(test, scratch):
    skill = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")

    def budget():
        now = words("SKILL.md")
        read = sum(words(rel) for rel in READ_SET)
        template = words("examples/lite-dossier.md")
        assert now < BEFORE_SKILL_WORDS, ("SKILL.md must shrink", now)
        assert now <= SKILL_WORDS, ("SKILL.md grew past this round's ratchet", now)
        assert read < BEFORE_READ_WORDS and read <= READ_WORDS, ("SKILL.md + template + vocabulary", read)
        assert template <= BEFORE_TEMPLATE_WORDS, ("lite template grew", template)
        return dict(skill=now, read_set=read, template=template)
    test("fix round: SKILL.md and its default reading set shrink, with a ratchet", budget)

    def rules():
        heading, body, start = section(skill, r"Keep it proportionate")
        assert heading, "missing the proportionality section"
        first_step = re.search(r"^## 1\.", skill, re.M)
        assert first_step and start < first_step.start(), "proportionality must come before the steps"
        text = flat(body)
        required = {
            "default-on and overriding": "override",
            "one reply gets the reply": "answer in one reply gets that reply",
            "only requested files": "only the files the user asked for",
            "side files need persistence or a request": "only when the task needs persistence or the user asks",
            "steps are checks, not writing": "the steps below say what to check, not what to write",
            "named folder only": "write only inside the output folder the user named",
            "no folder, no writes": "if none is named, write nothing",
            "check behaviour claims": "before you state how code behaves",
            "or mark them untested": "mark that claim untested",
            "checks never run donor code": "never donor code, even re-typed",
        }
        missing = [name for name, phrase in required.items() if phrase not in text]
        assert not missing, missing
        return sorted(required)
    test("fix round: the proportionality rules are stated before the steps", rules)

    def defaults():
        heading, body, _ = section(skill, r"Choose the (?:record|tier)")
        assert heading, "missing the record choice"
        bullets = re.findall(r"^- \*\*([^*]+)\*\* ?\(([^)]*)\)(.*)$", body, re.M)
        assert bullets, body
        name, condition, rest = bullets[0]
        assert "default" in condition.casefold(), ("the first record is the default", bullets[0])
        assert not any(h in (condition + rest) for h in HELPERS), ("the default record runs no helper", bullets[0])
        assert not re.search(r"\]\(", rest), ("the default record links no template", bullets[0])
        for other, condition, _ in bullets[1:]:
            assert "default" not in condition.casefold(), (other, "is not the default")
        assert "hash snapshots" not in flat(skill), "SKILL.md must not make snapshot copies a default"
        # Every path a SKILL.md command writes sits in the named output folder.
        outputs = re.findall(r'(?:--output|\binit)\s+"?([^"\s`]+)', skill)
        assert outputs and all(o.startswith("<output-folder>/") for o in outputs), outputs
        return dict(default=name, others=[b[0] for b in bullets[1:]], outputs=outputs)
    test("fix round: the default record is the reply, with no helper or side file", defaults)

    def stamp_stays_in_folder():
        def cli(*parts):
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, parts)], capture_output=True,
                                    text=True, timeout=30)
            try:
                return result.returncode, json.loads(result.stdout or result.stderr)
            except ValueError:
                return result.returncode, {"raw": result.stdout + result.stderr}
        folder = scratch / "fix-round" / "stamp-folder"
        shutil.copytree(FIXTURE, folder)
        source = folder / "DOSSIER.md"
        body = source.read_text(encoding="utf-8").replace(
            "285b1d80ec33c157c72899744e0a7c35cd9680284cda26df4b035df848c0a06e", "&lt;stamp&gt;", 1)
        source.write_text(body, encoding="utf-8")
        away = scratch / "fix-round" / "elsewhere" / "DOSSIER.md"
        code, data = cli("stamp", source, "--output", away)
        assert code == 2 and not away.exists(), ("stamp wrote the dossier outside its folder", code, data)
        assert "folder" in json.dumps(data), data
        beside = folder / "STAMPED.md"
        code2, data2 = cli("stamp", source, "--output", beside)
        assert code2 == 0 and beside.is_file(), data2
        code3, check = cli("check-lite", beside)
        assert code3 == 0 and check["status"] == "lite-complete", check
        return "refused away from its folder; stamped beside its source and checked"
    test("fix round: stamp keeps a lite dossier in the folder whose files it hashes", stamp_stays_in_folder)

    def snippet_rule():
        heading, body, _ = section(skill, r"Keep it proportionate")
        assert heading, "missing the proportionality section"
        bullets = [flat(b) for b in re.findall(r"^- (.+)$", body, re.M)]

        def bullet(phrase):
            found = [b for b in bullets if phrase in b]
            assert len(found) == 1, ("expected one bullet", phrase, found)
            return found[0]
        write = bullet("write only inside the output folder the user named")
        snippet = bullet("before you state how code behaves")
        required = [
            ("scratchpad and temp count as outside", write,
             "the host's scratchpad and temp folders count as outside"),
            ("inline preferred", snippet,
             "run snippets inline (`node -e`, `python -c`, literal paths), not from a file unless truly needed"),
            ("a file only inside the named folder", snippet, "and then only inside the named folder"),
            ("no folder named: inline only", snippet, "with none named, inline only"),
            ("untested on denial", snippet, "or if running is denied, mark that claim untested"),
            ("no workaround elsewhere", snippet, "never write or run elsewhere to work around a denial"),
            ("never donor code, even re-typed", snippet, "never donor code, even re-typed"),
        ]
        missing = [name for name, where, phrase in required if phrase not in where]
        assert not missing, missing
        # Scratch and temp locations are named only to say they are outside; nothing sends a write there.
        mentions = [flat(re.sub(r"^- ", "", line)) for line in skill.splitlines()
                    if re.search(r"scratch|\btemp\b|\btmp\b", line, re.I)]
        assert mentions == [write], ("scratch/temp named outside the write rule", mentions)
        # A file a check needed is reported: the closing line asks for written paths and checks run.
        closing = flat(skill.strip().splitlines()[-1])
        assert "the paths of any files written" in closing and "any checks run with their results" in closing, closing
        return [name for name, _, _ in required] + ["scratch/temp only as outside", "closing reports files and checks"]
    test("round 3: snippet checks run inline or inside the named folder", snippet_rule)


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
