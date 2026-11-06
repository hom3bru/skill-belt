"""DS-6 (dsh-superagent, 2026-10-31): a GitHub 404 is "not found or not visible to this account". GitHub answers 404, not
403, for a private resource the caller cannot see, so a row that reads "does not exist" with a GitHub 404 as its evidence
is a claim of absence the evidence cannot make: `research_log.py check` reports `404-read-as-absent` under the pacing
check. A row is a fetch, a search call or a rejected source on a GitHub host, with `http` 404 (or the number 404 in its
`result`, `note` or `reason`) and wording such as "does not exist", "no such repository" or "never existed".

Run: python -B -m unittest discover -s skills/westack-research/tests -v
Every rule also runs against a copy of the script with that one condition edited out, and the copy must let the bad row
through (or, for the two limits, flag the row the rule leaves alone). Each copy is built before its assertions.
"""
import json
import re
import unittest

import test_research_log as base

rl = base.rl
OK_WORDING = "not found or not visible to this account"


def fetch(url="https://github.com/acme/ghost-repo", http=404, result="the repository does not exist", **extra):
    row = {"at": "2026-10-30T10:02:30Z", "url": url, "status": "failed", "attempt": 1, "source": "S3"}
    if http is not None:
        row["http"] = http
    if result is not None:
        row["result"] = result
    row.update(extra)
    return row


class Rows(base.Fixture):
    def with_fetch(self, **kwargs):
        self.log["fetches"].append(fetch(**kwargs))
        return self.check_log()

    def test_a_github_404_recorded_as_not_found_or_not_visible_is_clean(self):
        report = self.with_fetch(result="404: " + OK_WORDING)
        self.assertEqual(report["findings"], [], report["findings"])
        self.assertEqual(report["status"], "clean")

    def test_a_github_404_read_as_the_repository_not_existing_is_flagged(self):
        report = self.with_fetch()
        found = [f for f in report["findings"] if f["code"] == "404-read-as-absent"]
        self.assertEqual(len(found), 1, report["findings"])
        self.assertEqual((found[0]["check"], found[0]["item"]), ("pacing", "S3"))
        self.assertIn("not visible", found[0]["detail"])
        self.assertEqual((report["status"], report["checks"]["pacing"]), ("findings", "failed"))

    def test_every_github_host_and_every_wording_of_absence_counts(self):
        for url in ("https://api.github.com/repos/acme/ghost", "https://raw.githubusercontent.com/acme/ghost/main/x.md",
                    "https://gist.github.com/acme/abc", "https://codeload.github.com/acme/ghost/zip/main",
                    "https://GitHub.com/acme/ghost"):
            with self.subTest(url=url):
                self.assertIn("404-read-as-absent", base.codes(self.with_fetch(url=url)))
                self.log["fetches"].pop()
        for words in ("the repo doesn't exist", "it doesn’t exist", "no such repository", "the user never existed",
                      "the file no longer exists", "a non-existent release", "no such page"):
            with self.subTest(words=words):
                self.assertIn("404-read-as-absent", base.codes(self.with_fetch(result=words)))
                self.log["fetches"].pop()

    def test_the_404_may_sit_in_the_wording_instead_of_a_field(self):
        report = self.with_fetch(http=None, result="GitHub returned 404, so the repository does not exist")
        self.assertIn("404-read-as-absent", base.codes(report))

    def test_a_search_call_row_is_read_too(self):
        call = {"at": "2026-10-30T10:03:30Z", "url": "https://api.github.com/repos/acme/ghost", "window": "any",
                "ranking": "relevance", "status": "failed", "attempt": 1, "http": 404, "note": "no such repository"}
        self.search("Q3")["calls"].append(call)
        report = self.check_log()
        self.assertEqual([(f["code"], f["item"]) for f in report["findings"]], [("404-read-as-absent", "Q3")])

    def test_a_rejected_source_whose_reason_reads_a_404_as_absence_is_flagged(self):
        self.log["sources"].append({"id": "S6", "title": "ghost-repo", "url": "https://github.com/acme/ghost-repo",
                                    "kind": "primary", "found_by": {"given": "the user pasted the link"},
                                    "status": "rejected", "reason": "the link returns 404: the repository does not exist"})
        report = self.check_log()
        self.assertEqual([(f["code"], f["item"]) for f in report["findings"]], [("404-read-as-absent", "S6")])
        self.source("S6")["reason"] = "the link returns 404: " + OK_WORDING + "; ask the user to open it"
        self.assertEqual(self.check_log()["findings"], [])

    def test_a_404_from_another_host_is_left_alone(self):
        report = self.with_fetch(url="https://blog.example/old-post", result="the page does not exist")
        self.assertNotIn("404-read-as-absent", base.codes(report))

    def test_a_github_row_that_says_absent_without_a_404_is_left_alone(self):
        for http in (200, 403, None):
            with self.subTest(http=http):
                report = self.with_fetch(http=http, result="the file does not exist in the tarball, listing read")
                self.assertNotIn("404-read-as-absent", base.codes(report))
                self.log["fetches"].pop()

    def test_the_report_says_what_it_cannot_tell(self):
        text = " ".join(self.check_log()["not_checked"]).lower()
        self.assertIn("404", text)
        self.assertIn("not visible", text)

    def test_the_cli_exits_1_on_the_finding(self):
        self.log["fetches"].append(fetch())
        path = self.save()
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            code = rl.main(["check", str(path), "--core", str(base.CORE)])
        self.assertEqual(code, 1)
        self.assertIn("404-read-as-absent", out.getvalue())
        self.assertEqual(json.loads(out.getvalue())["status"], "findings")


class BrokenCopies(base.Fixture):
    """One condition of the rule edited out of a copy of the script. The copy for the wording must pass the bad row; the
    copies for the two limits must flag the row the limit exists to leave alone."""

    def copy(self, *edits):
        return base.broken(*edits)

    def test_a_copy_that_does_not_read_the_wording_passes_a_404_read_as_absent(self):
        edit = ("        if ABSENT.search(said):", "        if False:")
        self.log["fetches"].append(fetch())
        control = self.copy(edit)
        self.assertIn("404-read-as-absent", base.codes(self.check_log()))
        self.assertNotIn("404-read-as-absent", base.codes(self.check_log(control)))

    def test_a_copy_that_flags_every_host_flags_a_blog_404(self):
        edit = ('        if host(row.get("url")) not in GITHUB_HOSTS:', "        if False:")
        self.log["fetches"].append(fetch(url="https://blog.example/old-post", result="the page does not exist"))
        control = self.copy(edit)
        self.assertNotIn("404-read-as-absent", base.codes(self.check_log()))
        self.assertIn("404-read-as-absent", base.codes(self.check_log(control)))

    def test_a_copy_that_asks_for_no_404_flags_a_row_with_another_status(self):
        edit = ('        if not (str(row.get("http")) == "404" or re.search(r"\\b404\\b", said)):', "        if False:")
        self.log["fetches"].append(fetch(http=200, result="the file does not exist in the tarball"))
        control = self.copy(edit)
        self.assertNotIn("404-read-as-absent", base.codes(self.check_log()))
        self.assertIn("404-read-as-absent", base.codes(self.check_log(control)))

    def test_a_copy_that_does_not_scan_rejected_sources_passes_a_rejected_404(self):
        edit = ('    rows = list(requests_of(run)) + [(s.get("id"), s) for s in run.sources if s.get("status") == "rejected"]',
                '    rows = list(requests_of(run))')
        self.log["sources"].append({"id": "S6", "title": "ghost-repo", "url": "https://github.com/acme/ghost-repo",
                                    "kind": "primary", "found_by": {"given": "the user pasted the link"},
                                    "status": "rejected", "reason": "404: the repository does not exist"})
        control = self.copy(edit)
        self.assertIn("404-read-as-absent", base.codes(self.check_log()))
        self.assertNotIn("404-read-as-absent", base.codes(self.check_log(control)))


if __name__ == "__main__":
    unittest.main()
