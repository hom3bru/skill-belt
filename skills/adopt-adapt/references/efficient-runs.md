# Efficient runs with unchanged evidence standards

Use this flow for multi-artifact or multi-recipient reviews. A quick call stays brief. Optimize acquisition and bookkeeping; retain every artifact, recipient, decisive source trace and experiment opportunity.

## Acquire once, assess separately

Batch independent read-only tool calls: primary files, both hosted-wiki checks for confirmed public repositories, background searches and unrelated artifacts can run together. Use the host's batch APIs and a small bounded concurrency, normally four or the provider's lower limit. Apply rate limits and tool constraints. Dependent redirects, identity resolution and newly discovered links enter the next wave. Continue every wave until all artifacts are assessed or their unresolved work is recorded; a wave is not a shortlist or a stopping budget.

An optional read-only plan makes the work explicit:

```text
python -B "<skill-directory>/scripts/acquisition.py" RUN/run.json --jobs 4
```

The plan proposes tasks and preserves the source/recipient matrix; it retrieves nothing and certifies no read. Mark `source.visibility` public/private/unknown from established identity/access evidence; unknown identity gets confirmation before hosted checks. Both wikis remain required when available. Record actual provider-page reads with optional `intake.artifacts[].coverage.deepwiki`/`codewiki` rows citing full-text captures, so replanning can reuse them. For unavailable pages retain attempts and remaining methods; do not repeat identical failures or block source-grounded review for missing summaries. Use existing authorized tools: no private uploads, new indexing, installation, paid elements or donor execution.

Fetch each confirmed canonical artifact/version once. Inspect and share its pinned raw captures and source-built map across recipients; retain all parent edges, aliases and source IDs. Existing unread captures need inspection, not another automatic fetch or a fabricated read. Each registered subject still needs correctly owned evidence; identical stored bytes can be shared without borrowing another recipient's claims. Evaluate recipient applicability, gates, verdict, uncertainty and tests separately. Keep independent review fresh.

Reuse facts only after identity, revision, scope and freshness checks. Previous verdicts/scores are excluded. Changed revisions, unresolved identities and different media/coverage need their own work. A failed method may prevent an immediate identical retry, but never suppress another retrieval method or future changed conditions. Useful background research and associated-link expansion still follow [source intake](source-intake.md).

## Finish once

After updating the actual record and intake, use `aa.py finalize RUN/run.json --output RUN/report.md`; add `--complete` only for a complete-coverage claim. It combines saved-byte readback and checked rendering. Preserve explicit pending/indexing status and failed-operation results. Validation caches last only for one operation; later calls recheck bytes and live dependencies. Do not substitute timestamps or old successful checks for freshness. See [gates](gates.md) for fields and [records](records.md) for separate commands.
