# The developer-experience lens (document mode)

For a plan or spec of something developers use. The rubric (eight dimensions, scores, time-to-hello-world tiers, the record) is the core's `dx.md` (`../westack/references/dx.md`); its dimension ids and tiers are repeated in `scripts/dxcheck.py` so this skill works alone.

## Before scoring

1. **Persona.** One developer: who, goal, environment, what they know. Ask the user if the document does not say; never guess a whole audience.
2. **First-time walk.** Narrate the persona's first hour from the document alone: where they find it, install, reach hello world, hit the first error. Each place they would stop or search is a friction point, with the document's line.
3. **Time to hello world.** Count the steps the document implies and estimate minutes; name the tier. It is inferred: nothing ran.
4. **The magic moment.** Name the first result that would make the persona keep going, and check the document gets them there early.
5. **Comparison (optional).** With the user's yes and westack-research, the time to hello world of one or two tools the persona already knows, with sources.

## The eight passes

For each dimension in the rubric: what a 10 looks like for this product, the score, the gap, and the findings that support it in the standard contract ([review rules](rules.md)). Every score in a plan review is `inferred`. Skip none; a dimension the document does not touch scores 0 with the gap "not addressed", which is itself a finding when it matters to the persona.

## The record

Write `dx.json` (`westack-dx-record-1`, kind `plan`) and run `python scripts/dxcheck.py record dx.json`. It checks the persona, every dimension once with a score from 0 to 10, an evidence mark and a gap, no `tested` mark in a plan, the tier matching the minutes and the overall score. Keep it: westack-qa's live audit compares its scores with this record and flags a live score more than 2 below the plan's.

## In the report

The lens verdict and the persona, the time to hello world and its tier, the eight scores with their gaps, then the findings by severity like any other lens.
