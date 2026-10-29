## Optional recovery index

For an interrupted structured run, project a compact JSON index from the current record:

```text
python -B "<skill-directory>/scripts/aa.py" handoff <run-dir>/run.json
python -B "<skill-directory>/scripts/aa.py" handoff <run-dir>/run.json --output handoff.json
```

The default prints to stdout. `--output` exclusively creates a new filename inside the same run directory; it refuses existing files, nested paths and links. Original reports and records stay unchanged. This is an optional view, not another authoritative store. Regenerate to a new filename after progress; the record digest identifies which saved content the view represents. It is a consistency identity, not a trusted signature.

Each pair retains its stable item/source/recipient IDs, recorded state, exact incomplete `reason` or READY prerequisites, doubt unknowns and unresolved gates. READY means assessment ready to render; a transfer remains a proposal. Its `next_step` is copied with authorization `not-assessed`; incomplete pairs point to their recorded reason and request scope. Neither a READY state nor an empty unresolved list authorizes implementation or establishes acceptance. No decisions are synthesized, no donor/provider calls run, and no resource/cost figures are inferred (`resources` is explicitly unavailable).

Local `reference` objects contain a path relative to the run directory and an RFC 6901 JSON pointer into the original record, for example `{"path":"run.json","pointer":"/items/1/reason"}`. Evidence rows retain bounded local capture paths, read scopes and limitations; claims retain recorded statuses. Source locators are inert data, not refreshed links. Pair evidence includes that source and recipient only, including unread captures and pending claims. A ledger reference on an incomplete item may point to unfinished work; that ledger is not certified complete.

The command uses the existing validator and fails with its actionable error on malformed records, changed captures, stale selected recipient snapshots or mismatched source/recipient joins. Initialized QUEUED runs and valid incomplete runs are usable, with their actual incomplete scope. Structural/byte checks do not certify semantic truth, runtime implementation, reviewer acceptance, or prose outside the record. Snapshot checks cover only declared local files, not remote source freshness. `--historical` retains byte checks but labels present applicability unchecked and every recipient `live_checked: false`.

