# Offline helpers

Jobscura's helpers handle the work where model judgment is least reliable: date arithmetic, money
arithmetic, structured-data parsing and checking claims against evidence. They need Python 3.10 or
newer and use only the standard library. They make no network calls. They read only the files you
name and never change them. The only thing they write is a new `--out` file, and they refuse to
overwrite one that exists.

Every command prints JSON to stdout. A blocked command exits with code 2 and prints a JSON error to
stderr, so check `status` rather than relying on the exit code alone. Run each command from the
Jobscura directory, or point it at the helper's absolute path. If no executor is available, do the
same review by hand and say that the helper did not run.

| Need | Command | Key output |
| --- | --- | --- |
| Understand a posting | `python -B scripts/posting_intel.py analyze --input posting.html --url URL --employer NAME --observed-at ISO` (or `--capture DIR`) | ATS vendor and job ID, schema.org JobPosting fields, required and preferred items with line numbers, pay, remote/hybrid, sponsorship, employer AI-use stance, hidden and AI-directed instructions, scam signals, freshness |
| Check a draft's claims | `python -B scripts/grounding.py claims --draft draft.docx --evidence cv.docx notes.md` | Per-sentence ledger: `supported`, `present_in_evidence`, `found_elsewhere` (attribution risk), `not_found`; flags for authority escalation and unsupported superlatives |
| Map requirements to evidence | `python -B scripts/grounding.py coverage --posting posting.html --evidence cv.docx [--draft letter.docx]` | Each requirement marked `addressed`, `evidence_not_used`, `addressed_without_found_evidence` or `no_evidence_found`, plus supported terms the draft leaves out |
| Check a file before upload | `python -B scripts/ats_lint.py Resume.docx` | Blockers (tracked changes, comments, hidden or white text in the body, headers, footers and notes, macros, image-only or encrypted PDF), warnings (tables, text boxes, columns, contact details only in the header), metadata, and a parse preview for DOCX and text files: the name, contact details, section titles, dated roles and education lines a simple parser would probably read |
| Plan deadlines and checks | `python -B scripts/deadlines.py --tracker export.csv --context /abs/context.json [--as-of ISO] [--ics deadlines.ics]` | Days and hours remaining in the user's time zone, reminder windows now due (minus those already sent), status checks due, unresolved dates, morning digest. `--ics` writes a calendar file for active dated roles with stable IDs or URLs and lists rows without either in `calendar.skipped`. Each event has a 09:00 alarm on each future reminder window. Existing ID-bearing UIDs stay stable. |
| Screen an employer's job board | `python -B scripts/board_feed.py --feed saved.json --company NAME [--board SLUG] [--previous last.json] [--tracker export.csv] [--context ctx.json] [--out this.json]` | Normalised postings from a saved Greenhouse, Lever, Ashby or SmartRecruiters response; title and location screening; tracked and possible-repost flags; new, changed and disappeared since the previous run |
| Check a tracker edit before saving | `python -B scripts/tracker_diff.py --before old.csv --after new.csv` | `blocked` for removed records, duplicate IDs or identities, a changed employer, requisition or URL, dropped columns, backwards application milestones or fewer unidentified rows; incomplete identities, reopened terminal states, changed terminal decisions, cleared values and repost candidates require review |
| Compare offers | `python -B scripts/offer_compare.py --offers offers.json [--format markdown]` | Year-by-year pre-tax value, totals, the difference from a baseline offer, and equity at 0, 50, 100 and 150% |
| Validate private context | `python -B scripts/user_context.py --context /abs/context.json` | Validation status, section names and whether the time zone is available |
| Capture, match and package uploads | `skills/application-packet/scripts/application_packet.py` | See the [packet command guide](../skills/application-packet/references/command-guide.md) |

## Reading the results

- Signals and statuses are prompts for review, each tied to an exact source line. A missing signal
  proves nothing. Never pass a helper's output to the employer.
- `supported` means the matching words were found next to related words in the user's evidence. It
  does not mean the claim is true. Treat `not_found` and `found_elsewhere` as questions for the user,
  not as permission to soften the wording until the check passes.
- Deadline plans are computed only from the export you supply. A reminder stays due until the
  tracker records an actual send. The plan itself sends nothing.
- `posting_intel.py` annualises pay with a stated unit (full-time: 2,080 hours, 260 days, 52 weeks,
  12 months) and, with a context file that sets `search.min_base_pay`, reports `floor_check`:
  `at_or_above_floor`, `floor_within_range`, `below_floor` or `not_comparable` (different currency or
  unknown period). The assumptions travel with the result.
- `board_feed.py` never fetches. The host saves the board's public JSON response first (the
  endpoint patterns are in the opportunity-discovery search strategy). A posting missing from a
  later feed is a reason to check the live page, never proof that it closed.
  API-error envelopes and malformed vendor containers block processing. A `--previous` snapshot must
  use schema version 1 and match the vendor, board and employer. An explicit vendor permits a valid
  empty feed to report disappeared postings.
- `tracker_diff.py` reports `rows`, identified `records` and `unidentified` counts for each export.
  Missing record IDs on either side produce `rows_without_record_id` review items. A decrease adds
  the blocking problem `unidentified_rows_decreased`. Backwards applied/interview/offer milestones
  produce `application_history_regressed`. Terminal reopenings and changed terminal decisions produce
  `status_reopened` and `terminal_status_changed` review items. Resolve these before treating the
  comparison as complete.
- Calendar UIDs use the existing employer/requisition/record-ID/deadline identity when an ID exists.
  Otherwise they use employer, normalized URL and deadline. Rows without an ID or URL are skipped
  with their row, employer, title and reason in `calendar.skipped`. Duplicate UIDs block export before
  a calendar file is written. Import the generated file into the user's calendar to schedule reminders.
- Tracker exports for `deadlines.py`, `board_feed.py`, `tracker_diff.py` and the packet helper are read-only snapshots of the one
  canonical tracker. Never create a second tracker to feed them.
- For `deadlines.py`, dates must be ISO (`2026-11-20`) or use a month name (`20 Nov 2026`).
  Numeric dates such as `03/04/2026` are reported as ambiguous rather than guessed. Use
  `--map deadline="Closes On"` for unusual headers.

`offers.json` shape (all money values are in the same currency, per year unless stated):

```json
{"currency": "USD", "years": 4, "baseline": "Current offer",
 "offers": [{"name": "Current offer", "base": 120000, "annual_raise_pct": 3,
             "bonus_target_pct": 10, "bonus_expected_payout_pct": 100, "sign_on": 10000,
             "equity": {"type": "rsu", "grant_value": 80000, "vesting_years": 4,
                        "cliff_months": 12, "frequency": "quarterly", "annual_growth_pct": 0},
             "retirement_match_pct": 4, "retirement_match_cap": 9000,
             "benefits_annual_value": 6000, "annual_costs": 0, "pto_days": 25}]}
```

Options use `"type": "options", "shares", "strike_price", "current_value_per_share"`. Back-weighted
grants use `"schedule_pct": [5, 15, 40, 40]`.
