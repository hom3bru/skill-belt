# Host capability matrix

Documentation checked 2026-10-26. These are manual compatibility declarations, not runtime-qualified adapters. [capabilities.json](capabilities.json) is the machine-readable matrix.

| Capability | Codex | Claude Code | Cursor |
| --- | --- | --- | --- |
| Project discovery documented | .agents/skills/estack | .claude/skills/estack | .cursor/skills/estack or .agents/skills/estack |
| Explicit invocation | host skill picker / $estack where supported | /estack | / picker → estack |
| Portable instruction body | supplied | supplied | supplied |
| Actual local invocation tested | not-run | not-run | not-run |
| Approvals/filesystem protection | native session policy; inspect | native configuration; inspect | native configuration; inspect |
| Exact per-task denied path enforced by package | unsupported | unsupported | unsupported |
| Hooks installed by package | none | none | none |
| Subagents/context isolation | probe session; unknown here | probe session; unknown here | probe session; unknown here |
| Durable state | optional local record, host-owned storage | same | same |
| Background execution/artifact delivery | probe session | probe session | probe session |

Unknown facilities cannot be assumed. Do not invent parallel results or host syntax. When independent review is required and unavailable, report the limitation. A supported single-agent self-review can proceed when the task permits it, labeled accurately.

D12 requires an independently confirmed real host denied-path boundary before testing alternate-tool writes. This package has none; qualification is blocked/unsupported. A diagnostic path check is not a sandbox. Do not attempt forbidden writes to “test” a boundary without an authorized disposable qualification environment.

Sources: [OpenAI skills](https://learn.chatgpt.com/docs/build-skills), [Claude Code skills](https://code.claude.com/docs/en/skills), [Cursor skills](https://cursor.com/docs/skills). Feature availability varies by version and session. Current source documentation is evidence for documented discovery only, not closed-source internals or this package's effectiveness.

