# Trees and forest: default repository research suite

For repository reviews under §2, use the applicable source families below by default. Depth follows the requested scope: a bounded mechanism needs its surrounding subsystem, while a whole-tool assessment needs the major subsystem boundaries. A self-contained quick call or non-repository source does not require a repository-provider tour.

## Default suite

| View | Sources to check | Contribution and limit |
| --- | --- | --- |
| Forest: hosted overviews | Check **both [DeepWiki](https://deepwiki.com/) and [CodeWiki](https://codewiki.google/)** for an existing page for the public repository; read each when available. | Discover components, vocabulary, diagrams and candidate connections. Summaries are CLAIMED-level hints, potentially donor-steered and stale; neither replaces the source-built map. |
| Forest: design and history | README, official/versioned docs, architecture diagrams, ADRs, releases/changelog; relevant maintainer issues and PRs. | Recover intended boundaries, assumptions and changed behavior. Documentation and discussion establish claims; code establishes current implementation. |
| Trees: navigation and traces | Native GitHub/GitLab repository tree, code search and symbol navigation; [Sourcegraph](https://sourcegraph.com/docs/code-search) when accessible; local `rg` and existing symbol/caller tools. | Locate entrypoints, imports, callers, configuration, data flow and tests at the pinned revision. Search hits alone do not establish wiring. |
| Bridge: structure and digests | Available [Repomix](https://repomix.com/guide/)/[Gitingest](https://gitingest.com/) read-only views or existing outputs; existing dependency/call graphs, package manifests and workspace/build configuration. | Expose overlooked modules and cross-boundary dependencies. Check revision, omissions and truncation; a digest or generated graph does not prove runtime behavior. |

Batch independent availability checks and primary reads under [efficient runs](efficient-runs.md). Use views that add distinct information. Both hosted wiki checks remain required; one never excuses skipping the other. For alternative navigation/digest tools, one suitable option per relevant family suffices; explain material skips. Provider names are defaults, not a whitelist: resolve concrete blind spots with additional sources.

For private repositories or local sources without a confirmed public identity, use authorized local views. A local clone of a confirmed public repository still gets the public checks. Do not upload private code, identifiers or credentials, trigger new hosted indexing, install packages, execute donor/config scripts, or add paid elements to fill the suite. Repomix/Gitingest can involve network retrieval; `npx` downloads and executes code. Record actual network use; existing local outputs may be read offline. Missing tools require a source-browsing fallback, not setup during evaluation.

## Forest → trees → forest

1. Sketch the components, boundaries and main data/control flow from the overview and design views. Keep unclear or conflicting edges provisional.
2. Follow promising parts and surprising connections into pinned raw files, entrypoints, callers/configuration and relevant tests. Search from recipient needs into the donor and from donor mechanisms toward overlooked needs. Scale breadth to the claim, including an apparently unrelated subsystem when its mechanism is promising.
3. Return to the system map: reconcile implementation with the summaries and diagrams, inspect cross-boundary effects, and correct contradictions. Verify every decision-changing claim and edge in the pinned source; an unverified decisive claim stays unknown and limits the conclusion. Reading a test shows its implementation; do not assume it ran. TESTED still requires a run in this work.

Build the final map from inspected source and checked references. Two summaries repeating the same underlying claim are not independent corroboration. An inaccessible provider means unavailable, not that the repository or feature is absent.

Record consulted URLs/paths, retrieval dates, known revisions or revision uncertainty, availability and material skips in existing evidence/coverage notes and `ledger.map.limitations`; cite captures when structured records are used. No new record fields are required. A failed retrieval invokes the alternative methods in [source intake](source-intake.md); record the actual fallback attempts, not just the first provider error. Stop provider probing when the relevant families have usable evidence or their applicable retrieval routes are exhausted and the decisive source paths traced. Unavailable summaries alone do not block a source-grounded review; insufficient raw evidence still limits or blocks the affected claim.
