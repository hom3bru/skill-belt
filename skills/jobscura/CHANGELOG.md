# Changes

## 0.5.0 - Full-cycle toolkit with deterministic helpers

Round-three adopt-adapt additions (independently reimplemented; no donor code or prose copied):

- J1–J4: masked sensitive-identifier and leftover-placeholder warnings, deterministic chronology
  review and decomposed-accent extraction checks.
- J5–J6: evidence-bound proficiency atoms and numeric direction-mismatch review flags.
- J7–J8: mixed-script and variation-selector evasion signals, additional hidden CSS and narrow
  instruction patterns; Unicode title comparison with explicit unavailable comparisons.
- J9–J12: independently usable sub-skill safety guards, defensible years/self-ratings,
  personal-detail conventions and role-specific eligibility/language gates.
- J13–J18: stage-specific interviewer questions, structured debriefs, likely-concern registers,
  salary-stage handling, a paste-back practice log and recurring recorded requirement gaps.
- J19: helper documentation, regression controls and refreshed public byte inventories.

Transfers from a second adopt-adapt review of the repositories that shaped Jobscura:

- A1: check entity/date combinations within evidence windows (SimplyApply; AGPL idea only).
- A2: distinguish tool use from implementation or ownership (Remotivated/job-hunt-skills; MIT idea).
- A3: bind grounding ledgers to input bytes and text units (earlier provenance design and JobCtrl; AGPL idea only for JobCtrl).
- A4: recognize multilingual and letter-spaced headings and measure garbled glyphs (Resume-Matcher, Apache-2.0, and career-ops, MIT; ideas).
- A5: distinguish location variants from potential reposts (career-ops-hq/career-ops; MIT idea).
- A6: flag interstitials in saved postings and captures (JobNavigator; MIT idea, detection only).
- A7: check supplied answers offline without filling forms (form-filler-ai, no licence, idea only; jobclaw-skills and give-me-job, MIT ideas).
- A8: guard offline imports and submission boundaries with an injected-import control (MS-Jahan/job-apply-kit; MIT idea only).
- A9: strengthen sourcing, claim credit, private story provenance and channel ownership (claude-resume-kit, Remotivated, career-ops, give-me-job and reactive-resume, MIT ideas; waddington, Apache-2.0 idea; jobapply, idea only).
- A10: document the transfers and refresh distribution hashes; no donor code or prose copied.

Fixes from an independent Codex audit:

- R1. DOCX privacy checks cover revisions, comments and invisible text in headers, footers and notes.
- R2. Tracker comparisons report raw and unidentified rows, require review for incomplete identities,
  and block a decrease in unidentified rows.
- R3. Applicant-paid fees remain flagged when a posting promises reimbursement or refunds.
- R4. Board feeds reject malformed vendor containers and API-error envelopes before comparison.
- R5. Previous board snapshots must match the schema version, vendor, board and employer.
- R6. Calendar events preserve existing ID-bearing UIDs, use URLs for ID-less rows and report skipped
  rows without stable identity. ID-less events get new UIDs in this unreleased version. Duplicate
  event identities block export.
- R7. Leadership claims remain in the grounding ledger when related evidence leaves authority unclear.
- R8. Tracker checks flag backwards application milestones and require review for terminal-state changes.
- R9. Out-of-range feed timestamps produce blocked JSON errors.
- R10. Offer comparisons reject cliffs beyond the vesting term and identify the affected offer.

Follow-up review fixes:

- Preserve applicant-payment signals when the instruction and its object span sentence boundaries.
- Skip and report malformed URL-only calendar rows while exporting reminders for valid rows.
- Restore the explicit header-mapping block when neither tracker export contains record IDs.

Fixes:

- Link guards no longer reject paths whose *parent folders* are operating-system aliases
  (for example macOS `/var` to `/private/var`, where every temporary folder lives) or files that
  are cloud-sync placeholders. Previously both made context loading and packet input fail. A file
  that is itself a symlink or junction is still refused, and so is any link inside a documents
  plan's folder or inside a packet. Containment is still decided on resolved paths.
- Packet validation checked every ancestor except one for links. It now checks exactly the
  components inside the packet.
- Tracker matching recognises common real-world headers (`Organization`, `Job Link`, `Job ID`,
  `Tracker ID`, `Req #` and others) in a second tier that never changes how trackers using the
  original headers are read. Spreadsheet `HYPERLINK` formulas resolve to their URL. Requisitions
  now compare without regard to letter case or whitespace. A secondary job ID can match, but it
  never blocks a URL match.
- HTML capture now separates `<br>`, list, table and heading text into lines.
- Removed owner-specific settings that remained in the public tracking procedure (a dated
  workflow update, spoken-briefing and three-item text rules, fixed cadences). They are now
  documented defaults that private context can override.
- Replaced host-specific "Library" references with generic document tools.
- The package version is now declared once, in `SKILL.md`; plugin metadata must agree with it.
- The context validator reports whether the selected IANA time zone is available on the host.
- The packet helper writes UTF-8 to stdout and stderr. On a default Windows pipe (cp1252), a
  non-ASCII employer name used to turn a valid match into a false "blocked" result. A corrupt XLSX
  tracker or a CSV field over 128 KB now produces a JSON block message instead of a traceback.

Fixes from an independent review of the new helpers (each covered by a regression test):

- Every helper keeps the exit-2 JSON contract for corrupt, encrypted or malformed inputs.
- DOCX inspection caps the number of parts and the total uncompressed size.
- Text in `noscript` and `template` elements is scanned as hidden text.
- Coverage keeps short technical terms (R, C#, AI) and brand names such as Workday. A requirement
  with nothing left to match is reported as `not_assessable` instead of being dropped.
- A status of "Not applied" stays active.
- Lookalike SuccessFactors domains are not trusted.
- Employer-paid training or equipment is no longer flagged as a payment scam.
- Pull-request review fixes:
  - A money claim whose currency differs from the evidence is no longer marked supported.
  - Requirements outside recognised sections stay in the coverage matrix, labelled `unclassified`.
  - `<w:vanish w:val="0|false|off"/>` counts as visible text.

Additions:

- Three workflows: `opportunity-discovery`, `networking-outreach`, `offer-negotiation`.
- `posting_intel.py`: schema.org JobPosting extraction, recognition of the posting's ATS
  (vendor, board and job ID, with the public JSON endpoint where one exists), required and
  preferred requirement extraction, pay, work arrangement, sponsorship, the employer's AI-use
  stance, hidden and AI-directed instructions (canaries, prompt injection, Unicode tag smuggling,
  HTML comments), scam signals and freshness.
- `grounding.py`: a claim ledger that checks numbers in context so that a real figure cannot be
  credited to the wrong project, with authority-escalation and superlative flags, plus a
  requirement coverage matrix that suggests only terms supported by evidence.
- `ats_lint.py`: DOCX/PDF parse safety and hygiene checks (tables, text boxes, columns, contact
  details only in the header, tracked changes, comments, hidden or white text, macros, image-only
  or encrypted PDFs, metadata).
- `deadlines.py`: time zone and daylight-saving aware countdowns, reminder windows deduplicated
  against recorded sends, check cadence, and refusal of ambiguous dates.
- `offer_compare.py`: multi-year pre-tax comparison with vesting, cliffs, back-weighted schedules,
  options at their spread, and equity sensitivity.
- Shared [integrity and safety](references/integrity-and-safety.md) rules, an
  [output formats](references/output-formats.md) page and a [helper index](references/helpers.md).
- Context schema version 2, with optional `monitoring` and `search` preferences. Version 1 files
  still load.
- A behavioural eval suite (11 cases) for `claude plugin eval`.
- Trigger-oriented descriptions for every workflow.
- Packet helper 0.3.0.

Transfers from an adopt-adapt review of open-source job-search tools. Only ideas were taken, each
reimplemented independently with the standard library; no donor code was copied or run.

- `board_feed.py` (idea: career-ops' provider contract and normalised job record, MIT). It
  normalises saved Greenhouse, Lever, Ashby and SmartRecruiters feeds, screens them, and marks
  tracked roles and possible reposts. It adds what career-ops lacks: new and disappeared postings
  between snapshots.
- `tracker_diff.py` (ideas: the Codex 0.5.0 draft's conservation check, plus repost detection in
  career-ops and JobFunnel). It blocks tracker edits that lose records, identities, columns or
  application history, and lists repost candidates.
- `deadlines.py --ics` (idea: the RFC 5545 iCalendar standard). It writes an importable calendar
  with stable UIDs and future-only alarms, so reminders need no scheduler.
- Pay annualisation and a pay-floor check against `search.min_base_pay` in `posting_intel.py`
  (idea: JobSpy's interval factors, MIT).
- A resume parse preview in `ats_lint.py` (idea: OpenResume's rule-based parser, AGPL-3.0; idea only,
  with independently written rules and scores).

## 0.4.1 - Windows path containment

- Resolve output and toolkit paths before comparing containment, including Windows short aliases.
- Reject internal private context before opening it; retain repository and linked-path guards.
- Add alias rejection and outside-output positive controls; preserve schema version 1 and package identity.

## 0.4.0 — Jobscura

- Rename the public product to Jobscura and add a discoverable Skill Belt router.
- Retain the package identifier and six existing skill names for update continuity.
- Preserve 0.3.0 tracking, intake, history, writing, packet and interview rules.
- Move user-specific routing and timezone choices into explicit private context.
- Add a closed versioned schema, fictional example and read-only context validator.
- Remove private author contact metadata and omit the private audit archive.
- Generate the synthetic XLSX test workbook at runtime from public fictional data.
- Correct packet validation's Windows path representation and reject linked input ancestors (helper 0.2.1).
- Add deterministic allowlisted plugin packaging and privacy rejection tests.

Earlier versions were released under the name Application Assistant. This edition
does not install a scheduler or alter any existing host automations.
