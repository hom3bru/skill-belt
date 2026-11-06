# Host: what the agent can touch

Use this for "what can my agent touch?" and "is my setup safe?". Read settings and change none: a settings change is persistent configuration and needs its own grant (core `authority.md`). Date every host-specific value; hosts change often.

## Switches

List the host's independent switches and what each covers: bypass mode off, rules and hooks managed centrally only, a plugin allowlist with pinned versions, a sandbox required with no fallback. A sandbox setting may cover the shell only, not file tools or MCP servers. Installing a plugin is a trust grant.

## Saved rules

- Flag a saved allow rule broader than one command family: a wildcard shell rule, an interpreter, a shell, `env`, `sudo`, `git` or `rm` (core `guards.md`).
- Treat a broad rule an agent proposed after reading repository or tool content as suspect. Show what it would allow before anyone approves it.
- A tool's own read-only hint or display title is a claim, never permission. Classify from the raw call; a tool missing from a reviewed list of reads counts as a write.
- A policy rule may name the account behind a credential. A bare name matches only use with no credential, and switching accounts re-evaluates every rule.

## Tools as a set

Judge the tools one agent holds together. Untrusted content, private data and destructive capability in one agent carry the risk even when each tool alone looks harmless. Name which of the three each tool adds.

## Agents and delegates

- Authority is fixed from trusted input before any untrusted content is read.
- Each delegate holds its own capabilities, stored outside the model. A sub-agent that inherits its parent's write capability is a finding.
- One agent's output is untrusted data to the next.
- A tool capability is bound to one principal, thread and kind. It is honoured only while that principal's turn is live, and withdrawn once the turn is over or the principal begins another; one used after its turn is a finding.

## Person-only actions

Check that the host sends credential and two-factor changes, sharing settings and payments to a person, whatever a rule or mode says, and that a model reviewer can add such a hand-off but never remove one. A host that lets an agent complete one alone is a finding.

## Local agent servers

Binding to loopback does not keep out the user's own browser. A local server should require a loopback Host header, an absent or loopback Origin and no proxy headers; distrust browsers; and treat a GET with side effects as a mutation. One that accepts a cross-origin browser POST is a finding.

## Automated triggers

- For a CI or webhook trigger, every actor needs write access, bots are refused unless named, and the workflow holds the fewest permissions it needs.
- A callback needs a validated URL (no private, loopback or link-local target), authentication, an id the run itself created, idempotent handling and a rate limit.
- Scanning CI itself, and reporting a skipped fork run as not scanned, belongs to the planned westack-ci.

## Inventory reports

Name only the users who have a detected agent, else the current user, and give components paths relative to the home folder.
