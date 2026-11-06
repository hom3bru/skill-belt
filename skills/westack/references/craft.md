# Craft rules (C12)

Each rule carries a Why: the failure or model weakness it answers. A rule with no reason is a removal candidate ([learn](learn.md)).

- Subtract before adding: the smallest sufficient change wins, and a dead path you touch is deleted, not wrapped. Climb a reuse ladder, stopping at the first rung that fully works: existing code, the standard library, a small helper, new code. Never subtract trust-boundary validation, data-loss handling, security or accessibility; new non-trivial logic gets a test. Why: models grow code (wrappers, options, copies) before removing any.
- No speculative abstraction: wait for two real callers; no unused options, flags or parameters. Why: an abstraction guessed from one caller is wrong at the second.
- Remove slop. In code: comments narrating the next line, defensive checks for impossible states, catch-all error swallowing, dead options. In prose: filler, performed hedges, repeated summaries. Why: models pad to look thorough, hiding the lines that matter.
- Point at the lookup; do not copy it. Do not restate what a tool's `--help`, the repository layout or the model's default behaviour supplies, and let helper output name the next command. Why: a pasted manual goes stale and costs tokens every session.
- Named foundations. Why: each answers a recurring failure (shallow wrappers, big-bang builds, split names, scattered checks, skipped repeated instructions, the same judgment re-made every session).
  - **Deep modules:** a small interface over substantial behaviour, with seams where tests can hold.
  - **Tracer bullets:** one thin path through every layer first, then widen it.
  - **Ubiquitous language:** one name per domain idea, in code, tests and docs.
  - **Illegal states unrepresentable:** types and schemas that reject bad combinations beat scattered checks.
  - **Lessons encoded in structure:** a recurring instruction becomes a check, test or type, not more prose. A validated judgment that recurs becomes a deterministic check or stdlib helper; the model keeps the novel cases. A helper that acts validates identifiers against live state, takes ids from the event not model text, caps its own calls and runs commands as an argument vector, never a shell.
- Give one recommendation when a decision is needed, and label a hypothesis as one. Why: a menu hands the choice back; an unlabelled guess reads as established.
- Where the repository's established style conflicts with these rules, follow the repository (an instruction file that disagrees with the code: [context](context.md)). Why: a team convention is evidence of current behaviour, and overriding it surprises later readers.

Provenance: C12 in provenance/facility-donors.json.
