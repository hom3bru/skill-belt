"""westack-build delivery diff audit: read the git output the agent saved and flag every changed path that
needs a decision before the work is called done.

  python diffaudit.py DIFF [--status STATUS] [--start-status STATUS0] [--allow GLOB ...]
                           [--deferred-ok GLOB ...] [--tests GLOB ...]

DIFF is the saved output of `git diff --no-color <start revision>`; STATUS of `git status --porcelain
--untracked-files=all` now (untracked files never appear in a diff); STATUS0 the same command saved before
the first edit, so paths that were already dirty are reported as not this work's. --allow names the
authorised paths (globs; ** spans folders); without it scope is reported as not checked. --deferred-ok
names deferred-execution paths the user explicitly put in scope. --tests replaces the test-path globs.

Flags (each one needs a decision unless marked info):
  out-of-scope                 outside every --allow glob
  deferred-execution           CI, hooks, build files, conftest.py, host settings, package scripts: runs later;
                               also the protected floor no --allow reaches: agent steering files (instruction
                               files, MCP configuration, agent ignore files, .agents), .git and .aws
  deferred-execution-in-scope  (info) the same, named by --deferred-ok
  existing-test-changed        an existing test lost or changed a line, gained a skip or focus marker, or was
                               deleted or renamed; evidence names assertion-removed, test-removed, skip-added
  tests-added                  (info) only additions to tests
  test-selection-changed       test configuration that narrows what runs (addopts, deselect, ignore patterns)
  check-config-changed         a linter, formatter or type-check configuration, or an ignore file, edited with no
                               reason in the diff (a comment on an added line); a first-time creation is fine, and
                               so is a change that only removes ignore-file lines. A check silenced by
                               configuration is not a fixed check
  scratch-candidate           a new file named like a probe, log or backup (repro_, debug_, tmp, *.log, *.orig)
  format-only-hunk             a hunk of an existing file that changes nothing once whitespace, quote style and
                               import order are normalised on both sides: reformatting no request asked for (NR-25).
                               Lines keep their relative indentation depth when the line count is unchanged
  preexisting-dirty            already modified before the work started: read its hunks before claiming them

Exit 0 clean, 1 needs-decision, 2 empty change or unreadable input, 64 usage. Standard library only. It
reads saved files and prints JSON; it runs nothing, never calls git and never touches the network.
"""
import argparse
import json
import pathlib
import re
import sys

FORMAT = "westack-build-diffaudit-1"
TEST_GLOBS = ("**/test_*.py", "**/*_test.py", "**/tests/**", "**/test/**", "**/__tests__/**", "**/*.test.*",
              "**/*.spec.*", "**/spec/**", "**/*_spec.rb", "**/*Test.java", "**/*Tests.cs", "**/*_test.go",
              "**/conftest.py")
DEFERRED_GLOBS = (".git/hooks/**", "**/.husky/**", "**/.githooks/**", "**/.pre-commit-config.yaml",
                  "**/.github/workflows/**", "**/.github/actions/**", "**/.gitlab-ci.yml", "**/.circleci/**",
                  "**/azure-pipelines.yml", "**/Jenkinsfile", "**/.travis.yml", "**/.drone.yml",
                  "**/bitbucket-pipelines.yml", "**/Makefile", "**/*.mk", "**/CMakeLists.txt", "**/Dockerfile*",
                  "**/docker-compose*.yml", "**/setup.py", "**/conftest.py", "**/noxfile.py", "**/tox.ini",
                  "**/build.gradle*", "**/pom.xml", "**/.envrc", "**/.bashrc", "**/.zshrc", "**/.profile",
                  "**/.bash_profile", "**/*profile.ps1", "**/.claude/settings*.json", "**/.claude/hooks/**",
                  "**/.codex/**", "**/.cursor/hooks*", "**/.vscode/tasks.json", "**/.devcontainer/**",
                  "**/*.service", "**/crontab",
                  # GS-20, the protected-path floor: a broad --allow does not reach the files that steer the agent
                  # (instruction files, MCP configuration, the ignore files that hide paths from it, .agents), git's
                  # own state (.git, .gitconfig) or a credential store (.aws).
                  "**/AGENTS.md", "**/CLAUDE.md", "**/CLAUDE.local.md", "**/GEMINI.md", "**/.cursorrules",
                  "**/.cursor/rules/**", "**/.windsurfrules", "**/.clinerules", "**/.github/copilot-instructions.md",
                  "**/.github/instructions/**", "**/.mcp.json", "**/.cursor/mcp.json", "**/.vscode/mcp.json",
                  "**/.gemini/settings.json", "**/.claudeignore", "**/.cursorignore", "**/.aiderignore",
                  "**/.codeiumignore", "**/.geminiignore", "**/.agents/**", "**/.git/**", "**/.gitconfig",
                  "**/.aws/**")
# Files that run later only when certain keys change: a hunk counts when its text names one of them.
CONTENT_DEFERRED = {
    "package.json": re.compile(r'"(?:scripts|(?:pre|post)?(?:install|prepare|publish|pack|test|build|lint|start|'
                               r'commit|version))"\s*:'),
    "pyproject.toml": re.compile(r"\[(?:build-system|project\.scripts|project\.entry-points[^\]]*|"
                                 r"tool\.[^\]]*(?:scripts|hooks|build)[^\]]*)\]|\bbuild-backend\b"),
    "setup.cfg": re.compile(r"\[options\.entry_points\]|\bentry_points\b|\bcmdclass\b"),
}
TEST_CONFIG = re.compile(r"(?:^|/)(?:pytest\.ini|tox\.ini|setup\.cfg|pyproject\.toml|package\.json|"
                         r"(?:jest|vitest|karma)\.conf(?:ig)?\.\w+|\.mocharc[\w.]*|phpunit\.xml[\w.]*)$")
SELECTION = re.compile(r"testpaths|addopts|--deselect|\s-k\s|--ignore|norecursedirs|python_files|python_functions|"
                       r"collect_ignore|testPathIgnorePatterns|testMatch|testRegex|modulePathIgnorePatterns|"
                       r"\bexclude\b|\"test\"\s*:")
# Linter, formatter and type-check configurations, and the ignore files that exempt paths from them (SS-12).
CHECK_CONFIG_GLOBS = (
    "**/.eslintrc", "**/.eslintrc.*", "**/eslint.config.*", "**/.eslintignore", "**/.prettierrc", "**/.prettierrc.*",
    "**/prettier.config.*", "**/.prettierignore", "**/.stylelintrc", "**/.stylelintrc.*", "**/stylelint.config.*",
    "**/.stylelintignore", "**/.markdownlint*", "**/.yamllint", "**/.yamllint.y*ml", "**/.shellcheckrc",
    "**/.hadolint.y*ml", "**/.sqlfluff", "**/ruff.toml", "**/.ruff.toml", "**/.flake8", "**/.pylintrc", "**/pylintrc",
    "**/mypy.ini", "**/.mypy.ini", "**/.isort.cfg", "**/.pycodestyle", "**/pyrightconfig.json",
    "**/.pyre_configuration", "**/.golangci.y*ml", "**/.rubocop.y*ml", "**/rustfmt.toml", "**/.rustfmt.toml",
    "**/clippy.toml", "**/.clang-format", "**/.clang-tidy", "**/.editorconfig", "**/biome.json*", "**/.biome.json*")
# Files shared with other settings count only when the edit touches a check setting.
_TOOLS = r"ruff|mypy|pylint|black|isort|pyright|flake8|pycodestyle|bandit|pyflakes|autopep8|yapf"
_CHECK_KEYS = (r"per-file-ignores|extend-ignore|extend-select|ignore_missing_imports|ignore_errors|disallow_\w+|"
               r"warn_\w+|check_untyped_defs|reportMissing\w+")
_PYTHON_CHECKS = re.compile(r"\[(?:tool\.)?(?:" + _TOOLS + r")\b|\b(?:" + _CHECK_KEYS + r")\b")
CHECK_CONFIG_CONTENT = {
    "pyproject.toml": _PYTHON_CHECKS, "setup.cfg": _PYTHON_CHECKS, "tox.ini": _PYTHON_CHECKS,
    "package.json": re.compile(r'"(?:eslintConfig|eslintIgnore|prettier|stylelint|lint-staged)"\s*:'),
}
TYPECHECK_JSON = re.compile(r"(?:^|/)[jt]sconfig[\w.-]*\.json$")
TYPECHECK_KEYS = re.compile(r'"(?:strict\w*|noImplicit\w+|noUnused\w+|noUnchecked\w+|skipLibCheck|checkJs|allowJs|'
                            r'useUnknownInCatchVariables|exclude|include|files)"\s*:')
REASON_COMMENT = re.compile(r"^\s*(?:#|//|;|/\*|\*|<!--)\s*\S+(?:\s+\S+){2,}")
REASON_INLINE = re.compile(r"\S\s+(?:#|//)\s*\S+(?:\s+\S+)+\s*$")
ASSERTION = re.compile(r"\bassert\w*\b|\bexpect\s*\(|\.should\b|\bassert(?:_eq|_ne)?!|\bt\.(?:Error|Fatal)f?\(|"
                       r"\brequire\.\w+\(|\.fail\(|\braises\b|\bRaises\b|\.to[A-Z]\w*\(")
SKIP = re.compile(r"@(?:unittest\.)?skip\w*|@pytest\.mark\.(?:skip\w*|xfail)|\bpytest\.(?:skip|xfail|importorskip)\(|"
                  r"\.skipTest\(|\b(?:it|test|describe|context)\.(?:skip|only|todo)\b|\bx(?:it|describe|test|context)"
                  r"\s*\(|\bf(?:it|describe)\s*\(|@Disabled\b|@Ignore\b|#\[ignore\]|\bt\.Skip\w*\(|"
                  r"\bskip\s*[:=]\s*(?:true|True)\b|\.only\s*\(")
TEST_DEF = re.compile(r"^\s*(?:async\s+)?def\s+test\w*|\b(?:it|test)\s*\(\s*['\"`]|^\s*func\s+Test\w+|@Test\b|"
                      r"\[(?:Fact|Test|TestMethod)\]")
SCRATCH = re.compile(r"(?i)^(?:repro|reproduce|scratch|tmp|temp|debug|try|playground)(?:[_.-][\w.-]*)?$|"
                     r"\.(?:log|orig|rej|bak|swp|tmp)$|~$|^\.DS_Store$|^nohup\.out$")
ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}
# Import statements, compared as a sorted set so a reorder alone counts as formatting (NR-25).
IMPORT_LINE = re.compile(r"^\s*(?:import\s|from\s+\S+\s+import\s|#\s*include\s|using\s+[\w.]+\s*;|"
                         r"(?:const|let|var)\s+\S+\s*=\s*require\s*\()")
DECIDE = {"out-of-scope", "deferred-execution", "existing-test-changed", "test-selection-changed",
          "check-config-changed", "scratch-candidate", "format-only-hunk", "preexisting-dirty"}
EVIDENCE_LIMIT = 8


class AuditError(ValueError):
    """The input cannot be read as git output."""


def decode(data):
    """Text from saved bytes: UTF-16 with a byte-order mark (Windows PowerShell 5 redirection) or UTF-8."""
    text = data.decode("utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else data.decode("utf-8-sig", "replace")
    return text.replace("\r\n", "\n")


def _glob(pattern):
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def matches(path, globs):
    """True when a repository-relative POSIX path matches any glob (* within a folder, ** across folders)."""
    for pattern in globs:
        pattern = pattern.replace("\\", "/")
        if _glob(pattern[2:] if pattern.startswith("./") else pattern).match(path):
            return True
    return False


def _unquote(token):
    """A git path token: C-quoted ("a/caf\\303\\251") or bare. Octal escapes are UTF-8 bytes."""
    if not (len(token) >= 2 and token[0] == '"' and token[-1] == '"'):
        return token
    out, i, body = bytearray(), 0, token[1:-1]
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body):
            if re.fullmatch(r"[0-7]{3}", body[i + 1:i + 4]):
                out.append(int(body[i + 1:i + 4], 8))
                i += 4
                continue
            out.append(ESCAPES.get(body[i + 1], ord(body[i + 1])))
            i += 2
            continue
        out.extend(body[i].encode("utf-8"))
        i += 1
    return out.decode("utf-8", "replace")


def _strip(path, prefix):
    path = _unquote(path.strip())
    return path[len(prefix):] if path.startswith(prefix) else path


def _header_paths(rest):
    """Old and new paths from the text after 'diff --git ', quoted or bare."""
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|\S+', rest)
    if len(tokens) == 2:
        return _strip(tokens[0], "a/"), _strip(tokens[1], "b/")
    half = rest.split(" b/", 1)  # bare paths with spaces: 'a/x y b/x y'
    if len(half) != 2:
        raise AuditError("unreadable diff header: diff --git " + rest)
    return _strip(half[0], "a/"), _strip("b/" + half[1], "b/")


def parse_diff(text):
    """[{path, old, change, hunks: [[(kind, line), ...]]}] from a unified git diff."""
    files, current, hunk = [], None, None
    for line in text.split("\n"):
        if line.startswith("diff --git "):
            old, new = _header_paths(line[len("diff --git "):])
            current = {"path": new, "old": old, "change": "modified", "hunks": []}
            files.append(current)
            hunk = None
        elif line.startswith(("diff --cc ", "diff --combined ")):
            raise AuditError("combined (merge) diffs are not supported: diff against the start revision")
        elif current is None:
            if line.strip() and not line.startswith(("warning:", "hint:")):  # git's stderr, saved with the diff
                raise AuditError("not a unified git diff: no 'diff --git' header before content")
        elif hunk is None and line.startswith("new file mode"):
            current["change"] = "added"
        elif hunk is None and line.startswith("deleted file mode"):
            current["change"] = "deleted"
        elif hunk is None and line.startswith(("rename from ", "copy from ")):
            current["old"] = _unquote(line.split(" from ", 1)[1])
            current["change"] = "renamed" if line.startswith("rename") else "copied"
        elif hunk is None and line.startswith(("rename to ", "copy to ")):
            current["path"] = _unquote(line.split(" to ", 1)[1])
        elif hunk is None and line.startswith("+++ ") and line[4:].strip() != "/dev/null":
            current["path"] = _strip(line[4:], "b/")
        elif line.startswith("@@"):
            hunk = []
            current["hunks"].append(hunk)
        elif hunk is not None and line[:1] in ("+", "-", " "):
            hunk.append((line[0], line[1:]))
    return files


def parse_status(text):
    """(untracked paths, all listed paths) from `git status --porcelain` v1 output."""
    untracked, listed = [], []
    for line in text.split("\n"):
        if len(line) < 4 or line[2] != " ":
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = _unquote(path.strip())
        if line[:2] == "!!":
            continue
        listed.append(path)
        if line[:2] == "??":
            untracked.append(path)
    return untracked, listed


def _test_evidence(entry):
    """Why a change to an existing test needs a decision, or [] when it only adds."""
    if entry["change"] == "deleted":
        return ["file-deleted"]
    found = []
    if entry["change"] in ("renamed", "copied") and entry["old"] != entry["path"]:
        found.append("renamed from " + entry["old"])
    removed = [text for hunk in entry["hunks"] for kind, text in hunk if kind == "-"]
    added = [text for hunk in entry["hunks"] for kind, text in hunk if kind == "+"]
    kept = {text.strip() for text in added}
    for text in removed:
        if text.strip() in kept or not text.strip():
            continue
        tag = "test-removed" if TEST_DEF.search(text) else "assertion-removed" if ASSERTION.search(text) else \
            "line-changed"
        found.append("%s: %s" % (tag, text.strip()))
    for text in added:
        if SKIP.search(text):
            found.append("skip-added: " + text.strip())
    return found


def _deferred(entry):
    name = entry["path"].rsplit("/", 1)[-1]
    if matches(entry["path"], DEFERRED_GLOBS):
        return True
    trigger = CONTENT_DEFERRED.get(name)
    if trigger is None:
        return False
    return any(any(k in "+-" for k, _ in hunk) and any(trigger.search(t) for _, t in hunk) for hunk in entry["hunks"])


def _check_config(entry):
    """Changed lines of a check configuration or ignore file edited with no stated reason, else [].

    Creating the file is fine. Lines removed from an ignore file only tighten the gate. A reason is a comment on an
    added line (three words or more) or an inline comment on one; a format with no comments cannot state it here.
    """
    if entry["change"] in ("added", "untracked"):
        return []
    path = entry["path"]
    name = path.rsplit("/", 1)[-1]
    lines = [(kind, text) for hunk in entry["hunks"] for kind, text in hunk]
    changed = [(kind, text) for kind, text in lines if kind in "+-"]
    if matches(path, CHECK_CONFIG_GLOBS):
        if name.endswith("ignore") and not any(kind == "+" for kind, _ in changed):
            return []  # only lines removed (or the file deleted): fewer paths are exempt, so the gate tightens
    else:
        touches = CHECK_CONFIG_CONTENT.get(name) or (TYPECHECK_KEYS if TYPECHECK_JSON.search(path) else None)
        if touches is None or not changed or not any(touches.search(text) for _, text in lines):
            return []
    if not changed and entry["change"] != "deleted":
        return []
    if any(kind == "+" and (REASON_COMMENT.search(text) or REASON_INLINE.search(text)) for kind, text in changed):
        return []
    return ["config: " + kind + text.strip() for kind, text in changed if text.strip()] or ["config: file-deleted"]


def _fold(text):
    """Text with formatting folded out: one quote style, whitespace collapsed, no spaces beside punctuation."""
    text = re.sub(r"\s+", " ", text.replace("'", '"')).strip()
    return re.sub(r" ?([^\w\s]) ?", r"\1", text)


def _normal(lines):
    """One side of a hunk with formatting taken out: its imports as a sorted list, the rest joined and folded, and
    the rest line by line with each line's relative indentation depth (so moving a line into a block is no reformat)."""
    imports = sorted(_fold(text) for text in lines if IMPORT_LINE.match(text))
    body = [text.expandtabs(4) for text in lines if not IMPORT_LINE.match(text) and text.strip()]
    depths = sorted({len(text) - len(text.lstrip()) for text in body})
    shaped = [(depths.index(len(text) - len(text.lstrip())), _fold(text)) for text in body]
    return imports, _fold(" ".join(body)), shaped


def _same_but_format(removed, added):
    """True when two sides differ only in formatting. With as many non-blank lines on each side, every line must keep
    its relative depth; a re-wrap (a different line count) is compared as joined text."""
    old, new = _normal(removed), _normal(added)
    if old[:2] != new[:2]:
        return False
    return len(old[2]) != len(new[2]) or old[2] == new[2]


def _format_only(entry):
    """A note for each hunk of an existing file whose two sides are equal once formatting is normalised, else []."""
    if entry["change"] not in ("modified", "renamed", "copied"):
        return []
    found = []
    for number, hunk in enumerate(entry["hunks"], 1):
        removed = [text for kind, text in hunk if kind == "-"]
        added = [text for kind, text in hunk if kind == "+"]
        if (removed or added) and _same_but_format(removed, added):
            found.append("format-only: hunk %d (%d removed, %d added)" % (number, len(removed), len(added)))
    return found


def audit(diff_text, status="", allow=(), deferred_ok=(), tests=(), start_status=""):
    """The audit report for saved git output. Raises AuditError when the diff cannot be read."""
    tests = list(tests) or list(TEST_GLOBS)
    entries = parse_diff(diff_text)
    untracked, _ = parse_status(status)
    _, before = parse_status(start_status)
    preexisting = sorted(set(before))
    seen = {e["path"] for e in entries}
    entries += [{"path": p, "old": None, "change": "untracked", "hunks": []}
                for p in untracked if p not in seen and p not in before]
    files = []
    for entry in entries:
        path, flags, evidence = entry["path"], [], []
        if path in before:
            flags.append("preexisting-dirty")
        if allow and not matches(path, allow):
            flags.append("out-of-scope")
        if _deferred(entry):
            flags.append("deferred-execution-in-scope" if matches(path, deferred_ok) else "deferred-execution")
        is_test = matches(path, tests) or (entry["old"] and matches(entry["old"], tests))
        if is_test and entry["change"] in ("added", "untracked"):
            flags.append("tests-added")
        elif is_test:
            found = _test_evidence(entry)
            if found:
                flags.append("existing-test-changed")
                evidence += found
            elif entry["hunks"]:
                flags.append("tests-added")
        if TEST_CONFIG.search(path) and any(k in "+-" and SELECTION.search(t) for h in entry["hunks"] for k, t in h):
            flags.append("test-selection-changed")
            evidence += ["selection: " + t.strip() for h in entry["hunks"] for k, t in h
                         if k in "+-" and SELECTION.search(t)]
        found = _check_config(entry)
        if found:
            flags.append("check-config-changed")
            evidence += found
        if entry["change"] in ("added", "untracked") and SCRATCH.search(path.rsplit("/", 1)[-1]):
            flags.append("scratch-candidate")
        found = _format_only(entry)
        if found:
            flags.append("format-only-hunk")
            evidence += found
        files.append({"path": path, "change": entry["change"], "flags": flags,
                      "evidence": evidence[:EVIDENCE_LIMIT] + (["... %d more" % (len(evidence) - EVIDENCE_LIMIT)]
                                                                if len(evidence) > EVIDENCE_LIMIT else [])}
                     | ({"from": entry["old"]} if entry["change"] in ("renamed", "copied") else {}))
    decide = sorted({f["path"] for f in files if DECIDE & set(f["flags"])})
    if not files:
        verdict, code = "empty", 2
    elif decide:
        verdict, code = "needs-decision", 1
    else:
        verdict, code = "clean", 0
    counts = {}
    for f in files:
        for flag in f["flags"]:
            counts[flag] = counts.get(flag, 0) + 1
    return {"format": FORMAT, "verdict": verdict, "exit_code": code, "files": files, "needs_decision": decide,
            "counts": counts, "scope": "checked" if allow else "not-checked", "preexisting": preexisting,
            "claim": "reads saved git output and ran nothing; heuristic flags for a decision, not proof of harm"}


def _read(path):
    try:
        return decode(pathlib.Path(path).read_bytes())
    except OSError as exc:
        raise FileNotFoundError(str(exc))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("diff", help="saved `git diff --no-color <start revision>` output")
    parser.add_argument("--status", help="saved `git status --porcelain --untracked-files=all` output, now")
    parser.add_argument("--start-status", help="the same, saved before the first edit")
    parser.add_argument("--allow", action="append", default=[], metavar="GLOB", help="authorised paths (repeatable)")
    parser.add_argument("--deferred-ok", action="append", default=[], metavar="GLOB",
                        help="deferred-execution paths the user explicitly scoped (repeatable)")
    parser.add_argument("--tests", action="append", default=[], metavar="GLOB", help="test-path globs (repeatable)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    try:
        report = audit(_read(args.diff), _read(args.status) if args.status else "", args.allow, args.deferred_ok,
                       args.tests, _read(args.start_status) if args.start_status else "")
    except FileNotFoundError as exc:
        sys.stderr.write("diffaudit.py: cannot read input: %s\n" % exc)
        return 64
    except AuditError as exc:
        report = {"format": FORMAT, "verdict": "unreadable", "exit_code": 2, "reason": str(exc),
                  "claim": "reads saved git output and ran nothing"}
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
