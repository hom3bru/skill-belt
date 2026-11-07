"""P2 guards group (1.0.0-alpha.5, unreleased): the record writer (HD-40), the host matrix fields (CM-11, CM-16,
CM-17, CM-19, CM-20, CM-21) and the pinned wording of the P2 text rules.

HD-40: `write_new` writes a record version to a temporary file in the same folder, flushes it and links it to its
final name. Every check runs the real function on a real folder and each has a broken copy: the pre-change function
(a half-written file at the final name) and a copy whose last step replaces instead of linking.

The matrix fields are data, so the checks read capabilities.json and run the same schema function over a doctored
copy that must fail. No host fact is asserted here: a field without a receipt stays `unknown`."""
import copy
import errno
import json
import os
import pathlib
import re
import tempfile
import types
import unittest
from unittest import mock

import test_westack as fixtures

ROOT = fixtures.ROOT
EVIDENCE = ROOT / "scripts" / "evidence.py"


def text(relative):
    return (ROOT / relative).read_bytes().decode("utf-8")


def flat(relative):
    return re.sub(r"\s+", " ", text(relative))


def load_evidence(source=None):
    """The real evidence.py, or a mutated copy of its source, as a module of its own."""
    module = types.ModuleType("guards_p2_evidence")
    module.__file__ = str(EVIDENCE)
    exec(compile(text("scripts/evidence.py") if source is None else source, str(EVIDENCE), "exec"), module.__dict__)
    return module


def mutated(old, new):
    source = text("scripts/evidence.py")
    if source.count(old) != 1:
        raise AssertionError("a broken copy needs exactly one occurrence of: " + old)
    return load_evidence(source.replace(old, new))


# The function as it stood before HD-40: it creates the final name first and then serialises into it.
OLD_WRITE_NEW = '''
def write_new(path, data):
    path = pathlib.Path(path)
    with path.open("x", encoding="utf-8", newline="\\n") as stream:
        stream.write(json.dumps(data, indent=2) + "\\n")
'''


class Unserialisable(dict):
    """A record that fails part-way through serialisation: the write failure injected into every writer."""

    def items(self):
        raise OSError(errno.ENOSPC, "No space left on device")


class WriteNewBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="westack-writenew-")
        self.folder = pathlib.Path(self.temp.name)
        self.final = self.folder / "task.0001.json"

    def tearDown(self):
        self.temp.cleanup()

    def listing(self):
        return sorted(p.name for p in self.folder.iterdir())


class AtomicRecordWrite(WriteNewBase):
    """HD-40: the final name never holds a half-written file, and an existing version is never replaced."""
    module = load_evidence()

    def test_a_record_is_written_whole_and_no_temporary_file_is_left(self):
        self.module.write_new(self.final, {"a": 1, "b": [2, 3]})
        self.assertEqual(json.loads(self.final.read_bytes().decode("utf-8")), {"a": 1, "b": [2, 3]})
        self.assertTrue(self.final.read_bytes().endswith(b"\n") and b"\r" not in self.final.read_bytes())
        self.assertEqual(self.listing(), ["task.0001.json"])

    def test_a_failure_while_writing_leaves_nothing_at_the_final_name(self):
        with self.assertRaises(OSError):
            self.module.write_new(self.final, Unserialisable(a=1))
        self.assertEqual(self.listing(), [], "no final file and no temporary file")

    def test_a_failed_flush_leaves_nothing_at_the_final_name(self):
        with mock.patch.object(self.module.os, "fsync", side_effect=OSError(errno.ENOSPC, "disk full")):
            with self.assertRaises(OSError):
                self.module.write_new(self.final, {"a": 1})
        self.assertEqual(self.listing(), [])

    def test_an_existing_version_is_never_replaced_and_nothing_else_is_left(self):
        self.final.write_bytes(b'{"old": true}\n')
        with self.assertRaises(FileExistsError):
            self.module.write_new(self.final, {"new": True})
        self.assertEqual(self.final.read_bytes(), b'{"old": true}\n')
        self.assertEqual(self.listing(), ["task.0001.json"])

    def test_a_filesystem_without_hard_links_falls_back_to_exclusive_create(self):
        no_links = OSError(errno.EPERM, "hard links are not supported here")
        with mock.patch.object(self.module.os, "link", side_effect=no_links):
            self.module.write_new(self.final, {"a": 1})
            self.assertEqual(json.loads(self.final.read_bytes().decode("utf-8")), {"a": 1})
            self.assertEqual(self.listing(), ["task.0001.json"])
            with self.assertRaises(FileExistsError):
                self.module.write_new(self.final, {"a": 2})
            self.assertEqual(json.loads(self.final.read_bytes().decode("utf-8")), {"a": 1})

    def test_the_fallback_removes_the_partial_file_it_made_when_the_write_fails(self):
        no_links = OSError(errno.EPERM, "hard links are not supported here")
        with mock.patch.object(self.module.os, "link", side_effect=no_links):
            with mock.patch.object(self.module.json, "dumps", side_effect=OSError(errno.EIO, "write failed")):
                with self.assertRaises(OSError):
                    self.module.write_new(self.final, {"a": 1})
        self.assertEqual(self.listing(), [])

    def test_the_temporary_name_cannot_be_a_numbered_version(self):
        seen = []
        real = self.module.os.link

        def spy(source, target, *args, **kwargs):
            seen.append(pathlib.Path(source).name)
            return real(source, target, *args, **kwargs)

        with mock.patch.object(self.module.os, "link", side_effect=spy):
            self.module.write_new(self.final, {"a": 1})
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].startswith(".") and seen[0].endswith(".tmp"), seen[0])
        self.assertIsNone(re.fullmatch(r"(?P<stem>.+)\.(?P<number>\d+)\.json", seen[0]))


class AtomicRecordWriteBrokenCopies(WriteNewBase):
    """The checks above must be able to fail."""

    def test_the_pre_change_writer_leaves_a_damaged_file_at_the_final_name(self):
        control = load_evidence()
        exec(OLD_WRITE_NEW, control.__dict__)
        with self.assertRaises(OSError):
            control.write_new(self.final, Unserialisable(a=1))
        self.assertEqual(self.listing(), ["task.0001.json"], "the old writer left a file at the final name")
        self.assertEqual(self.final.read_bytes(), b"", "an empty record that would block the version chain")

    def test_a_copy_whose_last_step_replaces_overwrites_an_existing_version(self):
        broken = mutated("os.link(temp, path)", "os.replace(temp, path)")
        self.final.write_bytes(b'{"old": true}\n')
        broken.write_new(self.final, {"new": True})
        self.assertEqual(json.loads(self.final.read_bytes().decode("utf-8")), {"new": True},
                         "the broken copy replaced the existing version, which the real function refuses")
        self.final.write_bytes(b'{"old": true}\n')
        with self.assertRaises(FileExistsError):
            load_evidence().write_new(self.final, {"new": True})

    def test_a_copy_that_leaves_its_temporary_file_is_caught_by_the_listing(self):
        broken = mutated("temp.unlink()", "pass")
        broken.write_new(self.final, {"a": 1})
        self.assertEqual(len(self.listing()), 2, self.listing())


STATES = ("unknown", "documented", "probed")
CLAIMS = ("instruction_files", "survives_compaction", "subagents_see_project_instructions", "hook_events",
          "hook_files_read", "frontmatter_fields_honoured")
ADAPTER = ("tool", "named_agents", "nesting", "fresh_context_flag", "read_only_tool_list")
OUTCOMES = ("observed", "blocked", "not-run", "unverified")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def claim_problems(where, claim, probed_only=False):
    """What is wrong with one matrix claim: a state from the three, and a source for anything but unknown."""
    if not isinstance(claim, dict) or claim.get("state") not in STATES:
        return [where + ": state is one of " + ", ".join(STATES)]
    if claim["state"] == "unknown":
        return []
    problems = []
    if not isinstance(claim.get("source"), str) or not claim["source"].strip():
        problems.append(where + ": a documented or probed claim names its source")
    if "value" not in claim:
        problems.append(where + ": a documented or probed claim carries its value")
    if probed_only and claim["state"] != "probed":
        problems.append(where + ": claimed without a probe marker")
    return problems


def matrix_problems(document):
    """Schema check for the P2 matrix fields. It asserts no host fact: it only requires that none is claimed
    without a state and a source."""
    problems = []
    for key in ("unknown", "not-applicable", "skipped", "blank"):
        if not isinstance(document.get("cell_states", {}).get(key), str):
            problems.append("cell_states lacks " + key)
    optional = document.get("capability_contract", {}).get("optional")
    if not isinstance(optional, list) or not optional:
        problems.append("capability_contract lists no optional capabilities")
    vocabulary = document.get("rule_vocabulary", {})
    if not isinstance(vocabulary.get("revision"), int) or vocabulary["revision"] < 1:
        problems.append("rule_vocabulary has no revision")
    for key in ("tools", "path_classes"):
        names = vocabulary.get(key)
        if not isinstance(names, list) or not names or len(set(names)) != len(names) or not all(
                isinstance(n, str) and re.fullmatch(r"[a-z][a-z-]*", n) for n in names):
            problems.append("rule_vocabulary." + key + " is a closed list of unique lower-case names")
    for host in document.get("hosts", []):
        name = host.get("name", "?")
        for field in CLAIMS:
            problems += claim_problems(name + "." + field, host.get(field))
        events = host.get("hook_events", {})
        for number, event in enumerate(events.get("claims", []) if isinstance(events, dict) else []):
            where = "%s.hook_events[%d]" % (name, number)
            if not (isinstance(event.get("source"), str) and event["source"].startswith("https://")):
                problems.append(where + ": a hook-event claim cites a documentation URL")
            if not isinstance(event.get("probed"), bool):
                problems.append(where + ": a hook-event claim is marked probed true or false")
            if event.get("can") not in ("block", "annotate", "observe"):
                problems.append(where + ": a hook can block, annotate or observe")
        adapter = host.get("delegation_adapter", {})
        for field in ADAPTER:
            problems += claim_problems(name + ".delegation_adapter." + field, adapter.get(field),
                                       probed_only=field == "nesting")
        for field in ("actual_install", "actual_invocation", "actual_isolation"):
            value = host.get(field)
            if not isinstance(value, str) or not value.startswith(OUTCOMES):
                problems.append(name + "." + field + " starts with an outcome: " + ", ".join(OUTCOMES))
            elif not value.startswith("not-run") and not DATE.search(value):
                problems.append(name + "." + field + " carries the date it was observed")
        if str(host.get("actual_invocation", "")).startswith("blocked") and not str(host.get("first_failure") or "").strip():
            problems.append(name + ": a blocked invocation keeps its first failure")
        for field in optional if isinstance(optional, list) else ():
            if field not in host:
                problems.append(name + " reports no " + field + " against the shared contract list")
    return problems


def matrix():
    return json.loads(text("hosts/capabilities.json"))


class MatrixFieldTests(unittest.TestCase):
    """CM-11, CM-16, CM-17, CM-19, CM-20, CM-21: the fields exist for every host, each marked unknown, documented or
    probed, and the copy of the matrix with one of them damaged fails the same function."""

    def test_the_matrix_passes_its_own_schema(self):
        self.assertEqual(matrix_problems(matrix()), [])

    def test_all_three_hosts_carry_every_field(self):
        hosts = {h["name"]: h for h in matrix()["hosts"]}
        self.assertEqual(set(hosts), {"Claude Code", "Codex", "Cursor"})
        for name, host in hosts.items():
            for field in CLAIMS + ("delegation_adapter", "actual_install", "actual_invocation", "actual_isolation",
                                   "first_failure"):
                with self.subTest(host=name, field=field):
                    self.assertIn(field, host)

    def test_no_host_fact_is_claimed_without_a_source(self):
        # CM-11 and the others stay unknown unless a dated observation or a documentation page is named.
        for host in matrix()["hosts"]:
            for field in ("survives_compaction", "subagents_see_project_instructions", "hook_files_read"):
                self.assertEqual(host[field], {"state": "unknown"}, host["name"] + "." + field)
            self.assertEqual(host["hook_events"]["claims"], [], host["name"])
            self.assertEqual(host["delegation_adapter"]["nesting"]["state"], "unknown", host["name"])

    def damaged(self, mutate):
        document = copy.deepcopy(matrix())
        mutate(document)
        return matrix_problems(document)

    def test_a_copy_missing_a_field_a_source_or_a_marker_fails(self):
        cases = {
            "instruction_files gone": lambda d: d["hosts"][0].pop("instruction_files"),
            "survives_compaction gone": lambda d: d["hosts"][1].pop("survives_compaction"),
            "subagents_see_project_instructions unmarked": lambda d: d["hosts"][2].update(
                subagents_see_project_instructions={"state": "yes"}),
            "hook_files_read gone": lambda d: d["hosts"][0].pop("hook_files_read"),
            "frontmatter_fields_honoured gone": lambda d: d["hosts"][1].pop("frontmatter_fields_honoured"),
            "a claim without a source": lambda d: d["hosts"][1].update(
                survives_compaction={"state": "documented", "value": "yes"}),
            "a hook-event claim with neither URL nor marker": lambda d: d["hosts"][1]["hook_events"]["claims"].append(
                {"event": "PreToolUse", "can": "block"}),
            "cell_states without not-applicable": lambda d: d["cell_states"].pop("not-applicable"),
            "a host without an optional capability": lambda d: d["hosts"][0].pop("background_execution"),
            "an invocation summary with no outcome": lambda d: d["hosts"][0].update(actual_invocation="it worked"),
            "isolation gone": lambda d: d["hosts"][2].pop("actual_isolation"),
            "a blocked invocation without its first failure": lambda d: d["hosts"][0].update(first_failure=None),
            "nesting claimed without a probe marker": lambda d: d["hosts"][1]["delegation_adapter"].update(
                nesting={"state": "documented", "value": "one level", "source": "docs"}),
            "an open vocabulary": lambda d: d["rule_vocabulary"].update(tools=[]),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(self.damaged(mutate), [], name)

    def test_a_well_formed_hook_event_claim_passes(self):
        def add(d):
            d["hosts"][1]["hook_events"]["claims"].append(
                {"event": "PreToolUse", "can": "block", "source": "https://example.invalid/hooks", "probed": False})
        self.assertEqual(self.damaged(add), [])

    def test_the_first_failure_is_kept_for_the_blocked_codex_invocation(self):
        codex = next(h for h in matrix()["hosts"] if h["name"] == "Codex")
        self.assertTrue(codex["actual_invocation"].startswith("blocked"))
        self.assertIn("model_not_found", codex["first_failure"])
        self.assertIn("run 1", codex["first_failure"])

    def test_the_existing_receipts_were_not_edited(self):
        # the three new outcome fields sit beside the recorded invocation text; its hashes are still there
        codex = next(h for h in matrix()["hosts"] if h["name"] == "Codex")
        for digest in ("dda21c1550baf1316cf55c3c7be0bb4be969e3aca2908f48013e9fcfdc539831",
                       "1f83d9b230f3518d22c2f3ac9a3522d2e1b556ed56e1f7a8630b459d7b80a874"):
            self.assertIn(digest, codex["actual_invocation"])


WORDING = {
    "references/authority.md": {
        "GS-14": ["No standing grant", "leaving a sandbox or read-only mode", "switching permission mode",
                  "a model-proposed command"],
        "GS-15": ["Show the resolved action first", "a request id", "no stable target, no approval"],
        "WA-41": ["A preview's approval is of its hash, re-checked before applying"],
        "GS-17": ["a repository's agent, hook, skill or rules file", "until the user approves its exact hash",
                  "an edit asks again", "re-check at use"],
        "GS-19": ["after listing what it will modify or delete", "a one-line rollback", "\"clean up\" is no grant"],
        "GS-34": ["Re-check authority at the executing step, not only at entry", "or only races"],
    },
    # the Host guard section moved from authority.md to guards.md; each pin keeps its phrases and follows its text
    "references/guards.md": {
        "GS-21": ["stop switch or gate definition the agent can rewrite is advice", "outside the work tree"],
        "WA-24 and WA-25": ["fails to evaluate is listed apart from matched and unmatched",
                            "an errored allow or ask grants nothing", "an errored deny denies"],
        "EV-57 and WA-26": ["lists the guards that ran, what each decided", "the deciding rule ids, layer and rule-set hash",
                            "\"allowed, guard did not run\" is inconclusive"],
        "WA-28": ["`ruletest.py --against` diff over a probe corpus", "inconclusive"],
    },
    "references/isolation.md": {
        "GS-59": ["declares its write paths", "check prefix overlap", "unknown, not conflict-free"],
        "EV-59 and GS-63": ["Label it full, degraded, failed or skipped, with what it cannot restore",
                            "mark a step applied only after its check passes", "let failure restore"],
        "GS-57": ["created and recorded as owned", "refuse a dirty, unpushed or question-holding workspace",
                  "never clear a non-empty directory you did not make"],
    },
    "hosts/README.md": {
        "CM-11 and CM-17 and CM-20": ["`unknown`, `documented` or `probed` with its source",
                                      "whether their rules survive compaction or reach subagents",
                                      "a rule that must survive goes in a channel known to",
                                      "honoured front-matter fields", "install, invocation and isolation outcomes apart, with the first failure"],
        "CM-19": ["`not-applicable` is not `unknown`", "reads `skipped`, never passed"],
        "CM-21": ["a delegation adapter"],
        "CM-16 and GS-33": ["Unverified guidance, not a probe", "can block, annotate or only observe", "answers deny or no opinion, never allow",
                            "an earlier allow or async hook can leave its gate dead", "independent, idempotent"],
        "EV-58": ["gates only turns that edited files", "blocks once naming the missing evidence",
                  "then lets the turn end and records the gap"],
        "EV-63": ["plant a unique marker only in the parent", "read the child's own transcript",
                  "a hidden transcript leaves the level unverified"],
        "GS-40": ["a sandbox is isolation only if it limits both filesystem and network"],
    },
}


def missing(body, phrases):
    return [phrase for phrase in phrases if phrase not in body]


class P2WordingTests(unittest.TestCase):
    """The text rules have no behaviour of their own to run (westack ships no permission engine or hook), so the
    pages must keep saying them, and each pin also runs on a copy with the phrase taken out: it must fail there."""

    def test_each_rule_keeps_its_gate_words(self):
        for relative, items in WORDING.items():
            body = flat(relative)
            for item, phrases in items.items():
                with self.subTest(doc=relative, item=item):
                    self.assertEqual(missing(body, phrases), [])

    def test_a_page_with_the_phrase_taken_out_fails_the_same_check(self):
        for relative, items in WORDING.items():
            body = flat(relative)
            for item, phrases in items.items():
                for phrase in phrases:
                    with self.subTest(doc=relative, item=item, phrase=phrase):
                        self.assertIn(phrase, missing(body.replace(phrase, ""), phrases))

    def test_the_stop_hook_pointer_to_the_release_rule_is_still_there(self):
        self.assertIn("A stop hook the user installs follows the release rule in [durable](../references/durable.md)",
                      flat("hosts/README.md"))

    def test_the_router_did_not_grow(self):
        self.assertLessEqual(len(text("SKILL.md").split()), 600)

    def test_the_new_text_keeps_the_diagnostic_label_and_the_fail_closed_rules(self):
        guards, authority = flat("references/guards.md"), flat("references/authority.md")
        for phrase in ("diagnostic, not a sandbox", "guard blocked", "never passes silently"):
            self.assertIn(phrase, guards)
        self.assertIn("strictest-first", authority)


class ChangelogAndEndingTests(unittest.TestCase):
    HEADING = "## 1.0.0-alpha.5 (P2 adoption), unreleased"
    ITEMS = ("EV-57", "EV-58", "EV-59", "EV-63", "GS-14", "GS-15", "GS-17", "GS-19", "GS-21", "GS-33", "GS-34", "GS-40",
             "GS-57", "GS-59", "GS-63", "HD-40", "CM-11", "CM-16", "CM-17", "CM-19", "CM-20", "CM-21", "WA-24", "WA-25",
             "WA-26", "WA-27", "WA-28", "WA-41")
    TOUCHED = ("references/authority.md", "references/isolation.md", "hosts/README.md", "hosts/capabilities.json",
               "scripts/evidence.py", "scripts/ruletest.py", "tests/test_guards_p2.py", "tests/test_ruletest_p2.py",
               "tests/test_p1_delegation.py")

    def section(self):
        body = text("CHANGELOG.md")
        self.assertIn(self.HEADING, body)
        return body.split(self.HEADING)[1].split("\n## ")[0]

    def test_the_changelog_cites_every_applied_item_under_the_new_heading(self):
        # At least once: other P2 groups applied their own parts of shared items (EV-58, EV-59, GS-15) and cite them too.
        mine = self.section()
        for item in self.ITEMS:
            with self.subTest(item=item):
                self.assertGreaterEqual(len(re.findall(r"\bP2 \(" + item + r"\)", mine)), 1)

    def test_touched_files_are_lf_only(self):
        for relative in self.TOUCHED:
            with self.subTest(file=relative):
                self.assertNotIn(b"\r", (ROOT / relative).read_bytes())

    def test_the_changelog_keeps_one_line_ending_throughout(self):
        data = (ROOT / "CHANGELOG.md").read_bytes()
        crlf, lf = data.count(b"\r\n"), data.count(b"\n")
        self.assertIn(crlf, (0, lf), "mixed line endings: %d CRLF of %d lines" % (crlf, lf))


if __name__ == "__main__":
    unittest.main()
