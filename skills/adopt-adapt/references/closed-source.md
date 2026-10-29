# Closed-source adopt/adapt from open-source intelligence

Use when the donor product’s core source is not lawfully available under an open license. Always pair with [legal.md](legal.md). Use [web-forensics.md](web-forensics.md) for web surfaces.

## Triggers
No public core repo; binary/SaaS only; user names a commercial product; only marketing + docs + SDK stubs. Set `donor_mode: closed-source-osint`.

## Allowed sources (pin each: URL/date/hash)
Official docs · OpenAPI/SDK · changelogs/status/trust/SOC2 summaries · engineering blogs/talks · patents/apps · job postings (**speculated** alone) · employee papers · public GitHub orgs · registries · Wayback/CDX · app-store/pricing pages · public datasets · **observable** behavior on public pages or user-authorized sessions.

**Disallowed:** leaks/warez; credential stuffing; social engineering; auth-bypass scrape; TPM circumvention (legal.md).

## Confidence ladder (required on every internal claim)
`stated` → `documented` → `observed` (≥2 independent non-mirror sources, or lawful HAR) → `inferred` → `speculated`.  
aa.py: every claim with `status: inferred` needs `confidence` in that set. Speculated never alone supports ADOPT/ADAPT.

## Triangulation
Two independent sources before treating an inference as planning-grade observed. Marketing mirrors count as one. Conflicts → keep both, UNKNOWN.

## Mechanism template
name · problem · visible I/O · control surface · algorithm sketch (no copied code) · failure modes · confidence · sources[] · expression_risk · legal_route (idea-only|public-api|clean-room|author-license|discard).

## Buildable spec
Rewrite as recipient requirements + acceptance tests; invent new identifiers; no decompiled paste; default legal route **idea-only**.

## Output
`closed_source: {mode, sources_consulted, mechanisms[], triangulation_log, buildable_spec, red_line_checks}`.

## When the closed donor is a binary
Use [re-verification](re-verification.md). Default posture for commercial binaries is **methods-only**: read-only observation, no writes/hooks/suspension, respect platform protections (never re-sign or weaken hardened-runtime protections), synthetic or self-built fixtures preferred. Every decompiler-derived statement is `inferred` with provenance. Actually investigating an opaque binary or app is a separate reverse-engineer-anything task; this skill judges only what to borrow.

Classify the [claimed output](re-methods.md) before choosing evidence. An executable relinker/API compatibility layer, static instruction translator, replacement engine and recovered-source port have different baselines; the word "port" or a native binary does not identify which occurred. Public observations cannot recover an absent server implementation; write the observable contract and mark unobserved behavior unknown.
