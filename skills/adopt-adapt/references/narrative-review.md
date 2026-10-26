# Case-local narrative review

Use before publishing a source assessment, especially a batch or verifier review.
This is a short entailment check, not another mandatory scoring system. Read the
decisive source lines and actual request; do not infer them from a previous case.

1. **Choose and name the output mode.** A bounded manual review may say `READY
   (manual assessment); machine validation not run`. Its inline queue is enough;
   do not initialize a machine record unless you intend to use it. If a machine
   record exists, report its actual state separately using `aa.py status run.json`
   or a direct read. Manual completion does not change that file. Never invent a
   `QUEUED → RESEARCHING → READY` transition or call input-only validation report
   validation. Structured mode publishes a completed record's rendered output.

2. **Check each decision-changing sentence against this case.** Keep a few local
   facts with source/recipient citations, then write doubt and transfer from those
   facts. Reuse empty field names, not another case's paragraphs. An argument may
   compare another queued donor when relevant; it may not borrow another
   recipient's behavior, permission, or state. The helper checks evidence subject
   relationships; a reviewer still checks whether the words follow from them.

3. **Separate instructions, claims and wiring.** `Run python verify.py` is a
   suggested invocation. `Can be used before merging` describes possible use.
   Neither asserts that CI calls it, nor proves it ran. An absent runner remains
   UNKNOWN, not CLAIMED wiring. Call something CLAIMED only when the donor
   actually asserts that capability, and identify the assertion.

4. **Preserve the exact permission scope.** Distinguish forbidden, authorized but
   unrun, and unrequested/unrun actions. `Do not run donor scripts` does not mean
   all recipient checks are forbidden. If no scripts ran, say so without inventing
   a broader prohibition. Research can finish without using every allowed action.
   Preserve requirement modality too: `If retries are used, they must be bounded`
   constrains an optional feature; it does not require adding retries. Keep what
   the user requests, what policy permits/limits, and what you recommend separate.

5. **Inspect how the decisive check can fail.** For language-native assertions,
   check disabling/build/runtime conditions that matter: Python `assert` is removed
   with `-O`/`-OO`; a success print may still run. If invocation flags are absent,
   report this conditional risk and the unknown actual mode. Source inspection is
   enough to identify it; running a donor is not required. Distinguish the
   inspected verifier's contents from its configuration, execution and domain
   coverage. A normal example does not establish malformed-input behavior.

6. **Keep the conclusion proportional.** A source fact, a bounded mechanism
   proposal and explicit unknowns can complete a review. Do not require the
   proposed recipient feature to exist already. An inspected receiving seam and a
   small acceptance test can justify ADAPT-with-prerequisite; unsupported runtime
   success, legal transfer or installation claims remain blocked. No useful
   additional mechanism is an acceptable result.

Practical final check: do the mechanism names, receiving seam, runtime caveats,
permissions and completion labels all describe this case? If a statement has no
support, remove it or label the missing evidence. No wording matcher certifies
this semantic review, and no correct-looking verdict excuses a wrong ledger.
