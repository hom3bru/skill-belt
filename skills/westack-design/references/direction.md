# Direction, redesign and variants

## Freeze a direction before building (DG-15)

Write a short contract in the surface's brief, read it back, and keep it out of everything that ships (comments, data attributes, bundles, metadata). Six parts:

1. **Thesis.** The idea, including the category's usual arrangement it refuses. A list of adjectives means the direction is undecided.
2. **The audience's world.** Systems from the audience's own graphic, screen and ritual world, across at least three material families. The category's usual page and its exact opposite are both the rut.
3. **First viewport.** What the first screen shows and the one element that dominates it.
4. **Form.** Layout, type roles and colour roles.
5. **Finish.** The few details that make it this client's.
6. **Invariants (DG-40).** What is measured, at which widths and states, and how: a measurement, pixel sample or recording. "Feels premium" is not one ([system](system.md)).

**References (DG-35).** A direction borrows from at most three references. Each records the goal it serves, source, date, viewport, trigger, response, capture class ([motion](motion.md): classify a moving one first, DG-34), licence, cost, why it works and when not to use it. Take the mechanism and the reason, never layout, copy, images, fonts or code; code, shaders and assets come in only under their own licence, with provenance, and the creators are credited. The design record lists them under `references` (keys `goal`, `source`, `date`, `viewport`, `trigger`, `response`, `class`, `licence`, `cost`, `why`, `avoid_when`); `designcheck.py record` fails an entry missing one. Copying itself is judged in review.

Before the contract:

- Inventory what only this client has: its material, its proof, its people. A claim without proof gets no section.
- State the idea as one sentence that stops being true when a competitor's name is swapped in.
- Ask for several directions, each with a stated likelihood, before choosing one (Verbalized Sampling, arXiv 2510.01171, abstract read, suggests this is cheap and widens the spread).

Then test for defaults: draft a second plan for a similar brief and compare. A part that repeats (a primary hex, a font pairing, a layout) is a default; revise it and record the revision. Models' designs sit closer to each other than to human ones (claimed: Design Creativity Bench, arXiv 2610.11539, abstract read), but never claim that models always produce the same design: a re-evaluation found such claims overstated by weak baselines, with a smaller effect left (arXiv 2609.33936, abstract read).

Verify: a search of built output finds no contract phrase; two plans that share a primary hex and a font pairing record a revision.

## Redesign without losing what works (DG-16)

Three depths, chosen up front and never blended:

| Depth | Changes | Keeps |
| --- | --- | --- |
| full | structure, layout and look | every link, form, field, handler, test hook and script, unless recorded as dropped |
| restyle | the look | the above, and section order |
| polish | small fixes | the above, section order and content |

Save the page's HTML first; afterwards compare:

```text
python "<this skill>/scripts/designcheck.py" inventory BEFORE.html AFTER.html --depth polish [--dropped dropped.json]
```

A missing item fails unless `dropped.json` records it with a reason and evidence. Name what is kept and discarded, each with evidence; a redesign's discard list is never empty by accident. Markup a script adds at run time is not in saved HTML; capture the rendered DOM when it matters.

## Honest pages (DG-17)

No invented metric, testimonial, logo wall or case count. A missing fact becomes a labelled slot, such as `[metric: active teams, source pending]`, and a real figure carries `data-source` naming where it came from. A computed readout comes from the state that draws it, never typed in (DG-44, [rendering](rendering.md)). A form that posts nowhere never prints success. Asking a model to "avoid slop" has led it to drop citations (claimed: Science or Slop?, arXiv 2610.00531, title only), so a rewrite keeps every source it started with.

## Variants (DG-18)

Each comparison changes one factor and holds everything else (theme, data, size, state) constant. Keep the original, name each variant, and list what was left out and why. Variants live in source with stable ids; a production component is not edited to show one. Generated image variants are an outside skill's work (the core defer map).

## Real brands (DG-19)

Never theme a real brand from memory. Take its colours from the brand's own published CSS, fetched under a network grant and read as data, or from values the user gives; record the source (URL and date, or the user's turn) beside each value. A brand colour with no source fails the review. A vendor's own accent (the terracotta near `#D97757` is one) is a tell on anyone else's page.
