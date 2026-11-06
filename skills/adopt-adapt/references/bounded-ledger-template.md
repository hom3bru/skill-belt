# Bounded ledger template (manual mode)

Fill bounded-review lines with evidence, `unknown` or `not applicable (reason)`. Ledger before verdict. Structured runs use [records](records.md).

```
ROUTING: <profile> (<high|medium|low>: <evidence>) · self: not selected (no explicit intent)
QUEUE: #1 <source> → <recipient> — READY (manual assessment); machine validation not run

SOURCE: <canonical locator> @ <commit / release / DOI version / doc date + content hash>
Inspected: <files or sections read, with lines>; blind spots: <what was not read and why>
RECIPIENT: <root> @ <branch> <HEAD>; dirty files relied on: <list>; rules read: <path (date)>

Refutation targets (written before the deep seam read):
1. Claimed benefit: <observation that would refute it> — confirmed | refuted | unknown
2. Already covered: <recipient observation that would make it ALREADY-COVERED> — ...
3. Broken analogy: <donor assumption that would not hold here> — ...

Evidence ladder:
| Claim | Level (CLAIMED/PRESENT/WIRED/TESTED/OBSERVED) | Citation (file:line or run receipt) |

Need: <gap/improvement/simplification + observed symptom or stated requirement; the user's statement counts; a gap alone is insufficient>
Unconfirmed need only: Current burden: <recipient observation + evidence, or unobserved>
Next check: <recipient-only burden observation if unobserved>; Prototype: <conditional on confirmed need>
Discovery: <finding in a starting lens or other area: source lines/section>; also inspected: <one line>
LEGAL: <flag> | route <route> | patent_signal <none|hit|unknown> | terms_restriction <...> | escalate? <yes|no>
Gates: <recipient perimeter, governed/frozen status of the seam, paid elements>

For / against: <strongest reason each way; a mismatch cites both sides, its failed precondition and whether repairing it changes the mechanism or recipient contract>
ADAPT only: behaviour/invariant · exact seam · semantic difference · current behavior → benefit → burden added/removed → smaller alternative · licence route · rollback · test that fails when the mechanism is disconnected
Review: self | <level, packet or report hash, strongest disconfirming observation, checked?>

VERDICT: <result> | fit not scored (bounded route) | mechanism <0-3>/3 | confidence <low|medium|high>
   (value 1: DISCARD (promising: <check ID or single next check>))
Summary: what it is · the mechanism · the benefit · the limit · next check ID (single lead: the check)
```

Confidence follows the ladder: any decisive CLAIMED or inferred claim means `low`, and `high` needs WIRED or above with at least one TESTED or OBSERVED claim, which also requires an independent review (SKILL.md §4, §7).
