# Critique and audit

Critique is report-only: the project's files end as they began, and captures and the report go in the evidence or a scratch folder. An audit is a critique of one named surface.

## 1. Check the evidence before judging (DG-3)

Validate the capture set first and judge nothing until it passes:

- Open each capture once and check it against its label: the page, width and state.
- A blank, wrong-section or missing capture means the disposition is `recapture` and the report holds no findings.
- Capture after entrance motion settles. Scroll a full page to the bottom first, so reveal-on-scroll sections render, then capture from the top.
- A capture taken while a font failed to load is void (the DG-24 font check finds it).
- The final review reads the delivered file (DG-45, [rendering](rendering.md)).

## 2. Observe, and keep only what is shown (DG-4, DG-27, DG-29)

- Exercise the states that matter (hover, focus, empty, loading, error, long content) and resize through the audit widths in `thresholds.json`.
- A finding needs a screenshot, console line, measurement or recording, or it is dropped. Motion needs a recording (DG-26).
- Numbers come from the render engine: computed styles, bounding boxes and pixel samples, or the declared source. Models reading screenshots report the repeated pattern instead of the odd element (claimed: Pattern over Pixels, arXiv 2608.03691, abstract: 21.2% and 7.9% accuracy).
- If the page will not open, the visual phases are not-run, only source heuristics are reported, and the first line is a DEGRADED banner.
- Static and rendered checks are reconciled. A static scan never combines rules scoped to different media (print, dark mode, hover). A static finding that a rendered check contradicts is dropped, with that reason.

## 3. Judgment first, detectors second (DG-5)

1. Write the design judgment from the captures and the brief, before reading any detector output.
2. Then run the checks below and add their findings, noting where they disagree with the judgment.

The report's first line is a method line (`Method: ...`) or, when a phase could not run, a `DEGRADED: ...` banner naming it; record the two phases' order.

## 4. Substance beside every ban (DG-6)

Passing every ban does not make a page good: check that one element dominates each screen, that no screen is nearly empty, that no section is only a heading and a paragraph, and that the content is real. The taste-skill author's own tests found that mechanical compliance did not raise judged quality (author-reported).

## 5. Scores are triage, never evidence (DG-7, SS-77)

- Score a few named criteria, weighted toward what models usually get wrong, each with two anchor examples (what a 0 and a 3 look like).
- Scores are integers from 0 to 3. When unsure between two, take the lower. Score the worst instance, not the mean.
- A criterion that cannot apply is n/a with a one-line reason and leaves the denominator. Record the maximum and the n/a set, so ten criteria with two n/a print /24, never /30, and trends never mix denominators.
- Re-check the anchors against a person when the model changes; the report names the model they were checked for.
- A score orders the work and never supports a finding. Judges of design disagree widely (claimed: DesignPref, arXiv 2511.20513, reports agreement of 0.25 among 20 designers).

## 6. The report file

Write the report as JSON (format `westack-design-report-1`) and check it with `designcheck.py report FILE`:

| Field | Holds |
| --- | --- |
| `mode`, `first_line`, `browser` | the mode; the method line or banner; the browser tool used, or `none` |
| `phases` | `judgment` and `detectors`, in the order written |
| `captures` | id, file and whether it is valid (with the problem when not); `disposition` is `recapture` when any is not |
| `findings` | id, claim, kind, level (the core's words), rule, path, correction, evidence (kind, ref; motion: class), and `rendered` when a rendered check agreed or disagreed |
| `claimed` | source-only judgments of hierarchy, prominence, density or usability |
| `runtime` | DG-23, DG-24 and DG-26: status (passed, failed, blocked, not-run) with evidence or the reason |
| `scores` | model, rubric (criteria, weights, anchors, the model they were checked for), rows, max, total and the n/a set |
| `proposals`, `environment`, `baselines` | what the user must accept; the run's OS, browser, headless mode and pixel ratio; each screenshot baseline, whether it changed and its environment (DG-31) |

## 7. The checks

| Command | Checks |
| --- | --- |
| `tokens SRC --theme T` | raw colours and lengths, with the token or on-scale class to use (DG-11); `--baseline` lists new tokens (DG-12); `--writing F` stops before a second token source |
| `contrast RECORD` | the record's colour pairs and components, variants inheriting from their base (DG-14) |
| `rules SRC --brief B` | `rules.json`: tells, honesty, frame, substance and motion rules; `--waivers`, `--record` for the motion policy, `--control` for a human page (DG-28) |
| `waivers FILE` | tier, reason and evidence of each waiver (DG-8) |
| `inventory BEFORE AFTER` | links, forms, fields, handlers, test hooks and scripts kept through a redesign (DG-16) |
| `record FILE` | the design record and its derived files (DG-20, DG-21) |
| `report FILE` | this report |
