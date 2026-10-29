<!-- Each check names its public source; per-donor evidence for the risk codes is archived in historical-findings.md section B. -->
# Due-diligence block (repos and packages)

Pin everything to the commit SHA you read. Record the command or URL used for each line.

On either route, skip Scorecard, OSV, maintenance and registry lines (and the whole-tool fit score) when nothing executable or copyable from the donor enters the recipient (an idea-only transfer), or when the whole tool is already DISCARD on a hard gate; write `not applicable (reason)`. Licence and source identity are still checked, and any plan that names a package or copies code needs the full block.

| Check | How (read-only, no install on the recipient machine) | What it does not prove |
|---|---|---|
| OpenSSF Scorecard | `https://api.securityscorecards.dev/projects/github.com/<o>/<r>`. Compare its `repo.commit` with your pinned SHA; if they differ, say so. | Code quality or fitness for the recipient |
| Vulnerabilities | `POST https://api.osv.dev/v1/query` with exact ecosystem/name/version. Check `MAL-` IDs separately. | Absence of unknown bugs |
| License | Read the LICENSE file at the SHA, and the header of every file you would salvage. GitHub "NOASSERTION" usually means several license blocks (feedparser: BSD-style code plus a separate docs license). No license is not permission. AGPL is not an automatic DISCARD, but whole-tool reuse needs the user's call. | Legal clearance |
| Maintenance | Last commit, last release, open-issue trend over 12 months (GitHub API). CHAOSS Contributor Absence Factor if bus-factor matters. | Future maintenance |
| Registry existence | For every package a plan names: `https://pypi.org/pypi/<name>/json` or `https://registry.npmjs.org/<name>`. 404 means the plan names a package that does not exist (slopsquatting guard; USENIX Sec '25 found 5.2% / 21.7% hallucinated package names). | That the package is safe |

## Donor-risk audit (required for skill / hook / MCP / agent-config donors, recommended for all)
Record `ledger.donor_risks[] = {code, evidence, status: present|absent|unknown, scope}`. Any `present` risk on the salvaged mechanism forces ADAPT-with-prerequisite (fix named) or excludes that part; never ADOPT. Score penalty: one `present` high risk = −1 on the whole-tool score; two or more = −2 (single strongest penalty rule still applies).

For skill, hook, MCP, plugin and agent-config donors, put a compact **behavior inventory** in the existing `ledger.map.content`, with support in `map.evidence` and unread or dynamic paths in `map.limitations`. For each relevant entrypoint, connect its host and activation conditions to commands or delegation, file reads/writes and persistence, network destinations and data, consent/opt-out controls, and pinned source evidence. Distinguish automatic execution, agent instructions, optional actions and inert links. Follow load-bearing helpers, configuration and browser assets, including conditions that disable the behavior; source wiring is not observed execution. State coverage and unknowns rather than claiming every path was scanned. Include instruction size only when useful for assessing footprint. Concise prose or a table is enough; HTML and whole-repository inspection are not requirements. Reuse the existing risk rows without repeating their findings. Examples of where each risk was seen in earlier reviews are history (`historical-findings.md` section B where an edition ships it), not evidence about a new donor.

| Code | What to look for |
|---|---|
| FAIL-OPEN-GUARD | Guard/hook that lets everything through on error or broken state |
| RUNNER-MISCOUNT | Broken/crashing tests not counted; 0 tests → exit 0 |
| NO-ASSERT-VERIFIED | "verify" prints `verified:true` with no result assertions |
| SILENT-SKIP-PASS | Optional lane skipped silently, run still PASS |
| HARDCODED-CLAIM | Report counts/booleans are literals, not measured |
| HOOK-AUTO-ANSWER | Hook answers user questions; machine choices logged as the user's |
| HOOK-APPROVAL-UNLOGGED | Hook-granted approvals with no durable, attributed record |
| ENV-LEAK | Full parent env (API keys) passed to hooks/child tools |
| UNPINNED-SESSION-INSTALL | Installs packages at session start without version/hash |
| INSTRUCTION-TRUNCATION | Shared size budget cuts most specific file first, warn-only |
| OVERRIDE-FILE | Override file silently replaces instructions |
| COMMENT-SUPPRESSION | Repo-controlled text can suppress reviewer findings |
| CLIENT-CONFIG-WRITE | Donor writes itself into other AI clients' configs |
| UNBOUNDED-STOP-HOOK | Stop hook can loop forever |
| TAG-PINNED-ACTIONS | Workflow actions pinned to tags, not SHAs |
| HAND-PATH-FILTERS | CI path filters maintained by hand, drift from import graph |
| PUBLISH-NO-HASH | Publish/verify compares names, not tarball hash |
| NO-TEST-TIMEOUT | No per-test timeout; a hang never fails |
| WARN-ONLY-LINT | Safety lint can only warn |
| MISSING-HOOK-PASSES | Hook checker `continue`s on a missing hook |
| PERMISSIVE-DEFAULT | Unknown config value → most permissive |
| AUTO-EXEC | SessionStart/project hooks, project MCP, PATH/env-file writes run on open |
| INSTRUCTION-TAMPER | Tool rewrites agent instruction files |
| AGENT-ADDRESSED-TEXT | Donor text gives imperatives to agents |
| DONOR-STEERED-MAP | Donor steers the architecture map (`.devin/wiki.json`), or map is unpinned |
| ERROR-BODY-SUCCESS | 200 / `is_error:false` counted as success |
| SELF-ATTESTED-EVIDENCE | Pass record writable by hand, no raw-output hash |
| CONTINUE-ON-ERROR | `|| true` / continue-on-error / warn-and-ship on gating steps |
| UNRUN-SUITE | Tests built/committed but run by no runner |
| ABSENT-METRIC-PASS | Missing metric defaults to pass/1.0/0 |
| RATCHET-LOWERED | Floor/threshold lowered or only convention-enforced |
| REVIEW-MARKED-ON-FAILURE | Work marked "reviewed/done" even when the review call failed |
| DROPPED-FILES-MARKED | File cap drops files but the range is still marked reviewed; top-N findings only |
| LAST-COMMIT-ONLY | Only the last of several commits is reviewed |
| BASE-URL-EXFIL | Env base-URL override sends diffs + API key/token to another host |
| MATCHER-MATCH-ALL | Invalid matcher silently becomes match-all |
| UNQUOTED-PATH-SUBST | Plugin path substituted into a shell command unquoted |
| FORCED-MANAGED-HOOK | Hooks always trusted and undisableable (managed / allowlisted builtin) |
| HOOK-CONFIG-WARN-ONLY | Broken hook config only warns |
| HOOK-RUN-UNRECORDED | No lasting record of which hook ran or what it decided |
| CONFIG-HASH-ONLY-TRUST | Hook trust hash covers config, not the script it runs |
