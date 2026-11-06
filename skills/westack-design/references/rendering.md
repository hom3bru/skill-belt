# Rendering checks

DG-38, DG-41, DG-43, DG-44 and the runtime halves of DG-39 and DG-46 need a rendered page or a recording, so they run only as [browser](browser.md) says: the host's browser tools, under a grant that names the target. With no browser each is `not-run`, never passed; `designcheck.py` lists each as not run. Numbers come from the engine, never a model reading a screenshot (DG-27).

## DG-38: the page reads with effects off

Shadows, glows, blur and motion decorate a page; they must not be what holds it together. Inject one stylesheet that sets `box-shadow`, `text-shadow`, `filter`, `backdrop-filter`, `animation` and `transition` to `none` on every element, then measure again:

- **Text contrast** of each text role against the pixels behind it, at the cuts in `thresholds.json`.
- **Region boundaries.** Each card, panel, dialog and input still stands apart from its surroundings by a border, a step in background or space. A card on its page's background with no border, separated only by a shadow, fails; the same card with a 1px border passes.
- **Hierarchy.** The element that dominates the first viewport still dominates it.

A boundary, contrast or silhouette only a shadow, glow or blur supplies is a finding, with measurements before and after. The DG-38 entry lists what it removed under `removed`; `report` refuses a passed or failed entry missing any of the six (`effects-not-removed`): a run that skipped the injection measured the page with its effects on.

## DG-39: smooth by elapsed time, not by frame

A correctness rule, not project policy: it holds in every project ([motion](motion.md)). Moving a value a fixed fraction toward its target on each animation frame (`x += (target - x) * 0.1`) settles about twice as fast at 120 frames a second as at 60. Scale the step by the time since the last frame instead: `a = 1 - Math.exp(-k * dt)`, with `dt` in seconds and clamped (a tab coming back from the background reports a huge one), then `x += (target - x) * a`. Two rates (`k`) are fine when moving toward light and toward dark should differ. Use a spring only where velocity or inertia is part of the motion, and clamp its `dt` too.

- **Static lead:** rule `motion-per-frame-lerp` (reflex) flags a constant-fraction step, or a `lerp` with a constant amount, within a `requestAnimationFrame`, `useFrame` or `setAnimationLoop` loop. A step already scaled by `dt` is not flagged.
- **Runtime half:** record the same motion at two emulated frame rates (60 and 120, say), as DG-26 records motion. The settle times differ by no more than 10%. The 10% is judgment, not a measured cut; a project may record its own.

## DG-43: a recorded frame is a function of time

A recorded or captured animation draws each frame from its time alone: seeded randomness, no wall clock, no state kept between frames. What moves by its own rules is simulated once at load, then only read. Capture can then seek, and load drops no frame. Check: render t=2, t=5, then t=2 again; both t=2 pixel hashes match. A renderer that steps per call (`x += v`) fails; asking only in order would miss it.

## DG-41: a capture waits for readiness

A capture waits for the page's own ready flag (set once its content and fonts have drawn), else fonts loaded and the network idle. A fixed pause is not readiness. The capture then fails if the page logged a console error while loading. A wait that times out blocks the capture: record it as not valid, with the problem `not ready`, and never take it anyway.

Each capture in the report records:

| Field | Holds |
| --- | --- |
| `ready` | `flag`, `fonts-network` or `timeout` |
| `console_errors` | how many errors the page logged before the capture |
| `valid`, `problem` | false, with the reason, when the wait timed out or an error was logged |

`report` refuses a timed-out or erroring capture marked valid (`capture-not-ready`, `capture-console-errors`), an unknown `ready`, and a DG-41 status its captures contradict (`readiness-status`): a timeout makes it blocked, else an error failed; passed needs both fields on every capture. An invalid capture means recapture with no findings (DG-3, [critique](critique.md)).

## DG-44: readouts move with their input

Change the input through the page's own control: each readout that depends on it moves. One that stays put was typed in, a finding ([direction](direction.md), DG-17); one capture cannot show it. Check one value by hand and record its inputs and arithmetic.

## DG-45: the final review reads the delivered file

An encoder or build can change what the live render showed, so final captures come from what ships: the encoded video's frames, the exported image, the built page. When the report names `delivered` (`path`, `sha256`), a capture marked `final` names that hash as `source_sha256`; otherwise `report` refuses it (`capture-not-delivered`).

## In the report

Each check here is a `runtime` entry with a [browser](browser.md) status and evidence or reason, checked by `report` when reported. Text a recording shows goes in `text_beats` (`text`, `held_s`): each beat holds at least `text-hold-s` in `thresholds.json`, 1 s plus 0.25 s per word past three (DG-46, `text-hold-short`).
