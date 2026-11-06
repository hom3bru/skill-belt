# Host adapters (C11)

Documentation checked 2026-10-28; one Claude Code probe run the same day. [capabilities.json](capabilities.json) is the machine-readable matrix. A capability counts as available only after a harmless probe succeeds in this session (listing browser tabs, `git worktree list`); unknown means unsupported.

| | Claude Code | Codex | Cursor |
| --- | --- | --- | --- |
| Skill roots (user; project) | `~/.claude/skills`; `.claude/skills` | `$CODEX_HOME/skills` and `~/.agents/skills`; `.agents/skills` | `~/.cursor/skills`; `.cursor/skills` and `.agents/skills` |
| Explicit invocation | `/westack` | host picker, `$westack` where supported | `/` picker |
| Explicit-only router | `disable-model-invocation: true`, observed honoured (2.1.310) | per-skill `agents/openai.yaml` policy (documented; not set or probed) | not verified |
| Actual invocation | observed: typed `/westack` loaded the router; an implicit request did not. Sub-skills: listed by the host in smoke campaigns on 2.1.310, bodies not probed | blocked: two read-only `codex exec` runs failed with `model_not_found`, for the configured model and for `--model gpt-6-luna` (codex-cli 0.142.5, 2026-10-29; usage limit not tested). Both times Codex cut its skills list at a 2% budget, listing no westack entry (see `discovery`) | not-run: editor CLI only, no headless agent CLI |

On all three hosts the package installs no hooks and cannot enforce a denied path (unsupported); probe the session for subagents, sandbox and background runs. Workers start only when the user asks, and the report says whether the work ran inline or with workers, and why (`westack-orchestrate`).

Install with `tools/install.py` (dry run by default); the router and its sub-skills share one root, so a sub-skill finds its core beside it. `scripts/registry.py` reports what is on disk; the host's own listing is what is loaded.

The Claude probe (`tools/host_probe.py`) ran `claude -p` with no bypass flag. Project-only settings still loaded the user's global instruction file: not isolated from user memory.

capabilities.json also records, per host and each as `unknown`, `documented` or `probed` with its source: instruction files loaded and whether their rules survive compaction or reach subagents (a rule that must survive goes in a channel known to), hook events and files read, honoured front-matter fields, a delegation adapter, and install, invocation and isolation outcomes apart, with the first failure. `not-applicable` is not `unknown`; an optional capability not run reads `skipped`, never passed.

## Browser drivers, in order

1. A browser tool the host gives this session (a browser pane, a Playwright or Chrome DevTools MCP server).
2. An installed Playwright the project already uses.
3. A third-party browser binary, only through the [defer map](../references/defer-map.json) and with consent.
4. None: browser checks are reported not-run.

How to use the one you get (the grant, the probe, the environment record, snapshots and annotated screenshots): [browser](../references/browser.md).

## Permission surfaces

Codex permission profiles govern local commands only. MCP servers, connectors, the browser, computer use and web search each have their own controls, and network domain rules apply only while the proxy is active (OpenAI permissions documentation, read 2026-10-28; not runtime-qualified). A path restriction on local commands says nothing about those surfaces; `permission_surfaces` in capabilities.json records the split.

Whether an alternate tool can bypass a path restriction needs an independently confirmed host denied-path boundary to test; this package has none, so that is blocked/unsupported. A diagnostic path check is not a sandbox. Never attempt forbidden writes to "test" a boundary outside an authorized disposable environment.

Sources: [OpenAI skills](https://learn.chatgpt.com/docs/build-skills), [Claude Code skills](https://code.claude.com/docs/en/skills), [Cursor skills](https://cursor.com/docs/skills). Documentation shows documented behaviour only, not closed-source internals or this package's effectiveness.

## Hook contract

westack installs no hooks; this is the contract for a guard hook the user installs, from Claude Code and Codex documentation and public source read 2026-10-28, not a probe here (Cursor not verified).

- A guard hook blocks with the host's blocking code (exit 2 on Claude Code and Codex), including when it cannot parse its input (exit 2, never 0); exit 1 only informs the user and lets the action proceed, so it fails open.
- A hook that crashes, times out or prints output the host cannot read counts as failed: block the action and report "guard blocked" ([guards](../references/guards.md), which also covers probing the gate).
- A hook that rewrites a tool's output and returns something malformed leaves the original output unchanged; never rely on a rewrite to remove content.
- Unverified guidance, not a probe: per host and event, record whether a hook can block, annotate or only observe, and ask for no more. A guard hook answers deny or no opinion, never allow; an earlier allow or async hook can leave its gate dead. Guards are independent, idempotent and print only standard fields.
- A stop hook the user installs follows the release rule in [durable](../references/durable.md): it gates only turns that edited files, blocks once naming the missing evidence, then lets the turn end and records the gap.

## A fresh reviewer, per host

[critique](../references/critique.md) needs a new agent given the brief only. The setting that gives one:

| Host | Setting | Evidence |
| --- | --- | --- |
| Claude Code | Agent tool with no `subagent_type` or a typed agent, brief only; headless, a new `claude -p`. Never `fork`, `--continue`, `--resume` or `--fork-session` | tool description (2.1.310); one nonce probe 2026-10-29, negative, no fork control |
| Codex | unknown | not probed; CLI blocked here |
| Cursor | unknown | not verified |

Unknown means unsupported: record the review as self unless the user starts a new session from the brief alone. A new agent can still read the instruction and memory files its host loads: list them in `coverage`. To qualify a fresh-agent claim, plant a unique marker only in the parent, ask the child for it and read the child's own transcript: a forked child reports it, and a hidden transcript leaves the level unverified. These settings are advice, not a boundary, and do not cover what the agent can read.

## Control labels

Every control named here is a boundary, a heuristic or advice. A boundary is the host or operating system refusing the action: only the host's permission settings and sandboxes can be one, and only after a probe; a sandbox is isolation only if it limits both filesystem and network. A heuristic catches likely cases (this package's path, scope and fingerprint checks). Advice is prose. The threat model is a well-meaning agent that errs or reads hostile text, not a determined attacker on the machine. Each note ends with what it does not cover: for the package's checks, hard links, a change between check and use, other tools or processes, and the MCP, browser and web surfaces above. A heuristic passing is inconclusive for safety, never a safety result.

Provenance: C11 in provenance/facility-donors.json.
