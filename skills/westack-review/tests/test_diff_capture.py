"""RT-2: review diffs are saved with git's external diff programs and text converters turned off, so a repository's
configured drivers cannot change the bytes under review or run a program while they are saved.

The documented commands (the table in references/code.md, section 1) are read from the page and run in a fixture
repository whose `*.txt` files have a textconv driver and whose environment names an external diff program. With the
flags the saved diff shows the raw lines and no program ran; the same commands without the flags show the converted text
and the program's marker, so the fixture can see the hazard the flags remove.

Run: python -B -m unittest discover -s skills/westack-review/tests -v
Needs git on the path; without it the repository tests are skipped (reported as skipped, never as passed).
"""
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

CODE = pathlib.Path(__file__).resolve().parents[1] / "references" / "code.md"
GIT = shutil.which("git")
FLAGS = ("--no-color", "--no-ext-diff", "--no-textconv")


def documented_diffs(text):
    """The `git diff ...` commands in code.md's section 1 table."""
    section = text.split("## 1.", 1)[1].split("## 2.", 1)[0]
    return re.findall(r"`(git diff [^`]*)`", section)


def without_flags(command):
    return " ".join(part for part in command.split() if part not in FLAGS[1:])


class DocumentedCommands(unittest.TestCase):
    def test_every_documented_local_diff_turns_the_drivers_off(self):
        commands = documented_diffs(CODE.read_text(encoding="utf-8"))
        self.assertEqual(len(commands), 3, commands)
        for command in commands:
            with self.subTest(command=command):
                for flag in FLAGS:
                    self.assertIn(flag, command.split())

    def test_a_command_without_the_flags_fails_the_same_check(self):
        for command in documented_diffs(CODE.read_text(encoding="utf-8")):
            self.assertNotIn("--no-textconv", without_flags(command).split())
            self.assertNotIn("--no-ext-diff", without_flags(command).split())


@unittest.skipUnless(GIT, "git is not on the path")
class FixtureRepository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.marker = root / "external-diff-ran"
        convert = root / "shout.py"
        convert.write_text("import sys\nsys.stdout.write(open(sys.argv[1], encoding='utf-8').read().upper())\n",
                           encoding="utf-8")
        external = root / "external.py"
        external.write_text("import pathlib, sys\npathlib.Path(%r).write_text('ran')\nprint('EXTERNAL DRIVER OUTPUT')\n"
                            % str(self.marker), encoding="utf-8")
        empty = root / "gitconfig"
        empty.write_text("", encoding="utf-8")
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=str(empty), GIT_CONFIG_NOSYSTEM="1",
                        PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("GIT_EXTERNAL_DIFF", None)
        python = pathlib.PurePath(sys.executable).as_posix()
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.git("config", "diff.shout.textconv", '"%s" -B "%s"' % (python, pathlib.PurePath(convert).as_posix()))
        (self.repo / ".gitattributes").write_text("*.txt diff=shout\n", encoding="utf-8")
        (self.repo / "a.txt").write_text("alpha\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base")
        (self.repo / "a.txt").write_text("beta\n", encoding="utf-8")
        self.external_env = dict(self.env, GIT_EXTERNAL_DIFF='"%s" -B "%s"' % (
            pathlib.PurePath(sys.executable).as_posix(), pathlib.PurePath(external).as_posix()))

    def git(self, *args, env=None):
        done = subprocess.run([GIT, *args], cwd=self.repo, env=env or self.env, capture_output=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8", "replace"))
        return done.stdout.decode("utf-8", "replace")

    def saved(self, command, env=None):
        parts = shlex.split(command.replace("<merge-base>", "HEAD"))
        self.assertEqual(parts[:2], ["git", "diff"])
        return self.git(*parts[1:], env=env)

    def working_tree_command(self):
        return next(c for c in documented_diffs(CODE.read_text(encoding="utf-8")) if c.endswith(" HEAD"))

    def test_the_documented_command_saves_the_raw_lines(self):
        diff = self.saved(self.working_tree_command())
        self.assertIn("-alpha", diff)
        self.assertIn("+beta", diff)
        self.assertNotIn("BETA", diff)

    def test_without_the_flags_the_converter_changes_the_bytes_under_review(self):
        raw = self.saved(self.working_tree_command())
        converted = self.saved(without_flags(self.working_tree_command()))
        self.assertIn("+BETA", converted)
        self.assertNotIn("+beta", converted)
        self.assertNotEqual(raw, converted, "the diff hash would differ")

    def test_the_documented_command_runs_no_external_diff_program(self):
        self.saved(self.working_tree_command(), env=self.external_env)
        self.assertFalse(self.marker.exists(), "an external diff program ran")

    def test_without_the_flags_the_external_diff_program_runs(self):
        out = self.saved(without_flags(self.working_tree_command()), env=self.external_env)
        self.assertTrue(self.marker.exists())
        self.assertIn("EXTERNAL DRIVER OUTPUT", out)


if __name__ == "__main__":
    unittest.main()
