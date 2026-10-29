"""Lite tier helpers: check-lite, scaffold-lite and stamp for a lite dossier (examples/lite-dossier.md).

check-lite reads the dossier's tables, bullets and readiness checklist, recomputes file hashes, and checks
what matters most for a small design: pins and snapshot hashes, the three options and the decision,
requirement coverage, rights against each reused unit's route, oracle independence, receipts bound to product
files when anything was implemented, and the saved review report. It says when the job has outgrown lite and
names the full-tier checks lite does not perform. It does not understand prose and is not schema validation.
"""
import itertools
import os
from pathlib import Path
import re

import frankenmine as fm

PROMPT = re.compile(r"&lt;[^&\n]*?&gt;")
CHECKBOX = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(.*)$")
BULLET = re.compile(r"^\s*-\s+\*\*([^*:]+):\*\*\s*(.*)$")
LEVELS = ("fresh-context-same-model", "different-model", "human")
CATEGORIES = ("open-source", "source-available", "proprietary", "public-domain", "task-authored")
BASES = ("licensed-reuse", "permission", "idea-only")
ROUTES = ("dependency", "narrow-port", "ffi", "wasm", "process", "rpc", "reimplementation", "pattern-only")
LITE_CODE_ROUTES = ("dependency", "narrow-port", "ffi", "wasm")
WORD_COLUMNS = ("Direction", "Basis", "Purpose", "Disposition", "Independence", "Result", "Licence category")
HASHED = (("Snapshot file", "SHA-256"), ("Oracle file", "SHA-256"), ("Report file", "SHA-256"),
          ("Raw output", "SHA-256"), ("Product file", "Product SHA-256"))
NONE_ALLOWED = ("dependencies", "pairs")
SEAM_NAMES = {"exports and consumers", "exports", "consumers", "closure", "initialization", "state and transactions",
              "state", "transactions", "resources and lifetime", "resources", "lifetime", "concurrency and cancellation",
              "concurrency", "cancellation", "errors and retries", "errors", "retries", "serialization",
              "permissions and effects", "permissions", "effects", "tests", "licensing"} | {
              d.replace("_", " ") for d in fm.SEAM_DIMENSIONS}
NOT_CHECKED = [
    "semantic deltas (lite stops at cross-language code reuse)",
    "process and rpc protocol contracts (lite escalates them)",
    "seam dimensions beyond those declared material",
    "one owner per state key across parts",
    "group interactions (lite escalates keys shared by three or more parts)",
    "donor-led lessons that differ only in wording from target-led ones",
    "pin authenticity (pins are syntax-checked only)"]


def cells(line):
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") else body
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", body)]


def tables(lines):
    """Pipe tables as (header, [(line index, {column: cell})])."""
    found, index = [], 0
    while index < len(lines):
        if lines[index].lstrip().startswith("|") and index + 1 < len(lines) and re.match(
                r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
            header = cells(lines[index])
            rows, index = [], index + 2
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                values = cells(lines[index])
                rows.append((index, dict(zip(header, values + [""] * (len(header) - len(values))))))
                index += 1
            found.append((header, rows))
        else:
            index += 1
    return found


def table_name(header):
    first = header[0].casefold()
    if first == "test":
        return "receipts" if len(header) > 1 and header[1].casefold() == "result" else "tests"
    return {"req": "requirements", "donor": "donors", "evidence": "evidence", "lesson": "lessons", "option": "options",
            "part": "parts", "dependency": "dependencies", "pair": "pairs", "reviewer": "review"}.get(first)


def is_none(text):
    return bool(fm._NONE_FORM.match(text) or fm._NA_FORM.match(text))


def ids(text):
    return [x.strip() for x in re.split(r"[,;]", text) if x.strip()]


def check_lite(path):
    path = Path(path)
    text = fm.read_bounded(path).decode("utf-8-sig")
    root, lines = path.parent, text.splitlines()
    problems, escalate = [], []

    def at(index, message):
        problems.append("line " + str(index + 1) + ": " + message)

    for index, line in enumerate(lines):
        if not line.lstrip().startswith(">"):
            for match in PROMPT.finditer(line):
                at(index, "unreplaced prompt " + match.group(0))
    bullets = {m.group(1).strip().casefold(): m.group(2).strip() for m in map(BULLET.match, lines) if m}
    named = {}
    for header, rows in tables(lines):
        name = table_name(header)
        if name:
            named[name] = rows
        for index, row in rows:
            first = row.get(header[0], "")
            if is_none(first):
                if name not in NONE_ALLOWED:
                    at(index, "table '" + header[0] + "' needs real rows, not '" + first[:40] + "'")
                elif fm.text_issue(first):
                    at(index, fm.text_issue(first))
                continue
            for column, value in row.items():
                if not value:
                    at(index, "empty cell under '" + column + "'")
                elif column not in WORD_COLUMNS and not PROMPT.search(value) and fm.text_issue(value):
                    at(index, "'" + column + "' " + fm.text_issue(value))
            for file_column, hash_column in HASHED:
                rel, expected = row.get(file_column, ""), row.get(hash_column, "")
                if rel and expected and not PROMPT.search(rel + expected):
                    try:
                        actual = fm.digest(fm.local_bytes(root, rel.strip("`")))
                    except (OSError, ValueError) as exc:
                        at(index, "cannot read " + rel + " for its hash: " + str(exc))
                    else:
                        if actual != expected.strip("`").casefold():
                            at(index, "hash mismatch for " + rel + " (stamp writes the file's SHA-256)")

    def rows_of(name, required=True):
        rows = [(i, r) for i, r in named.get(name, []) if not is_none(next(iter(r.values()), ""))]
        if required and name not in named:
            problems.append("missing " + name + " table")
        return rows

    target = bullets.get("target language", "")
    donors = {r["Donor"]: (i, r) for i, r in rows_of("donors")}
    if len(donors) > 3:
        escalate.append("more than three donors (" + str(len(donors)) + "): move to the full tier")
    evidence = {r["Evidence"]: (i, r) for i, r in rows_of("evidence")}
    snapshots = {r.get("Snapshot file", "").strip("`") for _, r in evidence.values()} - {""}
    folders = {s.rsplit("/", 1)[0] for s in snapshots if "/" in s}
    for ident, (index, row) in evidence.items():
        donor = donors.get(row.get("Donor"))
        if donor is None:
            at(index, "evidence " + ident + " names an unknown donor")
            continue
        implied = set(fm.LANGUAGE_BY_EXTENSION.get(os.path.splitext(row.get("Snapshot file", ""))[1].casefold(), ()))
        language = donor[1].get("Language", "")
        if implied and fm.language_key(language) not in implied:
            at(index, "donor " + row["Donor"] + " language " + repr(language) + " disagrees with the snapshot "
               "extension, which implies " + ", ".join(sorted(implied)))

    requirements = rows_of("requirements")
    lessons = rows_of("lessons")
    for ident, (index, row) in donors.items():
        if row.get("Status, scope and blind spots", "").casefold().startswith("reviewed"):
            mine = [r for _, r in lessons if r.get("Donor") == ident]
            for direction in ("target-led", "donor-led"):
                if not any(r.get("Direction", "").casefold() == direction for r in mine):
                    problems.append("donor " + ident + " is reviewed but lacks a " + direction + " lesson")
            targets = {fm.norm_name(r.get("Problem → mechanism (invariant)", "")) for r in mine
                       if r.get("Direction", "").casefold() == "target-led"}
            if any(fm.norm_name(r.get("Problem → mechanism (invariant)", "")) in targets for r in mine
                   if r.get("Direction", "").casefold() == "donor-led"):
                problems.append("donor " + ident + ": the donor-led lesson repeats the target-led one")
    req_ids = {r["Req"] for _, r in requirements}
    for index, row in lessons:
        need = row.get("Need or hypothesis", "")
        if need and not PROMPT.search(need) and need not in req_ids and not need.casefold().startswith("hypothesis:"):
            at(index, "lesson need must be a requirement ID or 'hypothesis: ...'")
        for e in ids(row.get("Evidence", "")):
            if e not in evidence or evidence[e][1].get("Donor") != row.get("Donor"):
                at(index, "lesson evidence " + e + " is not evidence from donor " + row.get("Donor", "?"))

    parts = {}
    for index, row in rows_of("parts"):
        ident, route = row["Part"], " ".join(row.get("Route", "").casefold().split())
        kind = next((r for r in ROUTES if route.startswith(r)), None)
        basis = row.get("Basis", "").casefold()
        if kind is None and not PROMPT.search(route):
            at(index, "route must be one of " + ", ".join(ROUTES))
        if kind in ("process", "rpc"):
            escalate.append("part " + ident + " uses a " + kind + " route, which needs a protocol contract: move to "
                            "the full tier")
        from_code = kind == "reimplementation" and "from code" in route
        if kind == "reimplementation" and not from_code and "from idea" not in route:
            at(index, "reuse route 'reimplementation' must say 'from code' or 'from idea'")
        code = kind in LITE_CODE_ROUTES or from_code
        if basis and not PROMPT.search(basis) and basis not in BASES:
            at(index, "basis must be licensed-reuse, permission or idea-only")
        donor = donors.get(row.get("Donor"))
        if donor is None:
            at(index, "part " + ident + " names an unknown donor")
        else:
            dindex, drow = donor
            category = drow.get("Licence category", "").casefold()
            if not drow.get("Status, scope and blind spots", "").casefold().startswith("reviewed"):
                at(dindex, "donor " + drow["Donor"] + " supplies part " + ident + " but is not reviewed")
            if not fm.is_real_pin(drow.get("Pin", "")) and not PROMPT.search(drow.get("Pin", "")):
                at(dindex, "donor " + drow["Donor"] + " supplies part " + ident + " and needs a real pin (full commit "
                   "or tag@sha256)")
            if category not in CATEGORIES and not PROMPT.search(category):
                at(dindex, "licence category must be one of " + ", ".join(CATEGORIES))
            if code and basis not in ("licensed-reuse", "permission"):
                at(index, "route " + route + " reuses donor code; basis " + (basis or "missing") + " does not permit it")
            elif code and category in fm.PERMISSION_CATEGORIES and basis != "permission":
                at(index, category + " code needs basis permission")
            if code and target and fm.language_key(drow.get("Language", "")) != fm.language_key(target):
                escalate.append("part " + ident + " is cross-language code reuse (" + drow.get("Language", "?") + " to " +
                                target + "), which needs semantic deltas: move to the full tier")
        touches = {fm.norm_key(k) for k in ids(row.get("Touches", "")) if not is_none(k)}
        if not touches:
            at(index, "touches must list the state, policy or interface keys the part uses")
        seams = row.get("Material seams", "")
        if seams and not PROMPT.search(seams) and not is_none(seams):
            for entry in (x.strip() for x in seams.split(";") if x.strip()):  # notes may contain commas
                name = entry.split(":", 1)[0].strip().casefold().replace("_", " ")
                if ":" not in entry or name not in SEAM_NAMES:
                    at(index, "material seam '" + entry[:40] + "' must read 'dimension: note' with a seam dimension")
        for e in ids(row.get("Evidence", "")):
            if e not in evidence or evidence[e][1].get("Donor") != row.get("Donor"):
                at(index, "part evidence " + e + " is not evidence from donor " + row.get("Donor", "?"))
        parts[ident] = dict(index=index, kind=kind, code=code, basis=basis, touches=touches)
    if "other seam dimensions" not in bullets:
        problems.append("missing 'Other seam dimensions' declaration")
    sharing = {}
    for ident, part in parts.items():
        for key in part["touches"]:
            sharing.setdefault(key, []).append(ident)
    for key, owners in sorted(sharing.items()):
        if len(owners) >= 3:
            escalate.append("key " + key + " is touched by three or more parts (" + ", ".join(owners) + "): move to "
                            "the full tier for group interactions")

    for index, row in requirements:
        for ref in ids(row.get("Met by", "")):
            if PROMPT.search(ref):
                continue
            prefix = next((p for p in ("new:", "existing:") if ref.casefold().startswith(p)), None)
            if prefix and not fm.text_issue(ref[len(prefix):] or "?"):
                continue
            if ref not in parts:
                at(index, "requirement " + row["Req"] + " is met by unknown part " + ref)

    options = {r.get("Option", "").casefold(): r for _, r in rows_of("options")}
    for label in ("Best existing", "Minimal fresh", "Fusion"):
        if label.casefold() not in options:
            problems.append("missing option: " + label)
    choice = bullets.get("decision", "").casefold().split(",")[0].strip()
    if choice == "defer":
        problems.append("decision is defer: design not ready")
    elif choice not in ("fusion", "minimal-fresh", "best-existing") and not PROMPT.search(choice):
        problems.append("decision must be fusion, minimal-fresh, best-existing or defer")
    rationale = bullets.get("rationale", "")
    if not rationale or (not PROMPT.search(rationale) and fm.text_issue(rationale)):
        problems.append("decision needs a rationale")
    reused = [p for p, part in parts.items() if part["kind"] not in (None, "pattern-only")]
    if choice == "fusion" and parts and not reused:
        problems.append("fusion needs at least one reused unit; lessons alone are minimal-fresh or best-existing")
    if choice in ("minimal-fresh", "best-existing") and reused:
        problems.append(choice + " keeps only pattern-only parts; reused: " + ", ".join(reused))

    if any(part["code"] for part in parts.values()):
        if "dependencies" not in named:
            problems.append("a code route needs the dependency table (or one row reading none: <reason>)")
        for index, row in rows_of("dependencies", required=False):
            part = parts.get(row.get("Part"))
            disposition = row.get("Disposition", "").casefold()
            category = row.get("Licence category", "").casefold()
            if part is None:
                at(index, "dependency names an unknown part")
            if disposition not in ("retain", "replace", "bridge", "exclude"):
                at(index, "dependency disposition must be retain, replace, bridge or exclude")
            if disposition in ("retain", "bridge") and not fm.is_exact_pin(row.get("Pin", "")):
                at(index, "retained dependency needs an exact pin")
            if category not in CATEGORIES:
                at(index, "dependency licence category must be one of " + ", ".join(CATEGORIES))
            elif category in fm.PERMISSION_CATEGORIES and part and part["basis"] != "permission":
                at(index, category + " dependency needs the part's basis to be permission")

    tests = {r["Test"]: (i, r) for i, r in rows_of("tests")}
    for ident, part in parts.items():
        purposes = {r.get("Purpose", "").casefold() for _, r in tests.values() if r.get("Part") == ident}
        if not purposes & {"product", "adapter", "integration"}:
            problems.append("part " + ident + " needs an acceptance test")
        if "negative-control" not in purposes:
            problems.append("part " + ident + " needs a negative control")
    for ident, (index, row) in tests.items():
        oracle = row.get("Oracle file", "").strip("`")
        if oracle in snapshots or any(oracle.startswith(f + "/") for f in folders):
            at(index, "oracle " + oracle + " is a donor snapshot or sits in a donor snapshot folder")

    if len(parts) >= 2:
        pairs = {}
        for index, row in rows_of("pairs"):
            pairs[frozenset(x.strip() for x in row.get("Pair", "").split("/"))] = (index, row)
        for left, right in itertools.combinations(sorted(parts), 2):
            entry = pairs.get(frozenset((left, right)))
            if entry is None:
                problems.append("pair " + left + " / " + right + " has no interaction row")
                continue
            index, row = entry
            disposition = row.get("Disposition", "").casefold()
            if disposition == "independent":
                shared = parts[left]["touches"] & parts[right]["touches"]
                if shared:
                    at(index, "pair is independent but both touch " + ", ".join(sorted(shared)))
            elif disposition in ("compatible", "resolved"):
                verifying = [t for t in ids(row.get("Test or reason", "")) if t in tests and
                             tests[t][1].get("Purpose", "").casefold() in ("integration", "interaction")]
                if not verifying:
                    at(index, "a compatible or resolved pair needs an integration test from the tests table")
            elif not PROMPT.search(disposition):
                at(index, "pair disposition must be independent, compatible or resolved")

    review = rows_of("review")
    if len(review) != 1 and "review" in named:
        problems.append("the review table needs exactly one reviewer row")
    for index, row in review:
        level = row.get("Independence", "").casefold()
        if level == "self":
            at(index, "review independence is self; it needs " + ", ".join(LEVELS))
        elif level not in LEVELS and not PROMPT.search(level):
            at(index, "independence must be one of " + ", ".join(LEVELS))
        report = row.get("Report file", "").strip("`")
        if report and not PROMPT.search(report):
            try:
                body = " ".join(fm.local_bytes(root, report).decode("utf-8").split()).casefold()
            except (OSError, ValueError, UnicodeError):
                body = None
            if body is not None and (fm.norm_name(row.get("Reviewer", "")) not in body or level not in body):
                at(index, "review report does not name the recorded reviewer and independence level")

    state = bullets.get("implementation", "").casefold()
    if state not in ("not-started", "implemented", "tested") and not PROMPT.search(state):
        problems.append("implementation must be not-started, implemented or tested")
    if state in ("implemented", "tested"):
        receipts = rows_of("receipts", required=False)
        if "receipts" not in named:
            problems.append("implementation is " + state + " but there is no receipts table bound to product files")
        raw_seen = set()
        for index, row in receipts:
            if row.get("Test") not in tests:
                at(index, "receipt names an unknown test")
            if row.get("Result", "").casefold() not in ("pass", "fail"):
                at(index, "receipt result must be pass or fail")
            elif row["Result"].casefold() == "fail":
                at(index, "receipt for " + row.get("Test", "?") + " failed")
            if row.get("Raw output") in raw_seen:
                at(index, "each receipt needs its own raw output")
            raw_seen.add(row.get("Raw output"))
            product = row.get("Product file", "").strip("`")
            if product in snapshots or any(product.startswith(f + "/") for f in folders):
                at(index, "product file " + product + " is a donor snapshot")
        missing = sorted(set(tests) - {r.get("Test") for _, r in receipts})
        if state == "tested" and missing:
            problems.append("tested work needs a receipt for every test; missing " + ", ".join(missing))

    boxes = [(i, m) for i, m in ((i, CHECKBOX.match(line)) for i, line in enumerate(lines)) if m]
    if not boxes:
        problems.append("readiness checklist missing")
    for index, match in boxes:
        if match.group(1) == " ":
            at(index, "unticked readiness item: " + match.group(2)[:90])
    status = "escalate-to-full" if escalate else "lite-complete" if not problems else "lite-incomplete"
    return dict(status=status, path=str(path), escalate=escalate, problems=problems, not_checked=NOT_CHECKED,
                scope="lite structure, file hashes and key cross-checks; not package-schema validation, design "
                      "readiness or semantic proof")


def scaffold_lite(output, donors, parts, requirements, product=None):
    """Write a lite dossier from the template with numbered rows; every judgement stays a prompt."""
    if not 1 <= donors <= 3:
        raise ValueError("lite takes one to three donors; use the full tier for more")
    if parts < 1 or requirements < 1:
        raise ValueError("lite needs at least one part and one requirement")
    template = (fm.PACKAGE / "examples" / "lite-dossier.md").read_text(encoding="utf-8").splitlines()
    out = []
    for line in template:
        if line.startswith("| R1 |"):
            out += [line.replace("| R1 |", "| R" + str(k) + " |", 1) for k in range(1, requirements + 1)]
        elif line.startswith("| D1 |"):
            out += [line.replace("| D1 |", "| D" + str(d) + " |", 1) for d in range(1, donors + 1)]
        elif line.startswith("| E1 | D1 |"):
            out += [line.replace("| E1 | D1 |", "| E" + str(d) + " | D" + str(d) + " |", 1) for d in range(1, donors + 1)]
        elif line.startswith("| L1 | D1 |"):
            for d in range(1, donors + 1):
                for n, direction in ((2 * d - 1, "target-led"), (2 * d, "donor-led")):
                    row = line.replace("| L1 | D1 | target-led |", "| L" + str(n) + " | D" + str(d) + " | " + direction + " |")
                    if direction == "donor-led":
                        row = row.replace("| &lt;...&gt; | E1 |", "| &lt;hypothesis: ...&gt; | E1 |", 1)
                    out.append(row.replace("| E1 |", "| E" + str(d) + " |"))
        elif line.startswith("| L2 | D1 |"):
            continue
        elif line.startswith("| P1 | D1 |"):
            for p in range(1, parts + 1):
                d = min(p, donors)
                out.append(line.replace("| P1 | D1 |", "| P" + str(p) + " | D" + str(d) + " |", 1)
                           .replace("| E1 |", "| E" + str(d) + " |"))
        elif line.startswith("| T1 | P1 |"):
            for p in range(1, parts + 1):
                out.append(line.replace("| T1 | P1 |", "| T" + str(2 * p - 1) + " | P" + str(p) + " |", 1))
                out.append(line.replace("| T1 | P1 | product |", "| T" + str(2 * p) + " | P" + str(p) +
                                        " | negative-control |", 1))
        elif line.startswith("| T2 | P1 |"):
            continue
        elif line.startswith("| &lt;P1 / P2&gt; |"):
            pairs = list(itertools.combinations(range(1, parts + 1), 2))
            out += [line.replace("| &lt;P1 / P2&gt; |", "| P" + str(a) + " / P" + str(b) + " |", 1) for a, b in pairs]
            if not pairs:
                out.append("| none: one part only | n/a: no pair to review | n/a: no pair to review |")
        else:
            out.append(line.replace("&lt;Product&gt;", product, 1) if product and line.startswith("# ") else line)
    fm.write_new(output, "\n".join(out) + "\n")
    return dict(status="scaffolded-lite", ok=True, path=str(output), donors=donors, parts=parts,
                requirements=requirements, note="Fill every prompt, run stamp for the SHA-256 cells, then check-lite; "
                                                "a scaffolded dossier never passes until it is filled.")


def stamp_lite(source, output):
    """Fill missing SHA-256 cells of a lite dossier into a NEW file; never rewrite a recorded hash.

    The new file must sit beside its source: check-lite resolves the dossier's file paths from its own
    folder, so a copy written anywhere else could not be checked and would be a write outside that folder."""
    source = Path(source)
    if Path(output).resolve().parent != source.resolve().parent:
        raise ValueError("stamp writes a lite dossier beside its source, in " + str(source.resolve().parent) +
                         ", where its file paths resolve; choose a new file name in that folder")
    lines = fm.read_bounded(source).decode("utf-8-sig").splitlines()
    root, filled, mismatches, unreadable = source.parent, [], [], []
    for header, rows in tables(lines):
        for index, row in rows:
            changed = False
            for file_column, hash_column in HASHED:
                rel = row.get(file_column, "").strip("`")
                if not rel or hash_column not in row or PROMPT.search(rel) or is_none(rel):
                    continue
                try:
                    actual = fm.digest(fm.local_bytes(root, rel))
                except (OSError, ValueError) as exc:
                    unreadable.append("line " + str(index + 1) + " " + rel + ": " + str(exc))
                    continue
                recorded = row[hash_column].strip("`").casefold()
                if re.fullmatch(r"[0-9a-f]{64}", recorded):
                    if recorded != actual:
                        mismatches.append("line " + str(index + 1) + " " + rel + ": recorded hash differs; not rewritten")
                    continue
                row[hash_column], changed = actual, True
                filled.append("line " + str(index + 1) + " " + rel)
            if changed:
                lines[index] = "| " + " | ".join(row[column] for column in header) + " |"
    fm.write_new(output, "\n".join(lines) + "\n")
    ok = not mismatches and not unreadable
    return dict(status="stamped" if ok else "stamped-with-findings", ok=ok, path=str(output), filled=filled,
                mismatches=mismatches, unreadable=unreadable,
                note="Only missing hashes are filled; recorded hashes are never rewritten. Run check-lite next.")
