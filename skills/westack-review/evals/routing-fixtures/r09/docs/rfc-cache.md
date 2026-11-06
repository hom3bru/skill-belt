# RFC: response cache for the catalog API

## Proposal

Add an in-memory cache in front of `GET /catalog/<id>`. Entries live for 60 seconds. Writes to a catalog item delete its entry.

## Design

- One cache per API process, keyed by item id.
- A write on one process does not reach the other processes' caches.
- Maximum 10,000 entries; the oldest entry is dropped first.

## Alternatives

- A shared Redis cache.
- Longer cache lifetimes with explicit versioning.

## Open questions

- Is 60 seconds acceptable for price changes?
