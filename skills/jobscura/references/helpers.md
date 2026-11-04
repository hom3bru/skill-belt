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
| Check a file before upload | `python -B scripts/ats_lint.py Resume.docx` | Blockers (tracked changes, comments, hidden or white text, macros, image-only or encrypted PDF), warnings (tables, text boxes, columns, contact details only in the header) and metadata |
| Plan deadlines and checks | `python -B scripts/deadlines.py --tracker export.csv --context /abs/context.json [--as-of ISO]` | Days and hours remaining in the user's time zone, reminder windows now due (minus those already sent), status checks due, unresolved dates, morning digest |
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
- Tracker exports for `deadlines.py` and the packet helper are read-only snapshots of the one
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
