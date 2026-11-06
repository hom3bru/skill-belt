"""westack-ship gate: summarise saved git, forge and repository output into per-step findings before delivery.

  python shipgate.py --status FILE [--remotes FILE] [--log FILE] [--pr FILE|none] [--rules BRANCH=FILE|none ...]
                     [--repo DIR] [--diff FILE] [--receipts FILE] [--default-branch NAME] [--body FILE] [--ui-change]
                     [--grant commit,push,pr,merge,release] [--output NEW.json]

Inputs are saved outputs, never live calls:
  --status    git status --porcelain=v2 --branch --untracked-files=all   (porcelain v1 with -b also reads)
  --remotes   git remote -v
  --log       git log --oneline <base>..HEAD   (commits not on the remote, when the branch has no upstream)
  --pr        gh pr list --head <branch> --state open --json number,state,isDraft,headRefOid,baseRefName,
              autoMergeRequest   (a list), gh pr view --json ... (an object), or a GraphQL response with
              mergeQueueEntry, reviewDecision and reviewThreads(first: 100) { pageInfo { hasNextPage }
              nodes { isResolved path } } (a merge needs the last two; unread is unknown); "none" when the remote
              has no pull requests at all
  --rules     BRANCH=FILE: gh api .../branches/BRANCH/protection or .../rules/branches/BRANCH; repeatable;
              BRANCH=none when the remote has no protection system
  --repo      the repository folder: workflows and merge-bot configuration are read (read only)
  --diff      git diff --no-color <base> (release metadata and secrets are read from the added lines)
  --receipts  a checks.py diff or parse result (westack core)
  --body      the PR body written for `gh pr create` (DS-4): a change that alters what users see (a .css, .scss, .sass, .less,
              .html, .vue, .svelte, .jsx, .tsx or .astro file in the diff, or --ui-change) carries a before and an after
              capture, one line each, in pairs: `- before: ![alt](shots/b.png) | scenario: S | viewport: 1280x800 |
              theme: light | state: S | revision: SHA`. Findings at level decide for the pr and merge steps:
              ui-evidence-missing, -after-only, -before-only, -mismatch (a stated label differs) and -unlabelled (a label or
              the revision is missing). --ui-change with no body is ui-evidence-unknown; no body and no flag checks nothing.
              Nothing opens an image: a clean result does not show the capture is real, current or a design review.

A field that could not be read is unknown, and unknown never counts as absent. Exit codes: 0 nothing blocks the
granted steps and readiness holds; 1 a blocker or a decision; 2 cannot tell (a needed input is missing or
unknown); 64 usage or input error. Standard library only. It runs no command and writes only a new --output file
(exclusive create).
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

FORMAT = "westack-shipgate-1"
STEPS = ("commit", "push", "pr", "merge", "release")
LATER = ("push", "pr", "merge", "release")
LIMIT = 16 * 1024 * 1024
CLAIM = "summarises saved outputs; ran nothing and pushed nothing, so it is only as true as those outputs"


class UsageError(Exception):
    pass


# ------------------------------------------------------------------ findings
def _finding(findings, fid, level, steps, message, evidence=(), readiness=False):
    findings.append({"id": fid, "level": level, "steps": list(steps), "readiness": readiness, "message": message,
                     "evidence": list(evidence)})


# ------------------------------------------------------------------ git status
def parse_status(text):
    state = {"format": None, "branch": None, "head": None, "detached": False, "upstream": None, "ahead": None,
             "behind": None, "changed": [], "untracked": [], "conflicts": []}
    lines = [line.rstrip("\r") for line in text.splitlines() if line.strip()]
    if any(line.startswith("# branch.") for line in lines):
        state["format"] = "v2"
        for line in lines:
            if line.startswith("# branch.oid "):
                oid = line.split(" ", 2)[2].strip()
                state["head"] = None if oid == "(initial)" else oid
            elif line.startswith("# branch.head "):
                head = line.split(" ", 2)[2].strip()
                state["detached"] = head == "(detached)"
                state["branch"] = None if state["detached"] else head
            elif line.startswith("# branch.upstream "):
                state["upstream"] = line.split(" ", 2)[2].strip()
            elif line.startswith("# branch.ab "):
                match = re.match(r"# branch\.ab \+(\d+) -(\d+)", line)
                if match:
                    state["ahead"], state["behind"] = int(match[1]), int(match[2])
            elif line.startswith(("1 ", "2 ")):
                fields = line.split(" ", 8 if line[0] == "1" else 9)
                path = fields[-1].split("\t")[0]
                state["changed"].append(path)
            elif line.startswith("u "):
                state["conflicts"].append(line.split(" ", 10)[-1])
            elif line.startswith("? "):
                state["untracked"].append(line[2:])
        return state
    state["format"] = "v1"
    for line in lines:
        if line.startswith("## "):
            header = line[3:]
            if header.startswith(("HEAD (no branch)", "HEAD (detached")):
                state["detached"] = True
                continue
            header = re.sub(r"^No commits yet on ", "", header)
            match = re.match(r"(?P<branch>[^ .]+(?:\.(?!\.)[^ .]+)*)(?:\.\.\.(?P<up>\S+))?(?: \[(?P<ab>[^\]]*)\])?", header)
            if match:
                state["branch"], state["upstream"] = match["branch"], match["up"]
                if match["up"]:
                    ahead = re.search(r"ahead (\d+)", match["ab"] or "")
                    behind = re.search(r"behind (\d+)", match["ab"] or "")
                    gone = "gone" in (match["ab"] or "")
                    state["ahead"] = None if gone else int(ahead[1]) if ahead else 0
                    state["behind"] = None if gone else int(behind[1]) if behind else 0
            continue
        code, path = line[:2], line[3:]
        if code == "??":
            state["untracked"].append(path)
        elif code in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}:
            state["conflicts"].append(path)
        elif code != "!!":
            state["changed"].append(path.split(" -> ")[-1])
    return state


def parse_remotes(text):
    remotes = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            entry = remotes.setdefault(parts[0], {"name": parts[0], "fetch": None, "push": None})
            kind = parts[2].strip("()") if len(parts) > 2 else "fetch"
            entry["push" if kind == "push" else "fetch"] = parts[1]
    return sorted(remotes.values(), key=lambda r: r["name"])


# ------------------------------------------------------------------ pull request
def _pr_records(data):
    """(records, error): the open-or-named PR records in a gh list, gh view or GraphQL response."""
    if data == "none" or data == []:
        return [], None
    if isinstance(data, dict) and ("data" in data or "errors" in data):
        if data.get("errors"):
            return None, "the GraphQL response carries errors"
        repository = ((data.get("data") or {}).get("repository")) or {}
        if "pullRequest" in repository:
            return ([] if repository["pullRequest"] is None else [repository["pullRequest"]]), None
        nodes = (repository.get("pullRequests") or {}).get("nodes")
        if isinstance(nodes, list):
            return nodes, None
        return None, "the GraphQL response holds no pullRequest"
    if isinstance(data, dict):
        return [data], None
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data, None
    return None, "not a pull request record"


def review_findings(record, label):
    """Merge-only findings from the PR's review state: an unresolved review thread or an open change request blocks;
    a thread list that was not read, or not read in full, is unknown and never reads as clean."""
    findings = []
    threads = record.get("reviewThreads")
    nodes = threads.get("nodes") if isinstance(threads, dict) else threads
    partial = isinstance(threads, dict) and bool((threads.get("pageInfo") or {}).get("hasNextPage"))
    readable = isinstance(nodes, list) and all(isinstance(n, dict) and "isResolved" in n for n in nodes)
    if not readable or partial:
        _finding(findings, "review-threads-unknown", "unknown", ["merge"],
                 "%s: review threads were not read in full (GraphQL reviewThreads with isResolved), so unresolved "
                 "comments cannot be ruled out" % label)
    else:
        unresolved = [n for n in nodes if not n["isResolved"]]
        if unresolved:
            _finding(findings, "review-threads-open", "block", ["merge"],
                     "%s has %d unresolved review thread%s: settle each with its reviewer before merging"
                     % (label, len(unresolved), "" if len(unresolved) == 1 else "s"),
                     [str(n.get("path") or n.get("id") or "thread") for n in unresolved][:20])
    if record.get("reviewDecision") == "CHANGES_REQUESTED":
        _finding(findings, "changes-requested", "block", ["merge"], "%s has an open change request" % label)
    return findings


def read_pr(data, local_head, rules):
    """The PR summary and its findings. `rules` gives the base branch's protection, for the merge queue."""
    findings = []
    pr = {"state": "unknown", "number": None, "url": None, "draft": None, "head": None, "base": None,
          "auto_merge": "unknown", "merge_queue": "unknown"}
    if data is None:
        _finding(findings, "pr-unknown", "unknown", LATER,
                 "no pull request lookup was saved: an armed auto-merge or merge-queue entry cannot be ruled out")
        return pr, findings
    records, error = _pr_records(data)
    if error:
        _finding(findings, "pr-unknown", "unknown", LATER, "the pull request record is unreadable: " + error)
        return pr, findings
    if not records:
        pr.update(state="none", auto_merge="n/a", merge_queue="n/a")
        return pr, findings
    if len(records) > 1:
        _finding(findings, "pr-unknown", "unknown", LATER, "%d pull requests match: name one" % len(records),
                 ["#%s" % r.get("number") for r in records])
        return pr, findings
    record = records[0]
    state = str(record.get("state") or "unknown").upper()
    pr.update(state=state.lower(), number=record.get("number"), url=record.get("url"), draft=record.get("isDraft"),
              head=record.get("headRefOid"), base=record.get("baseRefName"))
    label = "#%s" % record.get("number")
    if state != "OPEN":
        level = "info"
        _finding(findings, "pr-not-open", level, ["merge"], "%s is %s: report that, never merge or push it again"
                 % (label, state.lower()))
        pr.update(auto_merge="n/a", merge_queue="n/a")
        return pr, findings
    if "autoMergeRequest" not in record:
        _finding(findings, "auto-merge-unknown", "unknown", ("push", "pr"),
                 "%s: autoMergeRequest was not read, so an armed auto-merge cannot be ruled out" % label)
    elif record["autoMergeRequest"]:
        pr["auto_merge"] = "armed"
        _finding(findings, "auto-merge-armed", "block", ("push", "pr"),
                 "%s has auto-merge armed: a push can merge without anyone deciding it; disarming it is its own action"
                 % label, [json.dumps(record["autoMergeRequest"], sort_keys=True)])
    else:
        pr["auto_merge"] = "off"
    if "mergeQueueEntry" in record:
        pr["merge_queue"] = "queued" if record["mergeQueueEntry"] else "no"
        if record["mergeQueueEntry"]:
            _finding(findings, "merge-queued", "block", ("push", "pr", "merge"),
                     "%s is in the merge queue: it can merge without anyone deciding it" % label,
                     [json.dumps(record["mergeQueueEntry"], sort_keys=True)])
    else:
        base = rules.get(pr["base"]) if pr["base"] else None
        if base and base.get("merge_queue") is False:
            pr["merge_queue"] = "no"
        else:
            _finding(findings, "merge-queue-unknown", "unknown", ("push", "pr"),
                     "%s: merge-queue membership was not read (gh pr view does not show it; use GraphQL "
                     "mergeQueueEntry, or rules for the base showing no merge queue)" % label)
    if record.get("isDraft"):
        _finding(findings, "pr-draft", "block", ["merge"], "%s is a draft" % label)
    findings += review_findings(record, label)
    if local_head and pr["head"] and pr["head"] != local_head:
        _finding(findings, "pr-head-mismatch", "block", ["merge"],
                 "%s head %s is not the local HEAD %s: the receipts do not cover what would merge"
                 % (label, pr["head"][:12], local_head[:12]))
    return pr, findings


# ------------------------------------------------------------------ protection
def read_rules(entries):
    """{protected, merge_queue, required_checks, pr_required, known, sources} from one branch's saved responses."""
    result = {"protected": None, "merge_queue": None, "required_checks": [], "pr_required": None, "known": False,
              "sources": []}
    checks = set()
    for data in entries:
        if data == "none":
            result["sources"].append("none: no protection system")
            result.update(known=True, protected=bool(result["protected"]), merge_queue=bool(result["merge_queue"]))
            continue
        if isinstance(data, list):
            result["sources"].append("rules")
            result["known"] = True
            result["protected"] = bool(result["protected"]) or bool(data)
            types = {str(rule.get("type")) for rule in data if isinstance(rule, dict)}
            result["merge_queue"] = bool(result["merge_queue"]) or "merge_queue" in types
            result["pr_required"] = bool(result["pr_required"]) or "pull_request" in types
            for rule in data:
                if isinstance(rule, dict) and rule.get("type") == "required_status_checks":
                    for item in (rule.get("parameters") or {}).get("required_status_checks") or []:
                        if isinstance(item, dict) and item.get("context"):
                            checks.add(item["context"])
            continue
        if isinstance(data, dict) and "message" in data and len(set(data) - {"message", "status",
                                                                             "documentation_url"}) == 0:
            if str(data["message"]).strip().lower() == "branch not protected":
                result["sources"].append("classic: not protected")
                result["known"] = True
                result["protected"] = bool(result["protected"])
            else:
                result["sources"].append("error: " + str(data["message"])[:80])
            continue
        if isinstance(data, dict):
            result["sources"].append("classic")
            result["known"] = True
            result["protected"] = True
            status = data.get("required_status_checks") or {}
            checks.update(c for c in status.get("contexts") or [] if isinstance(c, str))
            checks.update(c["context"] for c in status.get("checks") or [] if isinstance(c, dict) and c.get("context"))
            if data.get("required_pull_request_reviews"):
                result["pr_required"] = True
            continue
        result["sources"].append("unreadable")
    result["required_checks"] = sorted(checks)
    return result


# ------------------------------------------------------------------ repository automation
TRIGGERS = ("push", "pull_request_target", "pull_request", "workflow_run", "check_suite", "status", "schedule",
            "release", "workflow_dispatch", "merge_group")
MERGE = re.compile(r"gh pr merge\b[^\n]*--auto|enablePullRequestAutoMerge|enable-pull-request-automerge|"
                   r"automerge-action|auto-merge-action|merge-me-action|\bgh pr merge\b", re.I)
OPEN_PR = re.compile(r"gh pr create\b|create-pull-request@|repo-sync/pull-request|pull-request-action", re.I)
PUBLISH = re.compile(r"npm publish|yarn publish|pnpm publish|twine upload|gh-action-pypi-publish|poetry publish|"
                     r"cargo publish|gem push|gh release create|softprops/action-gh-release|goreleaser|docker push|"
                     r"docker/build-push-action|vercel\b[^\n]*--prod|fly deploy|flyctl deploy|kubectl apply|"
                     r"terraform apply|serverless deploy|firebase deploy|netlify deploy", re.I)
BOT_FILES = (".mergify.yml", ".mergify/config.yml", ".github/mergify.yml", ".kodiak.toml", ".github/.kodiak.toml",
             "bors.toml", ".github/auto-merge.yml")
RENOVATE = ("renovate.json", "renovate.json5", ".renovaterc", ".renovaterc.json", ".github/renovate.json",
            ".github/renovate.json5")


def _read(path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return data[:LIMIT].decode("utf-8", errors="replace")


def workflow_triggers(text):
    """Event names under the workflow's top-level `on:` (inline or block form); heuristic, not a YAML parser."""
    lines = text.splitlines()
    found = set()
    for index, line in enumerate(lines):
        match = re.match(r"^(?:on|\"on\"|'on'|true):\s*(.*)$", line)
        if not match:
            continue
        inline = match[1].split("#")[0]
        found.update(t for t in TRIGGERS if re.search(r"\b%s\b" % t, inline))
        for nested in lines[index + 1:]:
            if nested.strip() and not nested.startswith((" ", "\t", "-")):
                break
            key = re.match(r"^\s{1,4}-?\s*([a-z_]+)\s*:?", nested)
            if key and key[1] in TRIGGERS and len(nested) - len(nested.lstrip()) <= 4:
                found.add(key[1])
        break
    return sorted(found)


def scan_repo(root):
    """[{path, kind, triggers, evidence}] for workflows and bot configuration that merge, open PRs or publish."""
    root = pathlib.Path(root)
    found = []
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml")) if (root / ".github" / "workflows").is_dir() \
        else []
    for path in workflows:
        text = _read(path)
        if text is None:
            continue
        rel = path.relative_to(root).as_posix()
        triggers = workflow_triggers(text)
        evidence = {"merge": [], "open-pr": [], "publish": []}
        for number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for kind, pattern in (("merge", MERGE), ("open-pr", OPEN_PR), ("publish", PUBLISH)):
                if pattern.search(line):
                    evidence[kind].append("%s:%d: %s" % (rel, number, line.strip()[:160]))
        tags = bool(re.search(r"(?m)^\s+tags(?:-ignore)?\s*:", text))
        found.append({"path": rel, "kind": "workflow", "triggers": triggers, "tags": tags,
                      "merges": evidence["merge"], "opens_prs": evidence["open-pr"], "publishes": evidence["publish"]})
    for rel in BOT_FILES:
        text = _read(root / rel)
        if text is None:
            continue
        merges = [rel + ":1: merge bot configuration"]
        if "mergify" in rel:
            merges = ["%s:%d: %s" % (rel, n, l.strip()[:160]) for n, l in enumerate(text.splitlines(), 1)
                      if re.match(r"^\s*(merge|queue)\s*:", l)]
        if merges:
            found.append({"path": rel, "kind": "merge-bot", "triggers": [], "tags": False, "merges": merges,
                          "opens_prs": [], "publishes": []})
    for rel in RENOVATE:
        text = _read(root / rel)
        if text is None:
            continue
        merges = ["%s:%d: %s" % (rel, n, l.strip()[:160]) for n, l in enumerate(text.splitlines(), 1)
                  if re.search(r"[\"']?automerge[\"']?\s*:\s*true", l, re.I)]
        if merges:
            found.append({"path": rel, "kind": "renovate", "triggers": [], "tags": False, "merges": merges,
                          "opens_prs": [], "publishes": []})
    return found


def automation_findings(entries):
    findings = []
    merging = [e for e in entries if e["merges"] or (e["opens_prs"] and "push" in e["triggers"])]
    if merging:
        evidence = []
        for entry in merging:
            evidence += entry["merges"] + (entry["opens_prs"] if "push" in entry["triggers"] else [])
        _finding(findings, "auto-merge-config", "decide", ("push", "pr"),
                 "repository automation can open or merge a pull request without anyone deciding it; a push or a "
                 "new PR may set it off (heuristic: read the lines)", evidence)
    publishing = [e for e in entries if e["publishes"] and "push" in e["triggers"]]
    if publishing:
        steps = sorted({"release"} | ({"push"} if any(not e["tags"] for e in publishing) else set()))
        evidence = [line for entry in publishing for line in entry["publishes"]]
        _finding(findings, "publish-on-push", "decide", steps,
                 "a push%s runs a workflow that publishes or deploys: that push is the publish, and needs its grant"
                 % (" of a tag" if all(e["tags"] for e in publishing) else ""), evidence)
    return findings


# ------------------------------------------------------------------ diff: release metadata and secrets
CHANGELOG = re.compile(r"(?i)^(?:CHANGELOG|CHANGES|HISTORY|NEWS|RELEASE[-_]?NOTES)(?:\.[A-Za-z0-9]+)?$")
FRAGMENTS = re.compile(r"(?i)(?:^|/)(?:changelog\.d|\.changeset|changes|newsfragments|\.changes)/")
VERSION_LINE = (
    (re.compile(r"(?i)^(?:VERSION|version\.txt)$"), re.compile(r"^\s*v?(\d+\.\d+[\w.+-]*)\s*$")),
    (re.compile(r"(?:^|/)(?:package\.json|composer\.json)$"), re.compile(r"^\s*\"version\"\s*:\s*\"([^\"]+)\"")),
    (re.compile(r"(?:^|/)(?:pyproject\.toml|Cargo\.toml|setup\.cfg)$"), re.compile(r"^\s*version\s*=\s*[\"']([^\"']+)[\"']")),
    (re.compile(r"(?:^|/)setup\.py$"), re.compile(r"\bversion\s*=\s*[\"']([^\"']+)[\"']")),
    (re.compile(r"\.py$"), re.compile(r"^\s*__version__\s*=\s*[\"']([^\"']+)[\"']")),
    (re.compile(r"(?:^|/)Chart\.yaml$"), re.compile(r"^version:\s*[\"']?([^\"'\s]+)")),
    (re.compile(r"\.gemspec$"), re.compile(r"\.version\s*=\s*[\"']([^\"']+)[\"']")),
)
SECRETS = (
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("api-key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{24,}")),
)
SECRET_FILES = re.compile(r"(?i)(?:^|/)(?:\.env(?:\.[\w-]+)?|id_rsa|id_ed25519|[\w.-]+\.(?:pem|p12|pfx|key))$")
SAFE_ENV = re.compile(r"(?i)\.env\.(?:example|sample|template|dist)$")


def parse_diff(text):
    """{path: {"added": [(line_number, text)], "new": bool, "deleted": bool}} from a unified git diff."""
    files, current, number = {}, None, 0
    for line in text.splitlines():
        if line.startswith("diff --git "):
            match = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            current = files.setdefault(match[2] if match else line[11:], {"added": [], "new": False, "deleted": False})
            continue
        if current is None:
            continue
        if line.startswith("new file mode"):
            current["new"] = True
        elif line.startswith("deleted file mode"):
            current["deleted"] = True
        elif line.startswith("@@"):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            number = int(match[1]) if match else 0
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+"):
            current["added"].append((number, line[1:]))
            number += 1
        elif line.startswith(" "):
            number += 1
    return files


def release_findings(files, repo):
    findings = []
    versions, changelog_files, fragment = {}, [], False
    for path, info in files.items():
        name = path.rsplit("/", 1)[-1]
        if info["deleted"]:
            continue
        if FRAGMENTS.search(path):
            fragment = True
            continue
        if CHANGELOG.match(name):
            changelog_files.append(path)
            continue
        for file_pattern, line_pattern in VERSION_LINE:
            if file_pattern.search(path) or file_pattern.search(name):
                for _, added in info["added"]:
                    match = line_pattern.search(added)
                    if match:
                        versions.setdefault(match[1], []).append(path)
                break
    changelog_text = "\n".join(text for path in changelog_files for _, text in files[path]["added"])
    release = {"new_versions": sorted(versions), "version_files": sorted({p for ps in versions.values() for p in ps}),
               "changelog_changed": bool(changelog_files) or fragment, "changelog_files": changelog_files,
               "fragment": fragment}
    if len(versions) > 1:
        _finding(findings, "version-mismatch", "block", ("release", "merge", "pr"),
                 "the diff sets different versions: %s" % ", ".join(sorted(versions)),
                 ["%s -> %s" % (", ".join(paths), version) for version, paths in sorted(versions.items())],
                 readiness=True)
    if versions and not release["changelog_changed"]:
        repo_has = None
        if repo:
            root = pathlib.Path(repo)
            repo_has = any(CHANGELOG.match(p.name) for p in root.iterdir() if p.is_file()) or any(
                (root / d).is_dir() for d in ("changelog.d", ".changeset", "newsfragments", "changes"))
        if repo_has is not False:
            _finding(findings, "version-without-changelog", "decide", ("pr", "merge", "release"),
                     "the version changes to %s but no changelog entry is in the diff%s"
                     % (", ".join(sorted(versions)), "" if repo_has else " (the repository was not read: if it "
                                                                          "keeps a changelog, add the entry)"),
                     release["version_files"], readiness=True)
    elif versions and changelog_files:
        missing = [v for v in versions if not re.search(r"(?<![\w.])v?%s(?![\w.])" % re.escape(v), changelog_text)]
        if missing:
            _finding(findings, "changelog-missing-version", "decide", ("pr", "merge", "release"),
                     "the changelog changed but its added lines never name %s" % ", ".join(sorted(missing)),
                     changelog_files, readiness=True)
    return release, findings


def secret_findings(files):
    evidence = []
    for path, info in sorted(files.items()):
        if info["deleted"]:
            continue
        if SECRET_FILES.search(path) and not SAFE_ENV.search(path):
            evidence.append("%s: secret-file (%s)" % (path, "added" if info["new"] else "changed"))
        for number, text in info["added"]:
            for kind, pattern in SECRETS:
                if pattern.search(text):
                    evidence.append("%s:%d: %s" % (path, number, kind))
    findings = []
    if evidence:
        _finding(findings, "secret-in-diff", "block", STEPS,
                 "the diff adds what looks like a credential or private key; values are not shown", evidence,
                 readiness=True)
    return findings


# ------------------------------------------------------------------ receipts
def receipt_findings(data):
    findings = []
    summary = {"status": "missing"}
    if data is None:
        _finding(findings, "receipts-missing", "unknown", LATER, "no saved checks.py result: readiness is unproven",
                 readiness=True)
        return summary, findings
    if not (isinstance(data, dict) and data.get("format") == "westack-checks-1"):
        summary["status"] = "unreadable"
        _finding(findings, "receipts-inconclusive", "unknown", LATER,
                 "the receipts file is not a checks.py result", readiness=True)
        return summary, findings
    if data.get("kind") == "diff":
        code = data.get("exit_code")
        summary = {"status": {0: "passed", 1: "failed"}.get(code, "inconclusive"), "verdict": data.get("verdict"),
                   "new_failures": data.get("new_failures") or [],
                   "preexisting_failures": data.get("preexisting_failures") or []}
        if code == 1:
            _finding(findings, "receipts-failing", "block", LATER, "new failures against the baseline",
                     summary["new_failures"], readiness=True)
        elif code != 0:
            _finding(findings, "receipts-inconclusive", "unknown", LATER, "checks.py could not tell: "
                     + "; ".join(data.get("reasons") or []), readiness=True)
        elif summary["preexisting_failures"]:
            _finding(findings, "preexisting-failures", "info", (), "failures that were already there, by name",
                     summary["preexisting_failures"])
        return summary, findings
    counts = data.get("counts") or {}
    executed = (counts.get("passed") or 0) + (counts.get("failed") or 0)
    summary = {"status": "passed", "counts": counts, "complete": data.get("complete")}
    if not data.get("complete") or executed == 0:
        summary["status"] = "inconclusive"
        _finding(findings, "receipts-inconclusive", "unknown", LATER,
                 "the run is incomplete or executed no tests: not a pass", readiness=True)
    elif counts.get("failed"):
        summary["status"] = "failed"
        _finding(findings, "receipts-failing", "block", LATER, "%d tests failed (no baseline to separate new from "
                 "pre-existing)" % counts["failed"], [t["name"] for t in data.get("tests") or []
                                                     if t.get("status") == "failed"], readiness=True)
    return summary, findings


# ------------------------------------------------------------------ UI evidence in the PR body (DS-4)
UI_FILE = re.compile(r"(?i)\.(?:css|scss|sass|less|html?|vue|svelte|jsx|tsx|astro)$")
CAPTURE = re.compile(r"^[\s>*+|-]*\**\s*(before|after)\b\W*?:\s*(.*)$", re.I)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)\s]+\)|<(?:img|video)\b|[\w./-]+\.(?:png|jpe?g|gif|webp|svg|mp4|webm|mov)\b", re.I)
VIEW = ("scenario", "viewport", "theme", "state")  # what a before and its after must share
UI_CLAIM = ("reads the saved PR body's before and after lines and the diff's file names; it opens no image, so it cannot "
            "tell a real capture from a mockup or a stale one, and a clean result is not a design review")


def _captures(body):
    """The capture lines of a PR body: {kind, image, labels}. A line starting before: or after: is a capture only when it
    holds an image or a label, so prose that happens to start that way is left alone."""
    found = []
    for line in body.splitlines():
        match = CAPTURE.match(line)
        if not match:
            continue
        labels = {}
        for part in re.split(r"\s*[|;]\s*", match[2]):
            key, colon, value = part.partition(":")
            if colon and key.strip().lower() in VIEW + ("revision",) and value.strip():
                labels[key.strip().lower()] = value.strip()
        image = bool(IMAGE.search(match[2]))
        if image or labels:
            found.append({"kind": match[1].lower(), "image": image, "labels": labels})
    return found


def ui_evidence(body, forced, ui_files=()):
    """DS-4: (summary, findings) for the before and after captures in a saved PR body. The change alters what users see
    when `forced` (the --ui-change flag) or the diff holds a UI file; with no saved body only the flag makes that unknown,
    since the body is written after the push this gate is usually run for."""
    findings, needed = [], bool(forced or ui_files)
    if body is None and forced:
        _finding(findings, "ui-evidence-unknown", "unknown", ("pr",),
                 "the change alters what users see, but no PR body was saved (--body): before and after captures cannot "
                 "be ruled out")
        return {"status": "unknown", "claim": UI_CLAIM}, findings
    if body is None:
        return {"status": "not-checked", "ui_files": sorted(ui_files), "claim": UI_CLAIM}, findings
    captures = _captures(body)
    if not captures:
        if needed:
            _finding(findings, "ui-evidence-missing", "decide", ("pr", "merge"),
                     "the change alters what users see, but the PR body has no before: or after: capture line")
            return {"status": "incomplete", "captures": 0, "claim": UI_CLAIM}, findings
        return {"status": "not-applicable", "captures": 0, "claim": UI_CLAIM}, findings
    before = [c for c in captures if c["kind"] == "before" and c["image"]]
    after = [c for c in captures if c["kind"] == "after" and c["image"]]
    if len(after) != len(before):
        only = "after" if len(after) > len(before) else "before"
        _finding(findings, "ui-evidence-%s-only" % only, "decide", ("pr", "merge"),
                 "%d before and %d after captures: each capture needs its partner, a real baseline for the before and the "
                 "changed view for the after" % (len(before), len(after)))
    for number, (old, new) in enumerate(zip(before, after), 1):
        differing = ["%s: %s against %s" % (f, old["labels"][f], new["labels"][f]) for f in VIEW
                     if f in old["labels"] and f in new["labels"] and old["labels"][f].casefold() != new["labels"][f].casefold()]
        absent = ["%s is missing %s" % (side, f) for side, item in (("before", old), ("after", new))
                  for f in VIEW + ("revision",) if f not in item["labels"]]
        if differing:
            _finding(findings, "ui-evidence-mismatch", "decide", ("pr", "merge"),
                     "pair %d compares different views: a before and an after share scenario, viewport, theme and state"
                     % number, differing)
        if absent:
            _finding(findings, "ui-evidence-unlabelled", "decide", ("pr", "merge"),
                     "pair %d: every capture names its scenario, viewport, theme, state and the revision it was taken at"
                     % number, absent)
    return {"status": "incomplete" if findings else "complete", "captures": len(captures), "pairs": min(len(before), len(after)),
            "claim": UI_CLAIM}, findings


# ------------------------------------------------------------------ the gate
def _delivery_state(state, pr, unpushed):
    if pr["state"] == "merged":
        return "merged"
    if pr["state"] == "open":
        return "pr-open"
    if state["upstream"] and state["ahead"] == 0 and not (state["changed"] or state["untracked"]):
        return "pushed"
    if unpushed:
        return "committed"
    if state["changed"] or state["untracked"] or state["conflicts"]:
        return "uncommitted"
    return "unknown" if not state["upstream"] else "pushed"


def gate(status, remotes=None, log=None, pr=None, rules=None, repo=None, diff=None, receipts=None,
         default_branch=None, grant=(), body=None, ui_change=False):
    grant = list(grant or [])
    unknown_steps = [s for s in grant if s not in STEPS]
    if unknown_steps:
        raise UsageError("unknown step in --grant: %s (steps: %s)" % (", ".join(unknown_steps), ", ".join(STEPS)))
    findings = []
    state = parse_status(status)
    branch = state["branch"]
    target = state["upstream"].split("/", 1)[1] if state["upstream"] and "/" in state["upstream"] else branch
    remote_name = state["upstream"].split("/", 1)[0] if state["upstream"] and "/" in state["upstream"] else None

    # local state
    if state["conflicts"]:
        _finding(findings, "conflicts", "block", STEPS, "unmerged paths", state["conflicts"], readiness=True)
    if state["detached"]:
        _finding(findings, "detached-head", "block", ("push", "pr"), "HEAD is detached: there is no branch to push")
    if state["changed"] or state["untracked"]:
        _finding(findings, "dirty-tree", "decide", LATER,
                 "uncommitted or untracked paths: a push carries only commits, so the receipts may cover content that "
                 "is not pushed; commit, leave out or remove each one",
                 ["changed: " + p for p in state["changed"]] + ["untracked: " + p for p in state["untracked"]])
    unpushed = None
    if state["upstream"]:
        if state["ahead"] is None:
            _finding(findings, "upstream-gone", "unknown", LATER, "the upstream %s is gone or unreadable"
                     % state["upstream"])
        else:
            unpushed = state["ahead"]
            if state["behind"]:
                _finding(findings, "behind-upstream", "block", ("push",),
                         "%d commits on %s are not here: integrate first (a new change), never force"
                         % (state["behind"], state["upstream"]))
    else:
        if branch and not state["detached"]:
            _finding(findings, "no-upstream", "info", ("push",), "%s has no upstream: a push creates it" % branch)
        if log is not None:
            unpushed = len([line for line in log.splitlines() if line.strip()])
    if unpushed:
        _finding(findings, "unpushed-commits", "info", (), "%d local commit%s not on the remote"
                 % (unpushed, "" if unpushed == 1 else "s"))

    # remotes and the push target
    remote_list = parse_remotes(remotes) if remotes is not None else None
    if remote_list is None:
        _finding(findings, "remote-unknown", "unknown", ("push", "pr", "release"), "git remote -v was not saved")
    elif not remote_list:
        _finding(findings, "no-remote", "block", ("push", "pr", "merge", "release"), "the repository has no remote")
    elif remote_name and remote_name not in {r["name"] for r in remote_list}:
        _finding(findings, "remote-unknown", "unknown", ("push",), "the upstream's remote %s is not listed"
                 % remote_name)
    if default_branch is None:
        _finding(findings, "default-branch-unknown", "unknown", ("push", "pr"),
                 "the default branch was not given: a push to it cannot be ruled out")
    elif target and target == default_branch:
        _finding(findings, "default-branch-target", "decide", ("push", "pr"),
                 "the push target is the default branch %s: that needs a grant naming it (a PR needs another branch)"
                 % default_branch)

    # protection
    protection = {name: read_rules(entries) for name, entries in sorted((rules or {}).items())}
    target_rules = protection.get(target) if target else None
    if target_rules is None or not target_rules["known"]:
        _finding(findings, "protection-unknown", "unknown", ("push",),
                 "branch protection for %s was not read (save the protection or rules response, or %s=none for a "
                 "remote without a protection system)" % (target or "the target", target or "BRANCH"),
                 target_rules["sources"] if target_rules else [])
    elif target_rules["protected"]:
        _finding(findings, "protected-target", "decide", ("push",),
                 "%s is protected: never push to it directly or bypass it; a pull request is the usual path" % target,
                 ["required checks: " + (", ".join(target_rules["required_checks"]) or "none named")])

    # pull request
    pr_summary, pr_findings = read_pr(pr, state["head"], protection)
    findings += pr_findings
    if pr_summary["base"]:
        base_rules = protection.get(pr_summary["base"])
        if base_rules is None or not base_rules["known"]:
            _finding(findings, "base-protection-unknown", "unknown", ("merge",),
                     "protection and required checks for the base %s were not read" % pr_summary["base"])

    # repository automation
    automation = scan_repo(repo) if repo else []
    if repo:
        findings += automation_findings(automation)
    else:
        _finding(findings, "automation-unknown", "unknown", ("push", "pr", "release"),
                 "the repository's workflows and merge bots were not read (--repo)")

    # release metadata and secrets
    files = parse_diff(diff) if diff is not None else {}
    release, release_list = release_findings(files, repo) if diff is not None else (
        {"new_versions": [], "version_files": [], "changelog_changed": None, "changelog_files": [], "fragment": False},
        [])
    findings += release_list
    findings += secret_findings(files)
    if diff is None:
        _finding(findings, "diff-unknown", "unknown", ("commit",) + LATER,
                 "no saved diff: secrets and release metadata were not checked", readiness=True)

    # receipts
    receipt_summary, receipt_list = receipt_findings(receipts)
    findings += receipt_list

    # the PR body's before and after captures (DS-4)
    ui_summary, ui_list = ui_evidence(body, ui_change, [p for p in files if UI_FILE.search(p)])
    findings += ui_list

    # steps
    order = {"block": 3, "decide": 2, "unknown": 1, "info": 0}
    steps = {}
    for step in STEPS:
        relevant = [f for f in findings if step in f["steps"] and f["level"] != "info"]
        worst = max((order[f["level"]] for f in relevant), default=0)
        pre = {3: "blocked", 2: "needs-decision", 1: "cannot-tell", 0: "clear"}[worst]
        steps[step] = {"granted": step in grant, "status": pre if step in grant else "not-granted",
                       "preconditions": pre, "findings": [f["id"] for f in relevant]}
    ready_list = [f for f in findings if f["readiness"]]
    readiness_worst = max((order[f["level"]] for f in ready_list), default=0)
    readiness = {"verdict": "not-ready" if readiness_worst >= 2 else "unknown" if readiness_worst == 1 else "ready",
                 "findings": [f["id"] for f in ready_list]}
    granted = [steps[s]["status"] for s in grant]
    if readiness["verdict"] == "not-ready" or any(s in {"blocked", "needs-decision"} for s in granted):
        verdict, code = "stop", 1
    elif readiness["verdict"] == "unknown" or "cannot-tell" in granted:
        verdict, code = "cannot-tell", 2
    else:
        verdict, code = "clear", 0
    return {"format": FORMAT, "state": state, "remotes": remote_list, "pr": pr_summary, "protection": protection,
            "automation": automation, "release": release, "receipts": receipt_summary, "ui_evidence": ui_summary,
            "findings": findings,
            "readiness": readiness, "steps": steps, "grant": grant,
            "delivery_state": _delivery_state(state, pr_summary, unpushed), "verdict": verdict, "exit_code": code,
            "claim": CLAIM}


# ------------------------------------------------------------------ command line
def _load_text(path, inputs, label):
    path = pathlib.Path(path)
    if not path.is_file():
        raise UsageError("%s: not a file: %s" % (label, path))
    raw = path.read_bytes()
    if len(raw) > LIMIT:
        raise UsageError("%s: input exceeds 16 MiB: %s" % (label, path))
    inputs.append({"input": label, "path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
    return raw.decode("utf-8", errors="replace").lstrip("﻿")


def _load_json(path, inputs, label):
    if path == "none":
        inputs.append({"input": label, "path": "none"})
        return "none"
    text = _load_text(path, inputs, label)
    try:
        return json.loads(text)
    except ValueError:
        return {"errors": ["not JSON"]} if label == "pr" else {"message": "not JSON"}


def main(argv=None, out=None):
    out = out or sys.stdout.write
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.error = lambda message: (_ for _ in ()).throw(UsageError(message))
    parser.add_argument("--status", required=True)
    parser.add_argument("--remotes")
    parser.add_argument("--log")
    parser.add_argument("--pr", help="a saved gh or GraphQL JSON file, or none")
    parser.add_argument("--rules", action="append", default=[], metavar="BRANCH=FILE|none")
    parser.add_argument("--repo")
    parser.add_argument("--diff")
    parser.add_argument("--receipts")
    parser.add_argument("--default-branch")
    parser.add_argument("--body", help="the saved pull request body (DS-4): its before and after captures are checked")
    parser.add_argument("--ui-change", action="store_true", help="the change alters what users see (DS-4)")
    parser.add_argument("--grant", default="", help="comma-separated steps the user granted: " + ", ".join(STEPS))
    parser.add_argument("--output", help="also write the JSON to this new file (exclusive create)")
    try:
        args = parser.parse_args(argv)
        inputs = []
        rules = {}
        for item in args.rules:
            name, sep, source = item.partition("=")
            if not sep or not name or not source:
                raise UsageError("--rules needs BRANCH=FILE or BRANCH=none")
            rules.setdefault(name, []).append(_load_json(source, inputs, "rules " + name))
        if args.repo and not pathlib.Path(args.repo).is_dir():
            raise UsageError("--repo: not a folder: " + args.repo)
        report = gate(
            _load_text(args.status, inputs, "status"),
            remotes=_load_text(args.remotes, inputs, "remotes") if args.remotes else None,
            log=_load_text(args.log, inputs, "log") if args.log else None,
            pr=_load_json(args.pr, inputs, "pr") if args.pr else None,
            rules=rules, repo=args.repo,
            diff=_load_text(args.diff, inputs, "diff") if args.diff else None,
            receipts=_load_json(args.receipts, inputs, "receipts") if args.receipts else None,
            default_branch=args.default_branch,
            grant=[s.strip() for s in args.grant.split(",") if s.strip()],
            body=_load_text(args.body, inputs, "body") if args.body else None, ui_change=args.ui_change)
        report["inputs"] = inputs
        text = json.dumps(report, indent=2) + "\n"
        if args.output:
            try:
                with pathlib.Path(args.output).open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(text)
            except FileExistsError:
                raise UsageError("output exists; never replaced: " + args.output)
            except OSError as exc:
                raise UsageError("cannot write output: " + str(exc))
        out(text)
        return report["exit_code"]
    except UsageError as exc:
        sys.stderr.write("shipgate.py: " + str(exc) + "\n")
        return 64


if __name__ == "__main__":
    sys.exit(main())
