"""DS-1 and DS-2 (dsh-superagent, 2026-10-31): `diffscope.py resolve LEDGER` checks two rules of resolve mode that were
only prose.

  DS-1  at most three review rounds per automated reviewer, a round being one distinct bot run and never one comment;
        the fourth distinct run is refused (`bot-round-cap`), a bot comment with no run id cannot be counted
        (`bot-run-unknown`), and the runs already addressed come back in the report so a later session continues the count
  DS-2  each reply answers in its own comment's thread: a reply with no comment to answer is `reply-not-in-thread`, and a
        reply that says again what the thread (or an earlier reply) already says is `reply-repeats`

Run: python -B -m unittest discover -s skills/westack-review/tests -v
The script under test is loaded by path; WESTACK_REVIEW_DIFFSCOPE may point at another copy. Every rule also runs against a
copy of the script with that one condition edited out, and the copy must let the bad ledger through. Each copy is built
before its assertions, so a line that has moved fails loudly instead of passing as "the check failed".
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get("WESTACK_REVIEW_DIFFSCOPE")
                      or pathlib.Path(__file__).resolve().parents[1] / "scripts" / "diffscope.py").resolve()
BOT = "coderabbitai[bot]"


def load(path=SCRIPT):
    key = "westack_review_threads_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def comment(cid, author=BOT, run="r1", **extra):
    return dict({"id": cid, "author": author, "run": run}, **extra)


def codes(report):
    return [(f["code"], f["id"]) for f in report["findings"]]


FOUR_RUNS = [comment("c1", run="r1"), comment("c2", run="r2"), comment("c3", run="r3"), comment("c4", run="r4")]
SEVEN_ONE_RUN = [comment("c%d" % n, run="r1") for n in range(1, 8)]
THREAD = [comment("c1", author="maria", run=None, answers=["Fixed in 1a2b3c4: the cache is now keyed by tenant."]),
          comment("c2", author="maria")]


def reply(rid, to, text="Fixed in 9f8e7d6: the loop now stops at the last page.", **extra):
    return dict({"id": rid, "in_reply_to": to, "text": text}, **extra)


class BotRounds(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def run_ledger(self, comments, **extra):
        return self.m.resolve(dict({"comments": comments}, **extra))

    def test_the_fourth_distinct_run_of_one_bot_is_refused_and_the_first_three_pass(self):
        report = self.run_ledger(FOUR_RUNS)
        self.assertEqual(codes(report), [("bot-round-cap", "c4")], report)
        self.assertEqual(report["status"], "findings")
        self.assertEqual(report["cap"], 3)
        self.assertEqual(report["rounds"][BOT], {"runs": ["r1", "r2", "r3"], "count": 3})

    def test_seven_comments_from_one_run_are_one_round(self):
        report = self.run_ledger(SEVEN_ONE_RUN)
        self.assertEqual((report["status"], report["findings"]), ("clean", []), report)
        self.assertEqual(report["rounds"][BOT], {"runs": ["r1"], "count": 1})

    def test_every_comment_of_a_refused_run_is_named(self):
        report = self.run_ledger(FOUR_RUNS + [comment("c5", run="r4"), comment("c6", run="r5")])
        self.assertEqual(codes(report), [("bot-round-cap", "c4"), ("bot-round-cap", "c5"), ("bot-round-cap", "c6")])
        self.assertEqual(report["rounds"][BOT]["count"], 3, "a refused run is never counted")

    def test_each_automated_reviewer_has_its_own_three_rounds(self):
        other = "copilot-pull-request-reviewer[bot]"
        two_bots = [comment("a%d" % n, run="ra%d" % n) for n in (1, 2, 3)] \
            + [comment("b%d" % n, author=other, run="rb%d" % n) for n in (1, 2, 3)]
        report = self.run_ledger(two_bots)
        self.assertEqual(report["findings"], [], report)
        self.assertEqual({name: row["count"] for name, row in report["rounds"].items()}, {BOT: 3, other: 3})

    def test_people_are_never_capped(self):
        people = [comment("p%d" % n, author="maria", run="review-%d" % n) for n in range(1, 8)]
        report = self.run_ledger(people)
        self.assertEqual((report["status"], report["rounds"]), ("clean", {}), report)

    def test_a_bot_is_a_bot_by_its_login_or_by_its_flag(self):
        flagged = [comment("c%d" % n, author="review-helper", run="r%d" % n, bot=True) for n in range(1, 5)]
        self.assertEqual(codes(self.run_ledger(flagged)), [("bot-round-cap", "c4")])
        unflagged = [comment("c%d" % n, author="review-helper", run="r%d" % n) for n in range(1, 5)]
        self.assertEqual(self.run_ledger(unflagged)["findings"], [], "no flag and no [bot] login is a person")

    def test_rounds_from_an_earlier_session_count_and_come_back(self):
        earlier = {"rounds": {BOT: ["r1", "r2", "r3"]}}
        report = self.run_ledger([comment("c9", run="r4")], **earlier)
        self.assertEqual(codes(report), [("bot-round-cap", "c9")], report)
        again = self.run_ledger([comment("c8", run="r2")], **earlier)
        self.assertEqual(again["findings"], [], "an earlier round's comment is not a new round")
        shaped = self.run_ledger([comment("c7", run="r3")], rounds={BOT: {"runs": ["r1", "r2"], "count": 2}})
        self.assertEqual(shaped["rounds"][BOT], {"runs": ["r1", "r2", "r3"], "count": 3})
        carried = self.run_ledger([comment("c6", run="r4")], rounds={n: r["runs"] for n, r in shaped["rounds"].items()})
        self.assertEqual(codes(carried), [("bot-round-cap", "c6")], "the report's rounds feed the next session")

    def test_a_bot_comment_with_no_run_id_cannot_be_counted(self):
        report = self.run_ledger([comment("c1", run=None), comment("c2", run="   ")])
        self.assertEqual(codes(report), [("bot-run-unknown", "c1"), ("bot-run-unknown", "c2")], report)
        self.assertEqual(report["rounds"], {}, "an unknown run is not a round")

    def test_the_cap_is_a_whole_number_the_report_states(self):
        report = self.run_ledger(FOUR_RUNS, cap=4)
        self.assertEqual((report["findings"], report["cap"]), ([], 4))
        self.assertTrue(any("not the default 3" in note for note in report["notes"]), report)
        for bad in (0, -1, "3", 2.5, True, None):
            with self.subTest(cap=bad), self.assertRaises(self.m.DiffError):
                self.run_ledger(FOUR_RUNS, cap=bad)

    def test_a_ledger_off_shape_is_refused_not_guessed(self):
        for bad in ([], "comments", {"comments": "c1"}, {"comments": [{"author": BOT}]}, {"comments": [], "rounds": []},
                    {"comments": [], "replies": {"id": "p1"}}, {"comments": [], "replies": ["p1"]}):
            with self.subTest(bad=bad), self.assertRaises(self.m.DiffError):
                self.m.resolve(bad)


class ThreadReplies(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def run_ledger(self, replies, comments=THREAD):
        return self.m.resolve({"comments": comments, "replies": replies})

    def test_a_reply_inside_each_comments_own_thread_is_clean(self):
        report = self.run_ledger([reply("p1", "c1", "Kept the keying; the test at tests/test_cache.py:40 covers it."),
                                  reply("p2", "c2")])
        self.assertEqual((report["status"], report["findings"]), ("clean", []), report)

    def test_replies_drafted_as_one_top_level_comment_are_flagged(self):
        table = "| Comment | Verdict |\n| c1 | accept |\n| c2 | reject |"
        for missing in (None, "", "   "):
            with self.subTest(in_reply_to=missing):
                report = self.run_ledger([reply("summary", missing, table)])
                self.assertEqual(codes(report), [("reply-not-in-thread", "summary")], report)

    def test_a_reply_to_no_gathered_comment_or_to_several_is_flagged(self):
        report = self.run_ledger([reply("p1", "c404"), reply("p2", ["c1", "c2"]), {"id": "p3", "text": "Done."}])
        self.assertEqual(codes(report), [("reply-not-in-thread", "p1"), ("reply-not-in-thread", "p2"),
                                         ("reply-not-in-thread", "p3")], report)

    def test_a_reply_that_says_again_what_the_thread_already_says_is_flagged(self):
        said_again = "fixed in 1A2B3C4 - the cache is now keyed by tenant"
        report = self.run_ledger([reply("p1", "c1", said_again)])
        self.assertEqual(codes(report), [("reply-repeats", "p1")], report)

    def test_a_reply_that_repeats_an_earlier_reply_in_the_same_ledger_is_flagged(self):
        report = self.run_ledger([reply("p1", "c2", "Rejected: the loop is bounded by the page count."),
                                  reply("p2", "c2", "Rejected: the loop is bounded by the page count!")])
        self.assertEqual(codes(report), [("reply-repeats", "p2")], report)

    def test_the_same_words_in_another_comments_thread_are_not_a_repeat(self):
        same = "Rejected: the loop is bounded by the page count."
        self.assertEqual(self.run_ledger([reply("p1", "c1", same), reply("p2", "c2", same)])["findings"], [])

    def test_a_new_answer_in_a_thread_that_has_one_is_not_a_repeat(self):
        report = self.run_ledger([reply("p1", "c1", "Also fixed for the admin path in 5d4c3b2.")])
        self.assertEqual(report["findings"], [], report)

    def test_answers_may_be_given_as_objects_with_a_text(self):
        thread = [comment("c1", author="maria", run=None, answers=[{"author": "dev", "text": "Won't fix: by design."}])]
        report = self.run_ledger([reply("p1", "c1", "won't fix - by design")], comments=thread)
        self.assertEqual(codes(report), [("reply-repeats", "p1")], report)

    def test_a_ledger_with_replies_and_rounds_reports_both(self):
        report = self.m.resolve({"comments": FOUR_RUNS, "replies": [reply("p1", None, "all done")]})
        self.assertEqual(sorted(code for code, _ in codes(report)), ["bot-round-cap", "reply-not-in-thread"])

    def test_the_report_says_what_it_does_not_show(self):
        text = json.dumps(self.run_ledger([reply("p1", "c1", "Fixed.")])).lower()
        self.assertIn("does not show", text)
        self.assertNotIn("approved", text)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", "-I", str(SCRIPT), "resolve", *args],
                              capture_output=True, text=True, env=env, timeout=120)

    def test_exit_codes_hash_and_unreadable_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            clean = json.dumps({"comments": SEVEN_ONE_RUN, "replies": [reply("p1", "c1")]}).encode("utf-8")
            (tmp / "clean.json").write_bytes(clean)
            (tmp / "over.json").write_text(json.dumps({"comments": FOUR_RUNS}), encoding="utf-8")
            (tmp / "bad.json").write_text("not json", encoding="utf-8")
            (tmp / "shape.json").write_text(json.dumps(["c1"]), encoding="utf-8")
            ok = self.run_cli(str(tmp / "clean.json"))
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            body = json.loads(ok.stdout)
            self.assertEqual((body["mode"], body["status"]), ("resolve", "clean"))
            self.assertEqual(body["ledger_sha256"], hashlib.sha256(clean).hexdigest())
            over = self.run_cli(str(tmp / "over.json"))
            self.assertEqual(over.returncode, 1)
            self.assertEqual(json.loads(over.stdout)["findings"][0]["code"], "bot-round-cap")
            for name in ("bad.json", "shape.json", "missing.json"):
                self.assertEqual(self.run_cli(str(tmp / name)).returncode, 2, name)
            self.assertEqual(self.run_cli().returncode, 64)


class BrokenCopies(unittest.TestCase):
    """Each copy has one condition of the rule edited out of the script's source, and must accept the ledger the
    condition exists to refuse."""

    def broken(self, tmp, *edits):
        """A copy of the script with each (pattern, replacement) line edit applied once, in one file."""
        source = SCRIPT.read_text(encoding="utf-8")
        for pattern, replacement in edits:
            edited, count = re.subn(pattern, replacement, source, count=1, flags=re.M)
            self.assertEqual(count, 1, "the line to break is not in the script: " + pattern)
            self.assertNotEqual(edited, source)
            source = edited
        target = pathlib.Path(tmp) / "diffscope_broken.py"
        target.write_text(source, encoding="utf-8")
        return load(target)

    def check(self, tmp, pattern, replacement, ledger, code):
        """(real report, broken report) for one ledger; the real one has `code`, the broken one lacks it."""
        broken = self.broken(tmp, (pattern, replacement))
        real, copy = load().resolve(ledger), broken.resolve(ledger)
        self.assertIn(code, [c for c, _ in codes(real)], real)
        return real, copy

    def test_a_copy_that_counts_comments_not_runs_fails_the_seven_comment_ledger(self):
        ledger = {"comments": SEVEN_ONE_RUN}
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.broken(tmp, (r"^        elif run in runs:$", "        elif False:"))
            copy = broken.resolve(ledger)
        self.assertEqual(load().resolve(ledger)["findings"], [], "the real check keeps one round")
        self.assertEqual({c for c, _ in codes(copy)}, {"bot-round-cap"}, "the copy refuses the fourth comment of one run")

    def test_a_copy_without_the_cap_lets_the_fourth_run_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, copy = self.check(tmp, r"^        elif len\(runs\) >= cap:$", "        elif False:", {"comments": FOUR_RUNS},
                                 "bot-round-cap")
        self.assertEqual(copy["findings"], [])

    def test_a_copy_that_treats_every_author_as_a_person_lets_the_fourth_run_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, copy = self.check(tmp, r"^        if not _bot\(item\):$", "        if True:", {"comments": FOUR_RUNS},
                                 "bot-round-cap")
        self.assertEqual(copy["findings"], [])

    def test_a_copy_that_assumes_a_missing_run_is_a_known_round_passes_an_unknown_run(self):
        ledger = {"comments": [comment("c1", run=None)]}
        with tempfile.TemporaryDirectory() as tmp:
            _, copy = self.check(tmp, r"^        if not _text\(run\):$", "        if False:", ledger, "bot-run-unknown")
        self.assertNotIn("bot-run-unknown", [c for c, _ in codes(copy)])

    def test_a_copy_that_forgets_the_earlier_sessions_rounds_lets_the_fourth_through(self):
        ledger = {"comments": [comment("c9", run="r4")], "rounds": {BOT: ["r1", "r2", "r3"]}}
        with tempfile.TemporaryDirectory() as tmp:
            _, copy = self.check(tmp, r"^    known = .*$", "    known = {}", ledger, "bot-round-cap")
        self.assertEqual(copy["findings"], [])

    def test_a_copy_without_the_thread_check_lets_a_top_level_summary_through(self):
        ledger = {"comments": THREAD, "replies": [reply("summary", None, "| c1 | accept |")]}
        with tempfile.TemporaryDirectory() as tmp:
            _, copy = self.check(tmp, r"^        if not _text\(target\) or target not in thread:$", "        if False:", ledger,
                                 "reply-not-in-thread")
        self.assertEqual(copy["findings"], [])

    def test_a_copy_without_the_repeat_check_lets_a_repeated_answer_through(self):
        ledger = {"comments": THREAD, "replies": [reply("p1", "c1", "Fixed in 1a2b3c4: the cache is now keyed by tenant.")]}
        with tempfile.TemporaryDirectory() as tmp:
            _, copy = self.check(tmp, r"^        if key and key in thread\.get\(target, \[\]\):$", "        if False:", ledger,
                                 "reply-repeats")
        self.assertEqual(copy["findings"], [])

    def test_a_copy_that_only_checks_a_reply_exists_fails_both_reply_ledgers(self):
        top_level = {"comments": THREAD, "replies": [reply("summary", None, "| c1 | accept |")]}
        repeated = {"comments": THREAD, "replies": [reply("p1", "c1", "Fixed in 1a2b3c4: the cache is now keyed by tenant.")]}
        with tempfile.TemporaryDirectory() as tmp:
            existence = self.broken(tmp, (r"^        if not _text\(target\) or target not in thread:$", "        if False:"),
                                    (r"^        if key and key in thread\.get\(target, \[\]\):$", "        if False:"))
            copies = existence.resolve(top_level), existence.resolve(repeated)
        self.assertEqual(codes(load().resolve(top_level)), [("reply-not-in-thread", "summary")])
        self.assertEqual(codes(load().resolve(repeated)), [("reply-repeats", "p1")])
        self.assertEqual([c["findings"] for c in copies], [[], []], "a copy that only sees that a reply exists passes both")


class Discipline(unittest.TestCase):
    def test_the_script_still_reads_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for banned in ("import subprocess", "os.system", "eval(", "exec(", "urllib", "socket", "shutil.rmtree"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
