# Host capability matrix

Documentation checked 2026-10-26. These are manual compatibility declarations, not runtime-qualified adapters. [capabilities.json](capabilities.json) is the machine-readable matrix.

| Capability | Codex | Claude Code | Cursor |
| --- | --- | --- | --- |
| Project discovery documented | .agents/skills/westack | .claude/skills/westack | .cursor/skills/westack or .agents/skills/westack |
| Explicit invocation | host skill picker / $westack where supported | /westack | / picker → westack |
| Portable instruction body | supplied | supplied | supplied |
| Actual local invocation tested | not-run | not-run | not-run |
| Approvals/filesystem protection | native session policy; inspect | native configuration; inspect | native configuration; inspect |
| Exact per-task denied path enforced by package | unsupported | unsupported | unsupported |
| Hooks installed by package | none | none | none |
| Subagents/context isolation | probe session; unknown here | probe session; unknown here | probe session; unknown here |
| Durable state | optional local record, host-owned storage | same | same |
| Background execution/artifact delivery | probe session | probe session | probe session |

Unknown facilities cannot be assumed. Do not invent parallel results or host syntax. When independent review is required and unavailable, report the limitation. A supported single-agent self-review can proceed when the task permits it, labeled accurately.

Codex permission profiles govern local commands only. MCP servers, connectors, the browser, computer use and web search each have their own controls, and network domain rules apply only while the proxy is active (OpenAI permissions documentation, read 2026-10-28; not runtime-qualified). A path restriction on local commands therefore says nothing about those surfaces; `permission_surfaces` in capabilities.json records the split.

Testing whether an alternate tool can bypass a path restriction requires an independently confirmed real host denied-path boundary. This package has none, so that qualification is blocked/unsupported. A diagnostic path check is not a sandbox. Do not attempt forbidden writes to “test” a boundary without an authorized disposable qualification environment.

Sources: [OpenAI skills](https://learn.chatgpt.com/docs/build-skills), [Claude Code skills](https://code.claude.com/docs/en/skills), [Cursor skills](https://cursor.com/docs/skills). Feature availability varies by version and session. Current source documentation is evidence for documented discovery only, not closed-source internals or this package's effectiveness.

