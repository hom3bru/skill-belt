# Coverage categories

Plan which categories apply before searching, search them, and record each one in the report's coverage map as **searched**, **partly searched**, **not searched** (with why) or **blocked** (what was tried). "Not relevant to this question" is a reason; "ran out of time" is a gap and goes in Gaps.

`log.md` keeps two tables, which the coverage map summarises:

| Table | Columns |
| --- | --- |
| Queries | time · tool · lane · query (verbatim) · outcome: *results*, *none in window* or *error* (wrong name, blocked, 404) · results kept |
| Sources opened | URL · date read · one-line summary · used or not, and why · ID if assessed |

An empty result is not evidence that nothing exists, and an error is not an empty result. When a query is corrected, the failed one stays visible.

| Category | What to look at | How to check it |
| --- | --- | --- |
| the user's own past research | Palette, `<research_root>/`, earlier reports on the topic | Extend; say what was reused |
| Open-source repositories | GitHub, GitLab, Codeberg; forks, dependents, issues, releases | Repository checks; licence from the LICENSE file |
| Closed and paid products | Docs, API references, changelogs, pricing, limits, data policies | Docs and changelogs over landing pages; date every pricing read |
| Papers and scholarship | arXiv, proceedings, Semantic Scholar, OpenAlex, Crossref, subject indexes; citing and cited work | IDs verified in two indexes; full text for the key ones |
| Protocols and specs | MCP, A2A, IETF drafts, W3C/WebAuthn, and the specs tools depend on | Read the version that applies; note what it does not define |
| Package registries | npm, PyPI, crates.io and others relevant to the field | Download trend, release cadence, last release, maintainers |
| Plugin and extension stores | VS Code, Chrome and Firefox, MCP directories, Claude and Cursor plugin lists | Install counts, last update, complaints in reviews |
| Company and lab blogs | Anthropic, OpenAI, Google, Cursor and others in the field | Engineering posts over announcements; dated |
| Official vendor docs and terms | What is supported or allowed | Quote the clause and its date; terms can rule an option out |
| News | Fast-moving launches, acquisitions and deprecations | Two independent outlets for anything consequential |
| Developer communities | X (by engagement), Hacker News (points), Reddit, Stack Overflow, GitHub issues | Link every thread; real complaints over praise |
| Data and benchmarks | Datasets, leaderboards, independent evaluations | Who ran it, on what, reproducible or not, relevant to the user's task |
| Defunct and historical work | Archived repos, discontinued products, archive.org snapshots, patents | When and why it died; what is worth borrowing; status label |
| Adjacent fields and other terms | The same problem under other names; deterministic and non-LLM methods; other languages | Log the alternate terms searched |
| Hands-on measurement | Running the top candidates on a scratch folder | Only when safe and allowed |
