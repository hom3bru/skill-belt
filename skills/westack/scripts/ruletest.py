"""westack ruletest: check that every guard rule agrees with its own examples, as the rule file loads.

  python ruletest.py RULES.json [--matrix CAPABILITIES.json] [--corpus PROBES.json [--against OLD.json]]

RULES.json is {"rules": [{"id": "no-force-push", "effect": "deny", "kind": "regex", "pattern": "git push .*--force",
"must_match": "git push --force origin main", "must_not_match": "git push origin main", "unresolved":
"git push --force $BRANCH", "alternate": "git push origin main --force", "twin": "git push --force origin main"}]}.
`effect` is allow, deny or ask. `kind` is regex (re.search, the default), prefix (the command equals the pattern, or
starts with it and a space) or glob (the whole command, case-sensitive). `must_match` and `must_not_match` are a
command or a list of commands, and every rule needs at least one of each: a rule that matches nothing protects
nothing, and a rule with no counter-example has never been tried against over-reach.

A deny or ask rule also needs three more classes, each a command or a list of commands the rule must match:
`unresolved` (the operand missing or unresolved, so a deny cannot go quiet), `alternate` (another spelling of the
target) and `twin` (one command for each must_not_match example, in the same order: the smallest change that makes
that counter-example match, so it is a counter-example for the reason intended). An allow rule needs only the first
two; any of the three that it carries is checked.

Three outcomes stay apart. A rule that matched its example, one that did not, and one that failed to evaluate (its
matcher raised) are different: the last is `errored`, its id is listed under `errored` beside the verdict, and it is
never read as "did not match". A prefix selector cannot fail to evaluate; a regex or glob can, so keep the selector
an exact or prefix match where you can. Where rules are combined (below), an errored allow or ask rule grants
nothing and an errored deny still denies.

A fourth outcome covers a newer vocabulary. A rule that names an effect, a kind, a tool class or a path class this
checker does not know is `unevaluated`: its id is listed under `unevaluated` beside `errored`, it is never read as
"did not match", the file fails, and a probe corpus is not decided at all while it stands. A reader that skipped the
line instead would let the rule's deny stop applying; failing here means a deny cannot fall silent after a vocabulary
change. A malformed value (a number, a blank, a missing field) is simply failed.

Optional fields. `layer` names where a rule came from (default "default") and is repeated in decisions. `applies_to`
(tool classes) and `path_classes` are checked against the closed lists in the host matrix (`rule_vocabulary` in
hosts/capabilities.json, or --matrix FILE); an unknown name is a load error. A file that uses them carries
`"matrix_revision": N`, the revision it was checked against: an older stamp reports `stale` and is not a pass. Those
names are checked, not matched: matching compares commands only. A file without them needs no matrix.

Probe corpus. --corpus PROBES.json ({"probes": ["git push --force origin main", ...]}) decides each probe by
strictest-first combination (deny beats ask beats allow, whatever the order; a probe no rule matches is denied by
default). Each decision record holds the probe and its SHA-256, the rules file's SHA-256, the verdict, the deciding
rules (id, layer, effect), any weaker rule it overrode and the ids that errored; an empty `decided_by` is the default
deny. replay(record, path) decides the same probe again and says `same`, `different` or `rules-changed`. Each rule is
tagged `matched` (it decided at least one probe), `shadowed` (it matched, but a stricter rule always decided) or
`never-reached` (no probe matched it). --against OLD.json compares the new file with the old one over the corpus:
`newly_allowed` probes, `loosened` ones (deny to ask), `newly_errored` rule ids, and per-rule `match_set_changes`,
because a deny narrowed to a smaller set still says deny on every probe it still covers.

It runs nothing and writes nothing: it compares each pattern with the example strings and the corpus. It does not
judge a command line, parse a shell, model a host's own rule order or show that the host enforces the rules, so a
pass means the rules agree with their own examples and is not a sandbox. A clean diff covers only the probes in the
corpus: it is inconclusive, never proof. It cannot tell that an alternate is a different spelling or a twin is
minimal; a reviewer reads those. Probe the guard itself separately (an unlisted host must fail, a hook gate must fire).

Exit 0 every rule agrees with its examples (and any diff has no regression); 1 a rule disagrees, errored, is
unevaluated, lacks an example, is not valid or is stale, or a diff found a regression; 2 a file cannot be read, is not the shape above or
holds nothing to check (nothing to check is never a pass); 64 usage. Standard library only.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys

FORMAT = "westack-ruletest-1"
EFFECTS = ("allow", "deny", "ask")
RANK = {"allow": 0, "ask": 1, "deny": 2}
KINDS = ("regex", "prefix", "glob")
EXTRA_CLASSES = (("unresolved", "an input with the operand missing or unresolved"),
                 ("alternate", "an alternate spelling of the target"),
                 ("twin", "a minimal positive twin of a must_not_match example"))
EXTRA_EFFECTS = ("deny", "ask")  # the effects that must carry every extra class
VOCABULARY_FIELDS = (("applies_to", "tools", "unknown-tool"), ("path_classes", "path_classes", "unknown-path-class"))
UNKNOWN_NAME_CODES = tuple(code for _, _, code in VOCABULARY_FIELDS)  # OC-9: a name the host matrix lacks
LIMIT = 1024 * 1024
TEXT_LIMIT = 1000
CLAIM = ("runs nothing and writes nothing; compares each rule with its own examples only, so a pass is not a sandbox "
         "and does not show the host enforces the rules; it cannot tell that an alternate is a different spelling "
         "or a twin is minimal")
DIFF_CLAIM = ("a clean diff is inconclusive: it covers only the probes in the corpus, models strictest-first "
              "combination (not a host's own rule order) and shows nothing about what the host enforces")


class RuleFileError(ValueError):
    """The file cannot be read as a rules file; nothing was checked."""


class Unevaluable(Exception):
    """A matcher raised while evaluating a command: the rule failed to evaluate, which is not "did not match"."""


def matcher(kind, pattern):
    """A function from a command to True or False. Raises re.error for a regex that does not compile."""
    if kind == "regex":
        search = re.compile(pattern).search
        return lambda command: search(command) is not None
    if kind == "prefix":
        return lambda command: command == pattern or command.startswith(pattern + " ")
    return lambda command: fnmatch.fnmatchcase(command, pattern)


def guarded(function):
    """The same function, but any exception it raises becomes Unevaluable."""
    def run(command):
        try:
            return function(command)
        except Exception as exc:  # re and fnmatch raise only on exotic input; whatever raises is "errored", never silence
            raise Unevaluable(type(exc).__name__ + ": " + str(exc)) from None
    return run


def examples(value):
    """The list of example commands, or None when the field is not a command or a non-empty list of commands."""
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list) or not items:
        return None
    if not all(isinstance(i, str) and i.strip() and len(i) <= TEXT_LIMIT for i in items):
        return None
    return items


def shown(text):
    return repr(text if len(text) <= 80 else text[:77] + "...")


def sha256(text):
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def vocabulary_problems(rule, vocabulary, problem):
    """Report any tool class or path class of a rule that is not in the closed lists of the host matrix."""
    for field, key, code in VOCABULARY_FIELDS:
        if field not in rule:
            continue
        names = rule[field]
        if not isinstance(names, list) or not names or not all(isinstance(n, str) and n.strip() for n in names):
            problem("bad-" + field.replace("_", "-"), field + " is a non-empty list of names from the host matrix")
            continue
        allowed = vocabulary[key]
        for name in names:
            if name not in allowed:
                problem(code, "the name " + shown(name) + " is not in the host matrix (" + ", ".join(allowed) + ")")


def check_rule(rule, seen, vocabulary=None):
    """The report for one entry of the file: its id, status and problems [{code, detail}]."""
    problems = []
    errored = False

    def problem(code, detail):
        problems.append({"code": code, "detail": detail})

    if not isinstance(rule, dict):
        problem("not-an-object", "a rule is an object with id, effect, pattern, must_match and must_not_match")
        return {"id": None, "status": "failed", "problems": problems}
    rule_id = rule.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        problem("no-id", "a rule needs a plain-text id")
    elif rule_id in seen:
        problem("duplicate-id", "the id " + shown(rule_id) + " is used twice")
    else:
        seen.add(rule_id)
    effect, kind, pattern = rule.get("effect"), rule.get("kind", "regex"), rule.get("pattern")
    foreign = []  # OC-9: names from a vocabulary this checker does not know, so the rule is unevaluated
    if effect not in EFFECTS:
        problem("bad-effect", "effect must be one of " + ", ".join(EFFECTS))
        if isinstance(effect, str) and effect.strip():
            foreign.append("effect")
    if kind not in KINDS:
        problem("bad-kind", "kind must be one of " + ", ".join(KINDS))
        if isinstance(kind, str) and kind.strip():
            foreign.append("kind")
    layer = rule.get("layer", "default")
    if not isinstance(layer, str) or not layer.strip() or len(layer) > 64:
        problem("bad-layer", "layer is a plain-text name of at most 64 characters")
    if vocabulary is not None:
        vocabulary_problems(rule, vocabulary, problem)
    hit = None
    if not isinstance(pattern, str) or not pattern.strip() or len(pattern) > TEXT_LIMIT:
        problem("bad-pattern", "pattern must be text, not blank and at most %d characters" % TEXT_LIMIT)
    elif kind in KINDS:
        try:
            hit = guarded(matcher(kind, pattern))
        except re.error:
            problem("bad-pattern", "the regular expression does not compile: " + shown(pattern))
        except (RecursionError, OverflowError):
            problem("bad-pattern", "the regular expression is too deeply nested: " + shown(pattern))
    must, must_not = examples(rule.get("must_match")), examples(rule.get("must_not_match"))
    for name, got in (("must_match", must), ("must_not_match", must_not)):
        good = got is not None
        if not good:
            problem("no-" + name.replace("_", "-"), name + " needs a command, or a list of commands, that is not blank")
    if hit is not None:
        try:
            for example in must or ():
                if not hit(example):
                    problem("must-match-failed", "the rule does not match " + shown(example) + ", which it must match")
            for example in must_not or ():
                if hit(example):
                    problem("must-not-match-matched", "the rule matches " + shown(example) + ", which it must not match")
        except Unevaluable as exc:
            errored = True
            problem("evaluation-error", "the rule failed to evaluate, which is not the same as not matching: " + str(exc))
    for name, meaning in EXTRA_CLASSES:
        got = examples(rule.get(name))
        if got is None:
            if name in rule or effect in EXTRA_EFFECTS:
                problem("no-%s-example" % name, name + " needs " + meaning + ", as a command or a list of commands "
                        "that is not blank")
            continue
        if name == "twin" and must_not is not None and len(got) != len(must_not):
            problem("twin-count", "twin needs one command for each must_not_match example (%d), found %d"
                    % (len(must_not), len(got)))
        try:
            for sample in got if hit is not None and not errored else ():
                if not hit(sample):
                    problem(name + "-failed", "the rule does not match " + shown(sample) + ", " + meaning
                            + ", which it must match")
        except Unevaluable as exc:
            errored = True
            problem("evaluation-error", "the rule failed to evaluate, which is not the same as not matching: " + str(exc))
    foreign += [p["code"] for p in problems if p["code"] in UNKNOWN_NAME_CODES]
    unevaluated = bool(foreign)
    return {"id": rule_id if isinstance(rule_id, str) else None, "effect": effect if isinstance(effect, str) else None,
            "kind": kind if isinstance(kind, str) else None,
            "status": "errored" if errored else "unevaluated" if unevaluated else "failed" if problems else "passed",
            "problems": problems}


def needs_vocabulary(document):
    """True when the file names tools or path classes or carries a matrix revision, so the host matrix is needed."""
    rules = document.get("rules") if isinstance(document, dict) else None
    return isinstance(document, dict) and ("matrix_revision" in document or any(
        isinstance(r, dict) and any(field in r for field, _, _ in VOCABULARY_FIELDS)
        for r in (rules if isinstance(rules, list) else ())))


def stamp_problems(document, vocabulary):
    """The matrix status of a file and its file-level problems [{code, detail}]."""
    stamp, current = document.get("matrix_revision"), vocabulary["revision"]
    if "matrix_revision" not in document:
        return "unstamped", [{"code": "no-matrix-revision", "detail": "the file names tools or path classes, so it "
                              "carries the matrix revision it was checked against (now %d)" % current}]
    if isinstance(stamp, bool) or not isinstance(stamp, int) or stamp < 1:
        return "bad", [{"code": "bad-matrix-revision", "detail": "matrix_revision is a whole number from 1"}]
    if stamp > current:
        return "ahead", [{"code": "bad-matrix-revision", "detail": "the stamp %d is newer than the matrix (%d)"
                          % (stamp, current)}]
    elif stamp < current:
        return "stale", [{"code": "stale-matrix-revision", "detail": "stamped %d, the matrix is now %d: check the "
                          "names again and restamp; a stale stamp is not a pass" % (stamp, current)}]
    return "current", []


def check(document, vocabulary=None):
    """The report for a parsed rules file. Raises RuleFileError when there is nothing to check."""
    rules = document.get("rules") if isinstance(document, dict) else None
    if not isinstance(rules, list) or not rules:
        raise RuleFileError('a rules file is {"rules": [...]} with at least one rule; a file with no rules checks nothing')
    matrix, file_problems = {"status": "not-used"}, []
    if needs_vocabulary(document):
        if vocabulary is None:
            raise RuleFileError("this file names tools, path classes or a matrix revision, so it needs the host "
                                "matrix (rule_vocabulary); none was given")
        status, file_problems = stamp_problems(document, vocabulary)
        matrix = {"status": status, "revision": vocabulary["revision"], "file_revision": document.get("matrix_revision")}
    seen = set()
    results = [dict(check_rule(rule, seen, vocabulary), index=index) for index, rule in enumerate(rules)]
    errored = [r["id"] or "#%d" % (r["index"] + 1) for r in results if r["status"] == "errored"]
    unevaluated = [r["id"] or "#%d" % (r["index"] + 1) for r in results if r["status"] == "unevaluated"]
    failed = any(r["status"] != "passed" for r in results) or any(p["code"] != "stale-matrix-revision" for p in file_problems)
    stale = not failed and bool(file_problems)
    return {"format": FORMAT, "status": "failed" if failed else "stale" if stale else "passed",
            "exit_code": 1 if failed or stale else 0, "checked": len(results), "rules": results, "errored": errored,
            "unevaluated": unevaluated, "matrix": matrix, "file_problems": file_problems, "claim": CLAIM}


def prepare(document):
    """[{id, effect, layer, hit}] for each rule of a parsed file. Raises RuleFileError naming a rule that cannot be used."""
    rules = document.get("rules") if isinstance(document, dict) else None
    if not (isinstance(rules, list) and rules):
        raise RuleFileError("a rules file is {\"rules\": [...]} with at least one rule")
    prepared, seen = [], set()
    for index, rule in enumerate(rules):
        where = "rule %d" % (index + 1)
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str) or not rule["id"].strip():
            raise RuleFileError(where + " is not an object with a plain-text id; check the file alone first")
        where += " (" + shown(rule["id"]) + ")"
        layer = rule.get("layer", "default")
        pattern, kind = rule.get("pattern"), rule.get("kind", "regex")
        if (rule["id"] in seen or rule.get("effect") not in EFFECTS or kind not in KINDS or not isinstance(layer, str)
                or not layer.strip() or not isinstance(pattern, str) or not pattern.strip()
                or len(pattern) > TEXT_LIMIT):
            raise RuleFileError(where + " has a repeated id or an unusable effect, kind, layer or pattern; check the "
                                "file alone first")
        seen.add(rule["id"])
        try:
            hit = matcher(kind, pattern)
        except (re.error, RecursionError, OverflowError):
            raise RuleFileError(where + " has a pattern that does not compile; check the file alone first")
        prepared.append({"id": rule["id"], "effect": rule["effect"], "layer": layer, "hit": hit})
    return prepared


def brief(rule, **more):
    return dict({"id": rule["id"], "layer": rule["layer"], "effect": rule["effect"]}, **more)


def decide(prepared, command, rules_sha256=None):
    """The decision record for one command: strictest effect wins, a command no rule matches is denied by default.

    A rule whose matcher raises is errored: an errored deny still denies, an errored allow or ask grants nothing."""
    matched, errored = [], []
    for rule in prepared:
        try:
            hit = rule["hit"](command)
        except Exception:  # the matcher failed to evaluate: kept apart from "did not match"
            errored.append(rule["id"])
            hit = rule["effect"] == "deny"
        if hit:
            matched.append(rule)
    top = max((RANK[r["effect"]] for r in matched), default=None)
    decided = [r for r in matched if RANK[r["effect"]] == top]
    return {"probe": command, "input_sha256": sha256(command), "rules_sha256": rules_sha256,
            "verdict": "deny" if not matched else decided[0]["effect"], "default": not matched,
            "decided_by": [brief(r, errored=True) if r["id"] in errored else brief(r) for r in decided],
            "overridden": [brief(r) for r in matched if r not in decided], "errored": errored}


def reach(prepared, decisions):
    """{rule id: matched | shadowed | never-reached} over a probe corpus."""
    decided = {d["id"] for record in decisions for d in record["decided_by"]}
    overridden = {d["id"] for record in decisions for d in record["overridden"]}
    return {r["id"]: "matched" if r["id"] in decided else "shadowed" if r["id"] in overridden else "never-reached"
            for r in prepared}


def match_sets(decisions):
    """{rule id: the probes it matched, whether or not it decided them}."""
    found = {}
    for record in decisions:
        for d in record["decided_by"] + record["overridden"]:
            found.setdefault(d["id"], set()).add(record["probe"])
    return found


def diff(new, old, probes, new_sha=None, old_sha=None):
    """Run a probe corpus through two prepared rule sets and report what got looser, what newly errors and what moved."""
    now = [decide(new, p, new_sha) for p in probes]
    before = [decide(old, p, old_sha) for p in probes]
    newly_allowed, loosened = [], []
    for n, o in zip(now, before):
        if RANK[n["verdict"]] < RANK[o["verdict"]]:
            item = {"probe": n["probe"], "old": o["verdict"], "new": n["verdict"], "old_decided_by": o["decided_by"],
                    "new_decided_by": n["decided_by"]}
            (newly_allowed if n["verdict"] == "allow" else loosened).append(item)
    newly_errored = sorted({i for r in now for i in r["errored"]} - {i for r in before for i in r["errored"]})
    new_sets, old_sets, changes = match_sets(now), match_sets(before), []
    for rule_id in sorted({r["id"] for r in new} & {r["id"] for r in old}):
        gained = sorted(new_sets.get(rule_id, set()) - old_sets.get(rule_id, set()))
        lost = sorted(old_sets.get(rule_id, set()) - new_sets.get(rule_id, set()))
        if gained or lost:
            changes.append({"id": rule_id, "gained": gained, "lost": lost})
    added = sorted({r["id"] for r in new} - {r["id"] for r in old})
    removed = sorted({r["id"] for r in old} - {r["id"] for r in new})
    regressed = bool(newly_allowed or loosened or newly_errored)
    return {"status": "regressed" if regressed else "changed" if changes or added or removed else "unchanged",
            "corpus_size": len(probes), "newly_allowed": newly_allowed, "loosened": loosened,
            "newly_errored": newly_errored, "match_set_changes": changes, "rules_added": added, "rules_removed": removed,
            "claim": DIFF_CLAIM}


def replay(record, path):
    """Decide a record's probe again against the file at `path`: same, different, or rules-changed (the file's
    SHA-256 is not the one the record names, so the old verdict cannot be reproduced from this file)."""
    document, rules_sha = load_with_hash(path)
    again = decide(prepare(document), record["probe"], rules_sha)
    if rules_sha != record["rules_sha256"]:
        status = "rules-changed"
    else:
        status = "same" if (again["verdict"], again["decided_by"]) == (record["verdict"], record["decided_by"]) \
            else "different"
    return {"status": status, "verdict": again["verdict"], "decided_by": again["decided_by"], "rules_sha256": rules_sha}


def read(path):
    """The bytes of a file of at most LIMIT bytes. Raises RuleFileError."""
    try:
        with open(path, "rb") as stream:
            data = stream.read(LIMIT + 1)
    except OSError as exc:
        raise RuleFileError("cannot read " + str(path) + ": " + str(exc))
    if len(data) > LIMIT:
        raise RuleFileError("the file is larger than %d bytes: %s" % (LIMIT, path))
    return data


def parse(data, what):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise RuleFileError("the " + what + " is not valid JSON: " + str(exc))


def load(path):
    """The parsed JSON of a rules file (a leading byte-order mark is allowed). Raises RuleFileError."""
    return parse(read(path), "rules file")


def load_with_hash(path):
    """(parsed rules file, SHA-256 of its bytes). Raises RuleFileError."""
    data = read(path)
    return parse(data, "rules file"), hashlib.sha256(data).hexdigest()


def load_corpus(path):
    """The list of probe commands of a corpus file. Raises RuleFileError; an empty corpus checks nothing."""
    document = parse(read(path), "probe corpus")
    probes = document.get("probes") if isinstance(document, dict) else None
    if examples(probes) is None:
        raise RuleFileError('a probe corpus is {"probes": [...]} with at least one command, none blank or over %d '
                            "characters; an empty corpus checks nothing" % TEXT_LIMIT)
    return probes


def load_vocabulary(path):
    """The closed lists of the host matrix. Raises RuleFileError."""
    document = parse(read(path), "host matrix")
    found = document.get("rule_vocabulary") if isinstance(document, dict) else None
    revision = found.get("revision") if isinstance(found, dict) else None
    if (not isinstance(revision, int) or isinstance(revision, bool) or revision < 1
            or any(examples(found.get(key)) is None for key in ("tools", "path_classes"))):
        raise RuleFileError("the host matrix " + str(path) + " has no usable rule_vocabulary (a revision from 1 and "
                            "non-empty tools and path_classes lists)")
    return found


def default_matrix():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hosts", "capabilities.json")


def run(args):
    document, rules_sha = load_with_hash(args.rules)
    vocabulary = load_vocabulary(args.matrix or default_matrix()) if needs_vocabulary(document) else None
    report = check(document, vocabulary)
    if not args.corpus:
        return report
    probes = load_corpus(args.corpus)
    old = prepare(load(args.against)) if args.against else None
    try:
        new = prepare(document)
    except RuleFileError as exc:
        report["corpus"] = {"skipped": str(exc)}
        return report
    decisions = [decide(new, p, rules_sha) for p in probes]
    report["corpus"] = {"size": len(probes), "decisions": decisions, "reach": reach(new, decisions)}
    if old is not None:
        report["diff"] = diff(new, old, probes, rules_sha, hashlib.sha256(read(args.against)).hexdigest())
        if report["diff"]["status"] == "regressed":
            report["exit_code"] = 1
            if report["status"] == "passed":
                report["status"] = "regressed"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rules", help="the JSON rules file")
    parser.add_argument("--matrix", help="the host matrix holding rule_vocabulary (default: hosts/capabilities.json)")
    parser.add_argument("--corpus", help="a JSON probe corpus: decide each probe and tag each rule's reach")
    parser.add_argument("--against", help="an older rules file: diff it with the new one over the corpus")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    if args.against and not args.corpus:
        sys.stderr.write("ruletest: --against needs --corpus\n")
        return 64
    try:
        report = run(args)
    except RuleFileError as exc:
        report = {"format": FORMAT, "status": "blocked", "exit_code": 2, "reason": str(exc), "claim": CLAIM}
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
