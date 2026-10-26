# Interruption and uncertainty

Action A appends one local entry. The tool response times out. Do not append again. Read the authorized target and correlate its operation ID:
- ID present with expected value: applied; record observed evidence and do not replay.
- ID absent with a trustworthy complete read: not-applied; refresh current scope before considering retry.
- Read inconclusive: uncertain; leave action blocked.

If an approval for pause occurrence old-1 arrives after the action changes to remote publication/new-2, it cannot authorize the new action. If a local action was denied, no alternate tool can turn it into an approved action. Keep prior action outcomes and append-only history; the optional previous-snapshot check catches missing history, not forged snapshots.

The deterministic replay fixtures exercise these record rules. They do not qualify exactly-once remote effects or host persistence.

