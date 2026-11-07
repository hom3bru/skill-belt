# Scanners

Deterministic scanners give evidence, never a verdict (SKILL.md rule 5). Use only what is installed: Betterleaks/gitleaks, osv-scanner, Semgrep CE, Trivy or Grype with Syft, Checkov, OpenSSF Scorecard. Which to install is the user's call; install none without a grant.

## Running a secret scanner

Betterleaks first, else gitleaks, if installed. Record each run in `scope.secret_scans`: tool, version, command, config file, scope, exit, log, result.

- Pass `--exit-code 2` and `--redact`. Exit 1, no summary line or "partial scan" reads not-run.
- Scan the working tree (`dir`) and the full history (`git`); one alone is partial, since a deleted secret stays in history.
- Suppress by fingerprint or path, never by the value; `check` flags a literal high-entropy allow-list entry.
- A history scan sees only the refs fetched, down to the clone's depth, so a shallow clone cannot show that a secret is absent. Record `shallow` (from `git rev-parse --is-shallow-repository`) and the `refs` scanned; a shallow history reads partial.

`check` reads completion only from gitleaks and Betterleaks logs. Record another tool's run as not-run, and cite its own signal from the table below in the findings.

## The project never configures its own scan

When you audit or vet a project, its own files must not decide what the scan reports. Left to its defaults, a scanner reads them from the folder it scans.

- Pass `--config` with a config you reviewed. Without it, Betterleaks loads `.betterleaks.toml` or `.gitleaks.toml` from the scanned folder, and gitleaks loads `.gitleaks.toml`, unless a config variable is set.
- Pass `--ignore-gitleaks-allow`, so inline `gitleaks:allow` and `betterleaks:allow` comments hide nothing; for TruffleHog, pass `--no-ignore-tag`.
- Betterleaks and gitleaks always load the scanned folder's ignore file (`.betterleaksignore`, `.gitleaksignore`), and no flag stops it: review its entries, or scan a copy without it.
- Run `secaudit.py suppressions ROOT`. It reads files, runs nothing, and lists every scanner config, ignore file and baseline the project holds and every inline allow comment, by path and line, never the line's text. Each is scope to review, never settled: with a secret scan in the record, `check` wants a record anchored at each (`<path>`, or `<path>::<marker>` for comments) and reports the rest as `suppression-unreviewed`.

`check` also flags a gitleaks or Betterleaks command without `--config` (`scan-target-config`) or without `--ignore-gitleaks-allow` (`scan-inline-allow`).

## Live checks stay off

Live validation sends a found credential to its service, so westack never uses it, even under a grant ([secrets](secrets.md)). Betterleaks validates only with `--validation`. TruffleHog, Kingfisher and detect-secrets validate by default, so pass their off switch. `check` flags a receipt that validates or leaves the default on (`scan-validation`).

## Per tool

What was checked at the pinned releases ([provenance](../provenance/donors.json)). "(list)" marks a claim from the reviewed scanner list that was not checked.

| tool | live checks off | complete scan | the project's own suppressions | history and scope |
| --- | --- | --- | --- | --- |
| Betterleaks 1.9.0 | off unless `--validation` | exit code and log together, with `--exit-code 2` | `.betterleaks.toml` or `.gitleaks.toml` without `--config`; the ignore file always; inline allow unless `--ignore-gitleaks-allow` | `git` mode reads every fetched ref (`git log --all`) |
| gitleaks 8.30.1 | no validation | as Betterleaks | `.gitleaks.toml` without `--config`; `.gitleaksignore` always; `gitleaks:allow` unless `--ignore-gitleaks-allow` | not checked |
| TruffleHog 3.99.7 | on by default: pass `--no-verification`, and `--no-update` to stop its update check | `--fail` exits 183 on findings; a scan error fails the run only with `--fail-on-scan-errors` | `trufflehog:ignore` comments unless `--no-ignore-tag` | per source mode |
| Kingfisher 2.16.0 | on by default: pass `--no-validate` (findings then read `not_attempted`); `--no-update-check` (list) | 0, 200 (findings) and 205 (validated findings) can each come with partial coverage: read `scan_partial` and `scan_failed` in the audit summary | `kingfisher.yaml` only when passed with `--config`; it is never found on its own | per source mode |
| detect-secrets 1.5.0 | on by default: pass `-n` or `--no-verify` | not checked | `pragma: allowlist secret` comments (also `nextline`); a committed baseline, `.secrets.baseline` in its examples | the working tree; `--all-files` goes past tracked files (list) |
| Secretlint 13.1.0 | none found | not checked | `.secretlintrc.*`, `.secretlintignore` and each folder's `.gitignore`; `secretlint-disable` comments when its comment rule is configured | never reads `.git`; skips gitignored files such as `.env` unless `--no-gitignore`; masks secrets by default |

`suppressions` lists every file and comment named in the fourth column except `.gitignore`, which every project has: read it when Secretlint runs.

Not carried: a ranking of which scanner to install (the user's call), Betterleaks 2 (a prerelease with other flags and report shape) and Titus (not installed here).
