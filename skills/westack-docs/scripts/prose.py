"""westack-docs prose helper: compare a rewrite with its original, lint prose by document type, lint westack's own pages.

  python prose.py preserve ORIGINAL REWRITE [--map MAP]
  python prose.py lint FILE... [--type DOCTYPE] [--mode draft|delivery] [--roots CONFIG] [--rules RULES]
  python prose.py selflint ROOT [--rules RULES]
  python prose.py inventory DOC FOLDER [--glob PATTERN] [--recursive]
  python prose.py series FOLDER [--glob PATTERN]

preserve  WD-2, WD-1, WD-3. Fails on a changed code fence, front matter, quotation (blockquote lines and double-quoted
          spans), table row, inline code span, link target, file path or sequence of heading levels; on a dropped hedge,
          condition or attribution word, a changed negation or scope word (only, first, most, all, every, never, none,
          always) or an added strength word (will, must, caused, proved and the like); and on a number or a name in the
          rewrite that the original lacks. Warns on a dropped number or name, changed heading wording and a rewrite under
          60 percent of the original's words. With --map (JSON {"changes": [{"id": "F1", "lines": [first, last]}]}, lines
          of ORIGINAL) every changed hunk must overlap a listed finding or request. A byte-identical rewrite passes: it is
          the no-op result.
lint      WD-4, WD-5, WD-6, WD-12, WD-13, WD-14, WD-16, WD-18. Applies references/rules.json to each file at the level
          its document type sets (strict, relaxed or skip; --type, or inferred from the file name). A skipped rule is
          listed as not audited. Code spans and fences are masked for rules that do not apply inside code. Gap markers
          are listed as open; in --mode delivery (the default) each is also a finding, in draft it is not. --roots CONFIG
          ({"format": "westack-docs-roots-1", "roots": [...], "exceptions": [{"path", "reason"}]}) fails a file outside
          the roots that is not an exact, reasoned exception.
selflint  WD-8. Lints every Markdown file under ROOT and reports, per rule, the naive count (no exclusions), the count
          kept after the exclusions and the count gated against its ceiling, and per exclusion the hits it removed: an
          exclusion that removed nothing shows 0. A gated count over its ceiling (0 unless the rules file lists one with
          its log) is a finding.

The rules file is checked as it loads (WD-7): every regex or builtin rule has examples it must fire on and must not fire
on, and both agree; a judgment rule has a reason; a reverted detector names the false positive that removed it; a
numeric gate (WD-9) has a corpus of at least 100 documents in at least two registers whose hashes still match; and a
ceiling has a log in which it only moved down. A rules file that fails stops the run.

inventory DS-5. A document that lists a folder's files is checked both ways: each file of FOLDER matching --glob that DOC
          does not name is `inventory-unlisted`, and each matching file DOC names that FOLDER lacks is `inventory-stale`. DOC
          names a file in a code span or a link target (a bare name is the folder's own, a path is read from DOC's folder,
          as a link is); fenced blocks and bare names in prose are not read. --recursive reads subfolders too.
series    DS-5. In FOLDER's numbered documents (names starting with digits and a dash, underscore or dot), a link to a
          numbered document of the same or a higher number is `series-forward-link`. Links in fences, to other folders,
          to unnumbered documents and external links are not read.

Exit 0 clean, 1 findings (fail severity; candidates and warnings never change the exit code), 2 unreadable (a missing
or non-UTF-8 file, an unusable rules, roots or map file, a corpus hash mismatch), 64 usage. Standard library only. It
reads the files named and prints JSON; it writes no file, runs no command and opens no network connection.
"""
import argparse
import difflib
import fnmatch
import hashlib
import json
import os
import pathlib
import re
import sys
from collections import Counter

FORMAT = "westack-docs-prose-1"
RULES_FORMAT = "westack-docs-rules-1"
ROOTS_FORMAT = "westack-docs-roots-1"
DEFAULT_RULES = pathlib.Path(__file__).resolve().parent.parent / "references" / "rules.json"
LEVELS = ("strict", "relaxed", "skip")
SEVERITIES = ("fail", "candidate")
KINDS = ("regex", "builtin", "judgment")
EXCLUSIONS = ("not-shipped", "doctype-skip", "code")
NOT_SHIPPED = ("evals", "tests")
SKIP_DIRS = ("node_modules", "__pycache__")
SHRINK = 0.6
WRAP_WIDTH = 50
MIN_CORPUS = 100
FLAGS = {"i": re.I, "m": re.M, "s": re.S, "x": re.X}
CLAIMS = {
    "preserve": "a mechanical comparison, not semantic proof: a claim reworded without a number, name, hedge, condition "
                "or scope word passes every check here, and a word list cannot tell a synonym from a shift in meaning",
    "lint": "candidates for a reader, not verdicts: only the forms in references/rules.json are caught, judgment rules "
            "are not checked, a skipped rule was not audited, and a clean result says nothing about accuracy or clarity; "
            "no file was edited",
    "selflint": "counts the rules' own patterns over westack's Markdown: a clean run shows no fail-rule hit above its "
                "ceiling after the listed exclusions, not that the pages are accurate or well written; no file was edited",
}

FENCE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
INLINE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
FRONT = re.compile(r"\A(?:﻿)?---\n.*?\n---[ \t]*(?:\n|\Z)", re.S)
HEADING = re.compile(r"^[ ]{0,3}(#{1,6})[ \t]+(.*?)[ \t#]*$")
LINK_TARGET = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_DEF = re.compile(r"^[ ]{0,3}\[[^\]]+\]:\s*(\S+)", re.M)
URL = re.compile(r"\b(?:https?|ftp)://[^\s<>()\"'`]+")
QUOTED = re.compile(r"\"[^\"\n]{2,}?\"|“[^”\n]{2,}?”")
PATH = re.compile(r"(?<![\w/.-])(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+\b|\b[\w-]+\.(?:md|py|js|ts|json|ya?ml|toml|txt|sh|ps1|cfg|ini|html|css|lock)\b")
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*%?")
NAME = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)*\b")
WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
SENTENCE = re.compile(r"[^.!?\n]+")
LIST_OR_BLOCK = re.compile(r"\s*(?:[-*+][ \t]|\d+[.)][ \t]|#|\||>|`{3}|~{3})")
COMPARATIVE = re.compile(r"\b(?:faster|slower|quicker|cheaper|smaller|larger|bigger|better|worse|safer|simpler|lighter|"
                         r"leaner|more (?:reliable|efficient|accurate|secure|robust|scalable|stable|performant|readable|"
                         r"maintainable)|less (?:error-prone|expensive|memory|cpu))\b", re.I)
BASELINE = re.compile(r"\bthan\b|\bcompared (?:to|with)\b|\bvs\.?(?=\s)|\bversus\b|\brelative to\b|\d", re.I)
INVISIBLE = {"​", "‍", "⁠", "­", "﻿", "᠎"}
AS_BUILT = (("last-verified commit", re.compile(r"(?im)^\W*last[ -]verified(?: against)?(?: source)?\W*\s*.*?\b[0-9a-f]{7,40}\b")),
            ("last-updated date", re.compile(r"(?im)^\W*last[ -]updated\W*\s*\d{4}-\d{2}-\d{2}")),
            ("applies-when line", re.compile(r"(?im)^\W*applies[ -]when\W*:\s*\S")))
# WD-1: the meaning-bearing words. Dropping a hedge, condition or attribution word, adding a strength word, or changing a
# negation or scope word fails; counts are per class, so a synonym inside one class (may for might) passes.
CLASSES = {
    "hedge": {"may", "might", "could", "some", "several", "often", "usually", "sometimes", "typically", "likely",
              "unlikely", "possibly", "probably", "perhaps", "approximately", "roughly", "generally", "partly"},
    "condition": {"if", "unless", "except", "until", "when", "whenever", "provided", "whether"},
    "attribution": {"according", "says", "said", "say", "reports", "reported", "reportedly", "claims", "claimed",
                    "suggests", "suggested", "suggest", "associated", "correlated", "appears", "appear", "seems", "seem"},
    "negation": {"not", "no", "nor", "neither", "without", "cannot"},
    "strength": {"will", "must", "certainly", "definitely", "clearly", "proves", "proved", "proven", "caused", "causes",
                 "guarantees", "guaranteed", "always"},
    "scope": {"only", "first", "most", "all", "every", "never", "none", "always"},
}


class RuleFileError(ValueError):
    """The rules file cannot be used: it breaks its contract, or a corpus it names has changed."""


class InputError(ValueError):
    """An input file cannot be read as UTF-8 text, or a roots or map file is not usable."""


class UsageError(ValueError):
    """A request the command line should have refused."""


# ---- reading and masking ---------------------------------------------------------------------------------------------
def read_text(path):
    """The file as text. Strict UTF-8 (a leading byte-order mark allowed); anything else is unreadable, never guessed."""
    try:
        data = pathlib.Path(path).read_bytes()
    except OSError as exc:
        raise InputError("%s cannot be read: %s" % (path, exc)) from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError("%s is not UTF-8 (byte %d): unscannable, never clean" % (path, exc.start)) from None
    return text.replace("\r\n", "\n")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def code_regions(text):
    """(start, end, kind) for the front matter, each fenced block and each inline code span."""
    regions = []
    front = FRONT.match(text)
    if front:
        regions.append((0, front.end(), "front"))
    position, fence, fence_start = (front.end() if front else 0), None, 0
    plain = []
    for line in text[position:].split("\n"):
        start, end = position, position + len(line)
        marker = FENCE.match(line)
        if fence is None and marker:
            fence, fence_start = marker.group(1), start
        elif fence is not None and marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence) \
                and not line.strip()[len(marker.group(1)):].strip():
            regions.append((fence_start, end, "fence"))
            fence = None
        elif fence is None:
            plain.append((start, line))
        position = end + 1
    if fence is not None:
        regions.append((fence_start, len(text), "fence"))
    for start, line in plain:
        for match in INLINE.finditer(line):
            regions.append((start + match.start(), start + match.end(), "inline"))
    return sorted(regions)


def code_only(text):
    """The fences and inline code spans: front matter is prose to a reader (a skill's description, a page title)."""
    return [region for region in code_regions(text) if region[2] != "front"]


def mask(text, regions):
    """The text with every region blanked to spaces, newlines kept, so offsets and line numbers do not move."""
    chars = list(text)
    for start, end, _ in regions:
        for i in range(start, min(end, len(chars))):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def inside(offset, regions):
    return any(start <= offset < end for start, end, _ in regions)


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def shown(text):
    text = text.replace("\n", "\\n")
    return text if len(text) <= 80 else text[:77] + "..."


# ---- the rules file (WD-7, WD-9, WD-8 ceilings) ----------------------------------------------------------------------
def invisible_chars(text):
    for i, ch in enumerate(text):
        if ch in INVISIBLE:
            if ch == "﻿" and i == 0:
                continue  # a leading byte-order mark is carved out
            if ch == "‍" and joins_emoji(text, i):
                continue
            yield i, "U+%04X" % ord(ch)
        elif 0xE000 <= ord(ch) <= 0xF8FF or ord(ch) >= 0xF0000:
            yield i, "private-use U+%04X" % ord(ch)


def pictographic(ch):
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF


def joins_emoji(text, i):
    before = i - 1
    while before >= 0 and (text[before] == "️" or 0x1F3FB <= ord(text[before]) <= 0x1F3FF):
        before -= 1
    return before >= 0 and i + 1 < len(text) and pictographic(text[before]) and pictographic(text[i + 1])


def comparatives(text):
    for match in SENTENCE.finditer(text):
        sentence = match.group(0)
        if COMPARATIVE.search(sentence) and not BASELINE.search(sentence):
            yield match.start() + COMPARATIVE.search(sentence).start(), "no baseline or number in the sentence"


def as_built_header(text):
    missing = [name for name, pattern in AS_BUILT if not pattern.search(text)]
    if missing:
        yield 0, "missing: " + ", ".join(missing)


def prose_line(line):
    return bool(line.strip()) and not line.startswith("    ") and not LIST_OR_BLOCK.match(line)


def hard_wraps(text):
    lines, offset = text.split("\n"), 0
    for i, first in enumerate(lines[:-1]):
        second = lines[i + 1]
        if prose_line(first) and prose_line(second) and not first.endswith(("  ", "\\")):
            if len(first) >= WRAP_WIDTH:
                yield offset + len(first) + 1, "a paragraph broken across lines"
        offset += len(first) + 1


BUILTINS = {"invisible-char": invisible_chars, "comparative-no-baseline": comparatives,
            "as-built-header": as_built_header, "hard-wrap": hard_wraps}


class Rule:
    def __init__(self, raw):
        self.id, self.item, self.kind = raw["id"], raw.get("item", ""), raw["kind"]
        self.severity = raw.get("severity", "candidate")
        self.in_code = bool(raw.get("in_code", False))
        self.levels = raw.get("levels", {"default": "strict"})
        self.gate = None
        self.regex = None
        if self.kind == "regex":
            flags = 0
            for letter in raw.get("flags", ""):
                flags |= FLAGS[letter]
            self.regex = re.compile(raw["pattern"], flags)

    def level(self, doctype):
        return self.levels.get(doctype, self.levels.get("default", "strict"))

    def scan(self, text):
        """(offset, matched text) for every hit in text, as given (the caller masks code when the rule wants it)."""
        if self.kind == "regex":
            for match in self.regex.finditer(text):
                yield match.start(), match.group(0)
        elif self.kind == "builtin":
            yield from BUILTINS[self.id](text)


def fires(rule, example):
    target = example if rule.in_code else mask(example, code_only(example))
    return any(True for _ in rule.scan(target))


def examples(value):
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list) or not items or not all(isinstance(i, str) and i for i in items):
        return None
    return items


def text_field(value):
    return isinstance(value, str) and bool(value.strip())


def rule_problems(raw, doctypes, seen):
    if not isinstance(raw, dict) or not text_field(raw.get("id")):
        return ["a rule without an id"]
    rid = raw["id"]
    if rid in seen:
        return [rid + ": duplicate id"]
    seen.add(rid)
    problems = []
    if raw.get("kind") not in KINDS:
        return [rid + ": kind must be regex, builtin or judgment"]
    if raw["kind"] == "judgment":
        if not text_field(raw.get("why")):
            problems.append(rid + ": a judgment rule needs a why")
        if "pattern" in raw:
            problems.append(rid + ": a judgment rule has no pattern")
        return problems
    if raw.get("severity") not in SEVERITIES:
        problems.append(rid + ": severity must be fail or candidate")
    levels = raw.get("levels")
    if not isinstance(levels, dict) or "default" not in levels:
        problems.append(rid + ": levels needs a default")
    else:
        for doctype, level in levels.items():
            if doctype != "default" and doctype not in doctypes:
                problems.append(rid + ": levels names an unknown document type " + doctype)
            if level not in LEVELS:
                problems.append(rid + ": level must be strict, relaxed or skip")
    if raw["kind"] == "regex":
        if set(raw.get("flags", "")) - set(FLAGS):
            return problems + [rid + ": unknown regex flag"]
        try:
            Rule(raw)
        except (re.error, KeyError) as exc:
            return problems + [rid + ": pattern does not compile: %s" % exc]
    elif rid not in BUILTINS:
        return problems + [rid + ": no builtin of that name"]
    must, must_not = examples(raw.get("must_match")), examples(raw.get("must_not_match"))
    if not must:
        problems.append(rid + ": needs at least one must_match example")
    if not must_not:
        problems.append(rid + ": needs at least one must_not_match example (a case it must not fire on)")
    rule = Rule(raw)
    for example in must or []:
        if not fires(rule, example):
            problems.append(rid + ": must fire on " + shown(example))
    for example in must_not or []:
        if fires(rule, example):
            problems.append(rid + ": must not fire on " + shown(example))
    if not text_field(raw.get("why")):
        problems.append(rid + ": needs a why")
    return problems


def gate_problems(gates, base, ids):
    """WD-9: a numeric gate names a hashed corpus of the project's own documents, n of at least 100, two registers."""
    problems = []
    for gate in gates:
        name = "gate " + str(gate.get("rule"))
        if gate.get("rule") not in ids:
            problems.append(name + ": names no checked rule")
        if not isinstance(gate.get("per_1000_words"), (int, float)) or gate["per_1000_words"] <= 0:
            problems.append(name + ": per_1000_words must be a positive number")
        if gate.get("n", 0) < MIN_CORPUS:
            problems.append(name + ": n under 100: report no rate from fewer than 100 documents")
        registers = gate.get("registers") or []
        if len(set(registers)) < 2:
            problems.append(name + ": one register: report no rate from a single register")
        corpus = gate.get("corpus") or {}
        try:
            raw = (pathlib.Path(base) / corpus.get("manifest", "")).read_bytes()
            entries = json.loads(raw.decode("utf-8"))["files"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(name + ": corpus manifest cannot be read: %s" % exc)
            continue
        manifest_digest = sha256(raw)
        if manifest_digest != corpus.get("sha256"):
            problems.append(name + ": corpus hash mismatch: the manifest changed since calibration")
        if len(entries) != gate.get("n"):
            problems.append(name + ": n does not match the manifest's %d files" % len(entries))
        if {entry.get("register") for entry in entries} != set(registers):
            problems.append(name + ": the manifest's registers differ from the gate's")
        for entry in entries:
            try:
                digest = sha256((pathlib.Path(base) / entry["path"]).read_bytes())
            except (OSError, KeyError, TypeError):
                problems.append(name + ": corpus file missing: %s" % entry.get("path"))
                continue
            if digest != entry.get("sha256"):
                problems.append(name + ": corpus hash mismatch: " + str(entry.get("path")))
    return problems


def ceiling_problems(config, ids):
    """WD-8: a ceiling above 0 is logged; each log entry may only lower it."""
    problems = []
    unknown = set(config.get("exclusions", {})) - set(EXCLUSIONS)
    if unknown:
        problems.append("selflint: unknown exclusions " + ", ".join(sorted(unknown)))
    ceilings = config.get("ceilings", {})
    history = {}
    for entry in config.get("ceiling_log", []):
        rule = entry.get("rule")
        if rule not in ids or not isinstance(entry.get("to"), int) or entry["to"] < 0:
            problems.append("selflint: a ceiling log entry names no rule or no value")
            continue
        if not text_field(entry.get("reason")) or not text_field(entry.get("date")):
            problems.append("selflint: the ceiling log entry for %s needs a date and a reason" % rule)
        if rule in history:
            if entry.get("from") != history[rule]:
                problems.append("selflint: the log for %s does not continue from %s" % (rule, history[rule]))
            elif entry["to"] > entry["from"]:
                problems.append("selflint: the ceiling for %s was raised: a ceiling can only move down" % rule)
        history[rule] = entry["to"]
    for rule, value in ceilings.items():
        if rule not in ids or not isinstance(value, int) or value < 0:
            problems.append("selflint: ceiling for %s must be a whole number for a known rule" % rule)
        elif value > 0 and history.get(rule) != value:
            problems.append("selflint: the ceiling for %s is %s but its log ends at %s: log every value" % (rule, value, history.get(rule)))
    return problems


def contract_problems(data, base=None):
    """Every way the rules file breaks its contract, as strings (empty when it loads)."""
    if not isinstance(data, dict) or data.get("format") != RULES_FORMAT:
        return ["not a %s file" % RULES_FORMAT]
    doctypes = data.get("doctypes")
    if not isinstance(doctypes, dict) or not doctypes:
        return ["doctypes missing"]
    if not isinstance(data.get("rules"), list) or not data["rules"]:
        return ["rules missing"]
    problems, seen = [], set()
    for raw in data["rules"]:
        problems += rule_problems(raw, doctypes, seen)
    for entry in data.get("reverted", []):
        if not text_field(entry.get("id")) or not text_field(entry.get("why")):
            problems.append("reverted: an entry needs an id and a why")
        if not text_field(entry.get("false_positive")):
            problems.append("reverted %s: needs the false_positive that removed it" % entry.get("id"))
    checked = {r["id"] for r in data["rules"] if isinstance(r, dict) and r.get("kind") in ("regex", "builtin")}
    problems += gate_problems(data.get("gates", []), base or ".", checked)
    problems += ceiling_problems(data.get("selflint", {}), checked)
    return problems


def load_rules(path=None):
    """The checked rules: {"rules": [Rule], "doctypes", "selflint", "judgment", "sha256"}; RuleFileError otherwise."""
    path = pathlib.Path(path or DEFAULT_RULES)
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise RuleFileError("the rules file %s cannot be read: %s" % (path, exc)) from None
    problems = contract_problems(data, path.parent)
    if problems:
        raise RuleFileError("; ".join(problems))
    rules = [Rule(r) for r in data["rules"] if r["kind"] != "judgment"]
    gates = {g["rule"]: g for g in data.get("gates", [])}
    for rule in rules:
        rule.gate = gates.get(rule.id)
    return {"rules": rules, "doctypes": data["doctypes"], "selflint": data.get("selflint", {}),
            "judgment": [r["id"] for r in data["rules"] if r["kind"] == "judgment"], "sha256": sha256(raw)}


# ---- preserve (WD-2, WD-1, WD-3) -------------------------------------------------------------------------------------
def expand(text):
    text = re.sub(r"\bwon't\b", "will not", text, flags=re.I)
    text = re.sub(r"\bcan't\b|\bcannot\b", "can not", text, flags=re.I)
    return re.sub(r"(\w)n't\b", r"\1 not", text, flags=re.I)


def names(prose):
    found = set()
    for match in NAME.finditer(prose):
        word = match.group(0)
        i = match.start() - 1
        while i >= 0 and prose[i] in " \t":
            i -= 1
        sentence_start = i < 0 or prose[i] in "\n.!?:;|#>-*+(\"'“‘[`"
        if word == "I" or (sentence_start and not re.search(r"[A-Z0-9]", word[1:])):
            continue
        found.add(word)
    return found


class Doc:
    def __init__(self, text):
        self.text = text
        regions = code_regions(text)
        self.front = "".join(text[s:e] for s, e, k in regions if k == "front")
        self.fences = [text[s:e] for s, e, k in regions if k == "fence"]
        self.inline = [text[s:e] for s, e, k in regions if k == "inline"]
        masked = mask(text, regions)
        lines = masked.split("\n")
        self.headings = [(len(m.group(1)), m.group(2).strip()) for m in (HEADING.match(line) for line in lines) if m]
        self.tables = ["|".join(c.strip() for c in line.strip().strip("|").split("|")) for line in lines
                       if line.lstrip().startswith("|")]
        self.links = LINK_TARGET.findall(masked) + REF_DEF.findall(masked) + [u.rstrip(".,;:") for u in URL.findall(masked)]
        spans = [(m.start(1), m.end(1), "link") for m in LINK_TARGET.finditer(masked)]
        spans += [(m.start(), m.end(), "url") for m in URL.finditer(masked)]
        plain = mask(masked, spans)
        self.quotes = [line.strip().lstrip(">").strip() for line in lines if line.lstrip().startswith(">")]
        self.quotes += [q.replace("“", "\"").replace("”", "\"") for q in QUOTED.findall(plain)]
        self.paths = PATH.findall(plain)
        self.words = plain.split()
        self.numbers = set(NUMBER.findall(plain))
        self.names = names(plain)
        tokens = WORD.findall(expand(plain).lower())
        self.vocabulary = set(tokens)
        self.classes = {name: sum(1 for t in tokens if t in words) for name, words in CLASSES.items()}


def change_spans(map_path):
    try:
        data = json.loads(read_text(map_path))
        spans = [(int(c["lines"][0]), int(c["lines"][1])) for c in data["changes"] if c.get("id") or c.get("request")]
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise InputError("the map %s is not {\"changes\": [{\"id\", \"lines\": [first, last]}]}: %s" % (map_path, exc)) from None
    return spans


def preserve(original, rewrite, map_path=None):
    """The preservation report for ORIGINAL against REWRITE (dict)."""
    report = {"format": FORMAT, "command": "preserve", "original": str(original), "rewrite": str(rewrite),
              "identical": False, "status": "clean", "findings": [], "notes": [], "claim": CLAIMS["preserve"]}
    try:
        text_a, text_b = read_text(original), read_text(rewrite)
        spans = change_spans(map_path) if map_path else None
    except InputError as exc:
        report.update(status="unreadable", error=str(exc))
        return report
    findings = report["findings"]

    def add(code, severity, detail, line=None):
        findings.append({"code": code, "severity": severity, "line": line, "detail": detail})

    if pathlib.Path(original).read_bytes() == pathlib.Path(rewrite).read_bytes():
        report["identical"] = True
        report["notes"].append("byte-identical: the no-op result; nothing justified was left to change")
        return report
    a, b = Doc(text_a), Doc(text_b)
    if a.fences != b.fences:
        add("fence-changed", "fail", "a fenced code block differs")
    if a.front != b.front:
        add("front-matter-changed", "fail", "the front matter differs")
    if Counter(a.quotes) != Counter(b.quotes):
        add("quote-changed", "fail", "quoted text differs: " + shown(", ".join(sorted(set(a.quotes) ^ set(b.quotes)))))
    if a.tables != b.tables:
        add("table-changed", "fail", "a table row differs")
    if Counter(a.inline) != Counter(b.inline):
        add("inline-code-changed", "fail", "inline code differs: " + shown(", ".join(sorted(set(a.inline) ^ set(b.inline)))))
    if Counter(a.links) != Counter(b.links):
        add("link-changed", "fail", "a link target differs: " + shown(", ".join(sorted(set(a.links) ^ set(b.links)))))
    if Counter(a.paths) != Counter(b.paths):
        add("path-changed", "fail", "a file path differs: " + shown(", ".join(sorted(set(a.paths) ^ set(b.paths)))))
    if [h[0] for h in a.headings] != [h[0] for h in b.headings]:
        add("heading-structure-changed", "fail", "the heading levels or count differ (expected only in revise-structure)")
    elif a.headings != b.headings:
        add("heading-text-changed", "warning", "heading wording differs")
    delta = {name: b.classes[name] - a.classes[name] for name in CLASSES}
    if delta.get("hedge", 0) < 0:
        add("qualifier-dropped", "fail", "%d hedge word(s) fewer (may, some, often ...)" % -delta["hedge"])
    if delta.get("condition", 0) < 0:
        add("condition-dropped", "fail", "%d condition word(s) fewer (if, unless, except, until ...)" % -delta["condition"])
    if delta.get("attribution", 0) < 0:
        add("attribution-dropped", "fail", "%d attribution word(s) fewer (according, says, associated ...)" % -delta["attribution"])
    if delta.get("negation", 0) != 0:
        add("negation-changed", "fail", "negation words changed by %+d (not, no, without ...)" % delta["negation"])
    if delta.get("strength", 0) > 0:
        add("strength-added", "fail", "%d strength word(s) more (will, must, caused, proved ...)" % delta["strength"])
    if delta.get("scope", 0) != 0:
        add("scope-changed", "fail", "scope words changed by %+d (only, first, most, all, every, never ...)" % delta["scope"])
    added_numbers = sorted(b.numbers - a.numbers)
    if added_numbers:
        add("added-number", "fail", "numbers not in the original: " + ", ".join(added_numbers))
    added_names = sorted(n for n in b.names if n.lower() not in a.vocabulary)
    if added_names:
        add("added-name", "fail", "names not in the original: " + ", ".join(added_names))
    dropped_numbers = sorted(a.numbers - b.numbers)
    if dropped_numbers:
        add("number-dropped", "warning", "numbers no longer present (a spelled-out number also shows here): " + ", ".join(dropped_numbers))
    dropped_names = sorted(n for n in a.names if n.lower() not in b.vocabulary)
    if dropped_names:
        add("name-dropped", "warning", "names no longer present: " + ", ".join(dropped_names))
    words_a, words_b = len(a.words), len(b.words)
    if words_b < SHRINK * words_a:
        add("shrink", "warning", "the rewrite has %d words against %d" % (words_b, words_a))
    if spans is not None:
        lines_a, lines_b = text_a.split("\n"), text_b.split("\n")
        for tag, i1, i2, _, _ in difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            low, high = (i1 + 1, i2) if i2 > i1 else (i1, i1 + 1)
            covered = any(first <= high and low <= last for first, last in spans)
            if not covered:
                add("unmapped-change", "fail", "lines %d-%d of the original changed with no finding or request" % (low, high), low)
    report["status"] = "findings" if any(f["severity"] == "fail" for f in findings) else "clean"
    return report


# ---- lint (WD-4, WD-5, WD-6, WD-12, WD-13, WD-14, WD-16, WD-18) -------------------------------------------------------
def infer_doctype(path):
    path = pathlib.Path(path)
    name, folders = path.name.lower(), [p.lower() for p in path.parts[-4:-1]]
    if name.startswith(("changelog", "history", "changes")):
        return "changelog"
    if name.startswith("readme"):
        return "readme"
    if name in ("agents.md", "agents.override.md", "claude.md", "gemini.md", "copilot-instructions.md") or ".cursor" in folders:
        return "instructions"
    if "adr" in folders or "decisions" in folders or name.startswith("adr"):
        return "adr"
    if name.startswith(("release-notes", "release_notes", "releasenotes")):
        return "release-notes"
    if name.startswith(("migrat", "upgrad")):
        return "migration"
    if name.startswith("runbook") or "runbooks" in folders:
        return "runbook"
    return "reference"


def bad_exception(entry, base):
    path = entry.get("path") if isinstance(entry, dict) else None
    return (not text_field(path) or not text_field(entry.get("reason")) or path.endswith(("/", "\\"))
            or any(ch in path for ch in "*?[") or (base / path).is_dir())


def load_roots(path):
    try:
        data = json.loads(read_text(path))
    except ValueError as exc:
        raise InputError("the roots file %s is not JSON: %s" % (path, exc)) from None
    if not isinstance(data, dict) or data.get("format") != ROOTS_FORMAT or not isinstance(data.get("roots"), list):
        raise InputError("the roots file %s is not a %s file" % (path, ROOTS_FORMAT))
    base = pathlib.Path(path).resolve().parent
    for entry in data.get("exceptions", []):
        if bad_exception(entry, base):
            raise InputError("roots: an exception must be one exact file path with a written reason, never a folder or "
                             "pattern: %s" % shown(json.dumps(entry)))
    return base, [r.replace("\\", "/").rstrip("/") for r in data["roots"]], {e["path"].replace("\\", "/") for e in data.get("exceptions", [])}


def lint(paths, doctype=None, mode="delivery", roots=None, rules=None):
    """The lint report for the files (dict). Nothing is edited."""
    report = {"format": FORMAT, "command": "lint", "mode": mode, "status": "clean", "files": [], "findings": [],
              "open_gaps": [], "judgment_only": [], "notes": [], "claim": CLAIMS["lint"]}
    try:
        loaded = load_rules(rules)
        root_config = load_roots(roots) if roots else None
    except (RuleFileError, InputError) as exc:
        report.update(status="unreadable", error=str(exc))
        return report
    if doctype is not None and doctype not in loaded["doctypes"]:
        raise UsageError("unknown document type " + doctype)
    report["judgment_only"] = loaded["judgment"]
    report["rules_sha256"] = loaded["sha256"]
    files = [pathlib.Path(p) for p in paths]
    unreadable = False
    for path in files:
        kind = doctype or infer_doctype(path)
        entry = {"file": str(path), "doctype": kind, "inferred": doctype is None, "status": "clean", "skipped": [], "open_gaps": []}
        report["files"].append(entry)
        if root_config:
            base, root_list, excepted = root_config
            try:
                relative = path.resolve().relative_to(base).as_posix()
            except ValueError:
                relative = None
            inside = relative is not None and (relative in excepted or any(
                relative == r or relative.startswith(r + "/") for r in root_list))
            if not inside:
                report["findings"].append({"code": "outside-roots", "severity": "fail", "file": str(path), "line": None,
                                           "item": "WD-13", "text": "not under a named docs root and not an exact exception"})
        try:
            text = read_text(path)
        except InputError as exc:
            entry.update(status="unreadable", error=str(exc))
            unreadable = True
            continue
        masked = mask(text, code_only(text))
        words = max(len(masked.split()), 1)
        for rule in loaded["rules"]:
            level = rule.level(kind)
            if level == "skip":
                entry["skipped"].append(rule.id)
                continue
            severity = rule.severity
            if level == "relaxed":
                severity = "candidate"
            target = text
            if not rule.in_code:
                target = masked
            hits = list(rule.scan(target))
            if rule.id == "gap-marker":
                gaps = [{"file": str(path), "line": line_of(text, start), "text": found} for start, found in hits]
                entry["open_gaps"] += gaps
                report["open_gaps"] += gaps
            if mode == "draft" and rule.id == "gap-marker":
                continue
            if rule.gate and hits and len(hits) * 1000.0 / words <= rule.gate["per_1000_words"]:
                report["notes"].append("%s: %d hit(s) in %s are under its calibrated gate" % (rule.id, len(hits), path.name))
                continue
            for start, found in hits:
                report["findings"].append({"code": rule.id, "severity": severity, "file": str(path), "line": line_of(text, start),
                                           "item": rule.item, "text": shown(found)})
    for entry in report["files"]:
        if entry["status"] != "unreadable" and any(f["file"] == entry["file"] and f["severity"] == "fail" for f in report["findings"]):
            entry["status"] = "findings"
    if unreadable:
        report["status"] = "unreadable"
    elif any(f["severity"] == "fail" for f in report["findings"]):
        report["status"] = "findings"
    return report


# ---- selflint (WD-8) -------------------------------------------------------------------------------------------------
def markdown_files(root):
    found = []
    for path in sorted(pathlib.Path(root).rglob("*.md")):
        parts = path.relative_to(root).parts
        if any(part.startswith(".") or part in SKIP_DIRS for part in parts[:-1]):
            continue
        if path.is_file():
            found.append(path)
    return found


def selflint(root, rules=None):
    """The self-lint report for every Markdown file under root (dict). Nothing is edited."""
    root = pathlib.Path(root)
    report = {"format": FORMAT, "command": "selflint", "root": str(root), "status": "clean", "files": 0, "unreadable": [],
              "rules": {}, "exclusions": {}, "dead_exclusions": [], "findings": [], "notes": [], "claim": CLAIMS["selflint"]}
    try:
        loaded = load_rules(rules)
    except RuleFileError as exc:
        report.update(status="unreadable", error=str(exc))
        return report
    config = loaded["selflint"]
    active = set(config.get("exclusions", {}))

    def exclusion_on(name):
        return name in active

    counts = {r.id: {"naive": 0, "kept": 0, "gated": 0, "ceiling": config.get("ceilings", {}).get(r.id, 0)} for r in loaded["rules"]}
    removed = {name: 0 for name in EXCLUSIONS if name in active}
    gated_hits = {r.id: [] for r in loaded["rules"]}
    for path in markdown_files(root):
        report["files"] += 1
        try:
            text = read_text(path)
        except InputError:
            report["unreadable"].append(str(path))
            continue
        relative = path.relative_to(root)
        shipped = not any(part in NOT_SHIPPED for part in relative.parts[:-1])
        kind = infer_doctype(relative)
        regions = code_only(text)
        for rule in loaded["rules"]:
            skipped = rule.level(kind) == "skip"
            for start, found in rule.scan(text):
                counts[rule.id]["naive"] += 1
                # Each hit is credited to the first exclusion that removes it; a removed hit is never counted kept.
                reason = None
                if exclusion_on("not-shipped"):
                    if not shipped:
                        reason = "not-shipped"
                if exclusion_on("doctype-skip"):
                    if reason is None and skipped:
                        reason = "doctype-skip"
                if exclusion_on("code"):
                    if reason is None and inside(start, regions) and not rule.in_code:
                        reason = "code"
                if reason:
                    removed[reason] += 1
                    continue
                counts[rule.id]["kept"] += 1
                # Only the exclusions remove hits: a relaxed level makes a kept hit a candidate, never a gated one.
                if rule.severity == "fail" and rule.level(kind) != "relaxed":
                    counts[rule.id]["gated"] += 1
                    gated_hits[rule.id].append({"code": rule.id, "severity": "fail", "file": str(path),
                                                "line": line_of(text, start), "item": rule.item, "text": shown(found)})
    report["rules"] = counts
    report["exclusions"] = removed
    report["dead_exclusions"] = sorted(name for name, hits in removed.items() if hits == 0)
    for rule_id, row in counts.items():
        if row["gated"] > row["ceiling"]:
            report["findings"] += gated_hits[rule_id]
        elif row["gated"] < row["ceiling"]:
            report["notes"].append("the ceiling for %s can move down to %d" % (rule_id, row["gated"]))
    if report["unreadable"]:
        report["status"] = "unreadable"
    elif report["findings"]:
        report["status"] = "findings"
    return report


# ---- inventory and series (DS-5) -------------------------------------------------------------------------------------
NUMBERED = re.compile(r"^(\d+)(?=[-_.])")
INVENTORY_CLAIM = ("compares file names only: it reads code spans and link targets (not fenced blocks or bare names in "
                   "prose), and a clean result does not show that what a document says about a listed item is accurate")
SERIES_CLAIM = ("compares the numbers in file names with the links between them: a clean result does not show that a "
                "document makes sense read in order, and links to unnumbered documents are not read")


def _inventory_token(token, doc_dir, folder):
    """The path a code span or link target names, relative to the folder, or None when it names something else. A bare
    name is the folder's own; a path is read from the document's folder, as a link is."""
    token = re.split(r"[#?]", token.strip().strip("<>"), maxsplit=1)[0]
    token = token[2:] if token.startswith("./") else token
    if not token or token.startswith(("/", "mailto:")) or re.search(r"\s|://|[*<>{}\\]", token):
        return None
    if "/" not in token:
        return token
    resolved = (doc_dir / token).resolve()
    if folder not in resolved.parents:
        return None
    return pathlib.PurePath(os.path.relpath(resolved, folder)).as_posix()


def inventory(doc, folder, glob="*", recursive=False):
    """DS-5: a document that lists a folder's files, checked both ways. Nothing is edited."""
    report = {"format": FORMAT, "command": "inventory", "doc": str(doc), "folder": str(folder), "glob": glob,
              "recursive": bool(recursive), "status": "clean", "existing": 0, "listed": 0, "findings": [],
              "claim": INVENTORY_CLAIM}
    try:
        text = read_text(doc)
    except InputError as exc:
        report.update(status="unreadable", error=str(exc))
        return report
    folder = pathlib.Path(folder).resolve()
    doc_dir = pathlib.Path(doc).resolve().parent

    def owed(rel):
        return fnmatch.fnmatchcase(pathlib.PurePosixPath(rel).name, glob) and (recursive or "/" not in rel)

    found = folder.rglob("*") if recursive else folder.iterdir()
    existing = set()
    for path in found:
        rel = path.relative_to(folder).as_posix()
        if path.is_file() and not any(p.startswith(".") or p in SKIP_DIRS for p in rel.split("/")) and owed(rel):
            existing.add(rel)
    tokens = [text[start:end].strip("`").strip() for start, end, kind in code_regions(text) if kind == "inline"]
    tokens += LINK_TARGET.findall(mask(text, code_regions(text)))
    named = {_inventory_token(token, doc_dir, folder) for token in tokens}
    listed = {rel for rel in named if rel and owed(rel)}
    unlisted, stale = sorted(existing - listed), sorted(listed - existing)
    for item in unlisted:
        report["findings"].append({"code": "inventory-unlisted", "item": item,
                                   "detail": "the folder holds it, but the document does not list it"})
    for item in stale:
        report["findings"].append({"code": "inventory-stale", "item": item,
                                   "detail": "the document lists it, but the folder does not hold it"})
    report.update(existing=len(existing), listed=len(listed), status="findings" if report["findings"] else "clean")
    return report


def series(folder, glob="*.md"):
    """DS-5: in a numbered series read in order, a document links only to earlier ones. Nothing is edited."""
    folder = pathlib.Path(folder).resolve()
    report = {"format": FORMAT, "command": "series", "folder": str(folder), "glob": glob, "status": "clean",
              "documents": 0, "unreadable": [], "findings": [], "claim": SERIES_CLAIM}
    numbered = {}
    for path in sorted(folder.iterdir()):
        match = NUMBERED.match(path.name)
        if path.is_file() and match and fnmatch.fnmatchcase(path.name, glob):
            numbered[path.name] = int(match[1])
    report["documents"] = len(numbered)
    seen = set()
    for name, own in numbered.items():
        try:
            text = read_text(folder / name)
        except InputError:
            report["unreadable"].append(name)
            continue
        masked = mask(text, code_regions(text))
        for target in LINK_TARGET.findall(masked) + REF_DEF.findall(masked):
            target = re.split(r"[#?]", target, maxsplit=1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            linked = (folder / target).resolve()
            number = numbered.get(linked.name) if linked.parent == folder else None
            later = number is not None and number >= own
            if later:
                if (name, linked.name) not in seen:
                    seen.add((name, linked.name))
                    report["findings"].append({"code": "series-forward-link", "item": "%s -> %s" % (name, linked.name),
                                               "detail": "a numbered document links only to earlier ones"})
    report["status"] = "unreadable" if report["unreadable"] else "findings" if report["findings"] else "clean"
    return report


# ---- command line ----------------------------------------------------------------------------------------------------
def exit_code(report):
    return {"clean": 0, "findings": 1}.get(report.get("status"), 2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("preserve", help="compare a rewrite with its original")
    one.add_argument("original")
    one.add_argument("rewrite")
    one.add_argument("--map", help="JSON mapping each changed span to a finding or request")
    two = sub.add_parser("lint", help="lint prose files by document type")
    two.add_argument("files", nargs="+")
    two.add_argument("--type", dest="doctype")
    two.add_argument("--mode", choices=("draft", "delivery"), default="delivery")
    two.add_argument("--roots", help="a westack-docs-roots-1 file")
    two.add_argument("--rules", help="a rules file (default: references/rules.json)")
    three = sub.add_parser("selflint", help="lint every Markdown file under ROOT")
    three.add_argument("root")
    three.add_argument("--rules")
    four = sub.add_parser("inventory", help="check a document's list of a folder's files both ways")
    four.add_argument("doc")
    four.add_argument("folder")
    four.add_argument("--glob", default="*", help="which files the document lists (default: every file)")
    four.add_argument("--recursive", action="store_true", help="also read the folder's subfolders")
    five = sub.add_parser("series", help="check that a numbered series links only to earlier documents")
    five.add_argument("folder")
    five.add_argument("--glob", default="*.md")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    try:
        if args.command == "preserve":
            report = preserve(args.original, args.rewrite, map_path=args.map)
        elif args.command == "lint":
            report = lint(args.files, doctype=args.doctype, mode=args.mode, roots=args.roots, rules=args.rules)
        elif args.command in ("inventory", "series"):
            if not pathlib.Path(args.folder).is_dir():
                sys.stderr.write("%s: %s is not a folder\n" % (args.command, args.folder))
                return 64
            report = (inventory(args.doc, args.folder, args.glob, args.recursive) if args.command == "inventory"
                      else series(args.folder, args.glob))
        else:
            if not pathlib.Path(args.root).is_dir():
                sys.stderr.write("selflint: %s is not a folder\n" % args.root)
                return 64
            report = selflint(args.root, rules=args.rules)
    except UsageError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 64
    sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
