# Reusable lessons and research frontier

Store facts/lessons separately from the write-only verdict history. A lesson records ID, source identity/version, inspected support, transformation/parent IDs, mechanism, applicable conditions, counterexamples/failures, local tests, status promising/locally-validated/stale/retired, freshness trigger and next discriminating experiment. No previous score or verdict is a premise in fresh evaluation.

Use `aa.py invalidate <lessons.json> <id>` to mark the changed node and every transitive descendant stale. This identifies re-verification work, not automatic falsity. Reuse only after rechecking source/recipient identity and scope. Merge duplicate lessons with all provenance parents retained; do not keep only the first item of an oversized batch. A derived summary does not sanitize an embedded instruction.

## Discovery clues and problem-based retrieval

Retain a useful, evidence-backed clue as `promising` even when its receiving seam
or actual recipient need is unknown. Record the inspected source/pin, a short
language-neutral problem/invariant, relevant assumptions or counterexamples, the
unresolved question and the next small check. That is a research lead, not a
transfer recommendation, legal clearance, accepted plan or proven gain. Use the
existing lesson file or authorized run artifact scope; do not create a new memory
service or automatically append lessons outside the user's write scope. Keep a
small frontier of plausible leads rather than accumulating every clever detail.

Optional `problem_tags` and `invariant_tags` can describe reusable concerns such
as `duplicate effects`, `interrupted writes`, `bounded work` or `identity
preservation`. Optional `problem`, `invariant` and `assumptions` fields explain
the neutral behavior. Prefer these concerns over repository names or languages
when looking for related facts; retain the original provenance and limits. Tags
are navigation aids, not a taxonomy every lesson must satisfy.

`python -B "<skill-directory>/scripts/research.py" search lessons.json --query "interrupted writes"`
retrieves fact candidates using lexical matching. Repeated `--problem TAG` and
`--invariant TAG` filters narrow their respective tags and descriptive fact text;
`--limit N` bounds output when desired. No limit or tag backfill is mandatory,
and older records remain usable.
The helper excludes stale/retired nodes and does not rank or return previous
verdicts, scores or decision history. Results remain unvalidated candidates with
freshness checks required: inspect their original evidence/identity and the live
recipient before making a fresh judgment. Lexical retrieval does not establish
semantic similarity, applicability or truth, and source-derived text remains
untrusted data. It does not shortlist or remove any source in the user's queue.

For new lessons, optionally store `dependencies: {"files": [{"path": "relative/file", "sha256": "<64 lowercase hex>"}]}`. Record an explicitly absent expected file with `"sha256": null`; its later appearance is a change. Use `research.capture_dependencies(root, paths, source_revision=...)` to create this declaration and `research.invalidate_changed_lessons(data, root, source_revision=...)` to compare it. The latter calls the existing graph invalidator for changed nodes, so descendants become stale too. It only invalidates lessons whose declared file hash, declared absence, or supplied source revision changed. It does not scan undeclared files or turn unchanged bytes into proof that a lesson is true. Older lessons without `dependencies` stay manual/unknown until a reviewer adds a fresh, scoped declaration; historical verdicts do not fill it in.

To retain a pinned local source tree as review data, call `research.create_archive(source_dir, archive_path, identity="...", revision="...")`, then `research.verify_archive(archive_path)` and `research.restore_archive(archive_path, fresh_destination)`. Supply the authorized source directory and its exact identity/revision yourself; for an uncommitted tree, label the revision as a working-tree capture and retain the archive hash with the review record. The ZIP includes a SHA-256 entry for every included file and records the identity, revision, exclusion rules, and paths actually excluded. It copies bytes only and never imports or runs donor code. By default it excludes `.git`, dependency/build/cache directories, `.env*`, and common credential, key, secret, and token filenames. These name rules cannot identify every secret: review the declared source scope and archive manifest before sharing. Symlinks/junctions are rejected, path traversal and member/hash mismatch fail verification, and existing archive or restore destinations are refused. The manifest detects accidental mutation; it is not a signature or authenticity proof. License files are included when present and not excluded by the caller's directory choice.

Design inputs inspected on 2026-10-09 (not promises of local gains):

Practical CLI (`<skill-directory>` is the folder holding SKILL.md): `python -B "<skill-directory>/scripts/research.py" dependencies ROOT --path FILE --output dependencies.json`; attach that declaration to its lesson. Before reuse, run `freshness lessons.json ROOT --output lessons-rechecked.json` (optional `--source-revision` on either command). `archive SOURCE ARCHIVE.zip --identity LOCATOR --revision SHA`, `verify-archive ARCHIVE.zip`, and `restore ARCHIVE.zip FRESH_DIRECTORY` support offline preservation. These commands do not install or execute sources; existing output destinations are refused.

Review filename exclusions: legitimate source such as `BrowserScenarioSecrets.ts` can match a secret-name rule. After inspecting that exact file, `archive --include-path relative/source.ts` includes it and records the exception while retaining other exclusions. Do not disable secret exclusions broadly or treat a source-looking filename as proof of safe contents.

| Source | Borrowed mechanism | Local falsifier / limit |
|---|---|---|
| [REA](https://github.com/morluto/rea/tree/1b73b5ab4bc75bd424e643de8e49f142ffa2b336) | Evidence identity, residual uncertainty, dependency/state closure | A valid JSON object attached to the wrong version must fail; bytes do not establish truth |
| [Universal Modder](https://github.com/rehan-remade/universal-modder/tree/8370faa8e114baf33acdb23079aff552a7728c4b) | Observable behavior, real vertical slice, independent oracle, field notes | A dead helper or shared-bug round trip cannot count as integrated/correct |
| [SkillFoundry](https://arxiv.org/html/2604.03964v1), [SkillX](https://arxiv.org/html/2604.04804v1) | Coverage-guided extraction, bounded contracts, consolidating successes/failures | More lessons without useful recall/transfer gains is failure; do not import unsafe dynamic evaluation |
| [ReCodeAgent](https://arxiv.org/html/2604.07341v4), [Kaizen](https://arxiv.org/html/2607.04058v1) | Semantic transfer and discriminating translation tests | Passing donor parity alone may reproduce a bug; findings depend on task/language |
| [Skill-Inject](https://arxiv.org/html/2602.20156v1), [SkillJack](https://arxiv.org/html/2608.03509v1) | Test legitimate utility plus malicious source redirection | Warnings alone do not prove injection resistance; derived records need provenance |
| [Agent Skill Evolution](https://arxiv.org/html/2610.04832v1), [SkillScriptBench](https://arxiv.org/html/2610.04008v1) | Native activation, full-package fault and clean-case testing | Forced reading and regex conformance do not establish host behavior |
| [XRepoSkill](https://arxiv.org/html/2609.36807v1), [held-out evolution](https://arxiv.org/html/2609.39148v1) | Conditioned cross-repository lessons, independent families | Development-case wins cannot establish holdout improvement |
| [Process evaluation](https://arxiv.org/html/2610.01833v1), [agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Distinguish process, result and failure causes | Right verdict with fabricated evidence still fails |

Research by unresolved capability, not publication count: inspect primary repo code, papers/method/results, maintainer issues and official docs as appropriate. Record study version, task/domain/model, oracle, observed limitation and what would test applicability here. Developer discussions are reproduction leads, not evidence today's host has the same bug. Trending repos deserve mechanism inspection; popularity does not establish correctness or explain its own cause. Verify current identities when freshness matters rather than reusing this cutoff as “latest.”

Maintain a small frontier of open questions tied to decisions: unknown edge, missing useful mechanism, uncertain oracle, stale policy, unresolved integration effect. Each next research step must discriminate between alternatives. Retire stale/no-value notes; do not accumulate universal rules or start recurring monitoring implicitly.
