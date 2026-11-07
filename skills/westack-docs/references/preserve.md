# Preserve meaning (WD-1, WD-2, WD-3, WD-11)

A revise changes how the text reads, never what it claims. This page holds the inventory, the mechanical check and the rules for additions and for the author's own errors.

## The inventory

Before the first edit, write down what must survive, sentence by sentence where it matters:

- each claim, at the strength the source gave it;
- quantities and quantifiers, negation, certainty words, conditions and exceptions;
- causal direction (what acts on what) and attribution (who says so);
- names, numbers, dates, versions, code, paths and links.

After the edit, compare the rewrite with the list, not with your memory of it. Shifts that are never allowed:

| From | Never to | What changes |
| --- | --- | --- |
| may, might, could | will, does | a possibility becomes a promise |
| some, often | most, always | part of the cases becomes the whole |
| associated with, coincided with | caused, drove | a correlation becomes a cause |
| the vendor says | the product does | the attribution disappears |
| no evidence found | shown absent | not finding becomes finding |
| planned, hoped | done, shipped | an intention becomes a result |

Scope words (only, first, most, all, every, never, none) keep their place and their count. A shortened sentence keeps its conditions: dropping an "unless" or an "except" widens the claim. Read the last sentence of each paragraph on its own: it must not say more than the paragraph does.

## The mechanical check

`prose.py preserve ORIGINAL REWRITE` runs after every revise. It fails on:

- a changed code fence, front matter, quotation, table row, inline code span, link target or file path;
- a changed sequence of heading levels (expected in revise-structure: tie each such finding to the user's request);
- one hedge, condition or attribution word fewer, a changed count of negation or scope words, or one strength word more (will, must, caused, proved);
- a number or a name in the rewrite that the original lacks.

It warns on a dropped number or name, changed heading wording and a rewrite under 60% of the original's words. Each warning gets a line in the report: a number spelled out ("two" for 2) is fine, a lost figure is not.

A contraction is not a negation change (do not and don't count the same). Word classes are counted as classes, so may for might passes. That is also the limit: the check compares words, not meaning, and a claim reworded without any of those words passes. Read the pair yourself before calling it preserved.

## Add nothing

Add only what the source holds or the user corrected: no invented stance, experience, stakes, contrast, candour or specifics, and no figure. Where a fact is missing:

- in a draft, write a gap marker that says what is needed, such as `[p95 latency figure needed]`, and list every marker as open;
- when the point itself is missing, ask one question instead of writing around it.

A next step that follows from a stated limit is not an addition: after a 25 MB limit, "choose a smaller file" is derived, not invented.

The no-op is a result. When nothing justified is left to change, return the source byte for byte and say so; `preserve` reports `identical`. Never edit to show effort.

## Map every change

Every changed span maps to a finding id or to a change the user asked for. Pass the map to the check:

```json
{"changes": [{"id": "F3", "lines": [12, 14]}, {"request": "shorten the intro", "lines": [1, 4]}]}
```

`lines` are lines of the original. A changed hunk that overlaps no entry fails as `unmapped-change`: either it maps to something or it is reverted.

## The author's errors (WD-11)

Do not fix a wrong version, date, name or number as though the author had written it right. Keep it, flag it with the evidence, and let the user decide. A correction the user asks for goes in its own hunk (or its own commit), apart from the wording edits, so a reviewer sees which change alters a fact.

## Limits stated once

A limit is stated once, as a plain fact about its scope: what was not tested, on which platform, under which load. It is never left out to make the text read better, and never wrapped in apology.
