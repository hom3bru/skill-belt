# Secrets and credentials

The core rule stands in every mode: never acquire, test or probe a credential (core `authority.md`). This page says how to find, describe and protect them.

## A credential in source is a disclosure path

Count any credential in a file under the audited tree, wherever it sits:

- test files and fixtures;
- constants nothing uses any more;
- hidden environment and tool files (`.env`, `.npmrc`, `.pypirc`, shell profiles);
- JSON service-account credentials;
- private keys and keystores;
- notebooks, logs and build output that were committed.

Judge it by its format and how the code uses it, not by the folder it sits in. Not findings: public keys and certificates, documented placeholders (`YOUR_KEY_HERE`, `xxxx`, `changeme` in an example), hashes, and identifiers that grant nothing on their own.

Never check whether a credential is live, even under a grant, by calling its service or through a scanner's live validation (Betterleaks' `--validation`; TruffleHog, Kingfisher and detect-secrets validate by default, so pass their off switch): leave it off and say the result is unverified. Describe a secret only by its key name and location (file and line), never its value, in the record, the report and every message; a masked prefix is still part of the value.

## Running a secret scanner

The scanned project never configures its own scan: pass a reviewed config, turn inline allow comments off, and list its configs, ignore files, baselines and allow comments (`secaudit.py suppressions ROOT`) as scope to review, never as settled. Each tool's flags, completion signal and receipt: [scanners](scanners.md).

## Before captured text leaves the machine

Before captured text (a log, a transcript, a diff, a scope listing) goes to an outside model or service:

1. Scan it on the device for secrets with an installed secret linter, and for structured personal data, validating card and account numbers by their checksum where the format has one.
2. Record each hit's source and its severity, mask the value, and never store the raw one.
3. Treat a scan with no hits as inconclusive.

Core `guards.md` already removes secrets and private data before a note leaves; this adds the on-device scan and its record. Before writing a receipt, note or brief, run `secaudit.py redact FILE`: auth schemes and cookie names stay; values under secret-named keys go.

## Asking the user

Never ask the user to paste a credential into the conversation: the transcript keeps it. Name the file, environment variable or prompt where they place it themselves.

## What to check in the target

- **Handles, not values.** An agent should receive a secret as a reference that works once, for one tool and one conversation, inside a short window; never the value. Check every channel that could show a typed secret back to a model or a log: the accessibility tree, screenshots, page text, live views and logs. A typed password that appears in a page-text dump is a finding.
- **Credential files.** Code that stores credentials should not create the file when it only reads; should create its private directory on the first write; should refuse symlinks; should write atomically with owner-only permissions; and should cap how much it reads. A symlinked config that is followed, or an unbounded read, is a finding.
- **Destinations.** A credential goes only to the service it belongs to, and that service accepts only its own kind of key ([intake](intake.md)).
- **Remote URLs.** Credentials inside a remote URL, a clone URL or a log line are a disclosure; scope receipts and reports never carry them.
