# Report layout

The report is one file, `REPORT.md`, in `<research_root>/<YYYY-MM-DD>-<topic-slug>/`. Next to it go:
- `log.md`: the query table and the sources-opened table;
- `sources/`: the originals relied on;
- `manifest.json`: bytes and sha256 for each file.

1. **Answer.** The best option for the user's problem and why, in a few lines.
2. **Scope.** The problem, the decision, the window (start and cutoff), the research questions and criteria, what would change the answer, the stop rule, and earlier research reused. Add the user's project baseline when there is one: repository, branch, commit, what exists and its known gaps.
3. **Top picks.** A table with these columns:
   - ID; name and link; type; maintainer; status;
   - the dated event that puts it in the window;
   - key numbers (stars, contributors, PRs merged this year, last push, licence from the LICENSE file, and downloads or installs where relevant), each labelled by origin;
   - fit to the user's problem;
   - how much was read: N of M parts, blind spots, and whether they could change the rank.

   IDs go by lane: R repository, P paper, C product or service, D discussion or standard, B the user's baseline. The rest of the report cites IDs.

   When the user asked for a full survey, also keep an **Inventory** appendix: every assessed item by ID, a line each, apart from Top picks. Inclusion means relevant, not recommended.
4. **How they are built.** The construction comparison: what the strongest do, where weak ones cut corners, and claims versus independent evidence. Include each top pick's doubt pass: the case against, the case for, the deciding evidence, and whether the rank survives.
5. **Papers.** Verified IDs, measured numbers and limits.
6. **Products, protocols and terms.** Closed products, the specs that matter, and what vendor terms allow.
7. **Community.** Ranked threads and posts, each linked; real complaints.
8. **Defunct, and older but foundational.** What died, why, what is worth borrowing; older items still standard.
9. **Hands-on.** What was measured and how, or why it was not.
10. **Traps.** Licences, star inflation, telemetry or network calls, terms risks.
11. **Recommendation and next steps** for the user's actual setup. Mark fit provisional where the user's setup was not inspected.
    - Mark each recommendation's need *demonstrated* (with evidence in the user's setup) or *anticipated*. An anticipated need defaults to defer, with the question that would decide it.
    - When hands-on was not done, name the comparison that would settle the choice: the candidates, the data, what it must establish, and the baseline it runs against.
12. **Coverage map.** It holds, in order:
    - every planned category: searched, partly searched, not searched (why) or blocked (what was tried);
    - the branches seen but not followed, each with why it might matter;
    - the prominent candidates checked and set aside, each with what was checked and why;
    - the query outcome counts from `log.md`: results, none in window, error.
13. **Gaps and not done.** Verification not performed, sources not reached, claims left unverified, earlier claims corrected.
14. **Check work.** `## Check work <YYYY-MM-DD> (<reviewer>)` from the check-work sub-skill, containing:
    - the verdict;
    - the reviewer's restatement and blind answer;
    - load-bearing assumptions;
    - findings with dispositions (accepted, rejected with evidence, or open);
    - counter-recommendations with the author's assessment;
    - open questions;
    - what held up, what was not checked, and any disputes.

    Or write "check-work not run (why)".

A deeper dive appends `## Deeper dive <YYYY-MM-DD>` at the end and updates sections 3, 11, 12 and 13 in place, marking each change `(corrected <date>)` or `(added <date>)`. Check-work fixes are marked `(corrected <date>, check-work F<n>)`.
