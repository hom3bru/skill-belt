<!-- Generic profile: an engineer's Claude Code / Codex / Cursor workflow. Host rules are read live from the user's own instruction and settings files; documentation facts were fetched 2026-10-09. -->
# Profile: coding-workflow (Claude Code / Codex / Cursor as the recipient)

## Routing signals
Host-config paths (`~/.claude`, `~/.codex`, `~/.agents`, `config.toml`, hooks, CLAUDE.md) → high, unless the target is a named recipient package inside them; a skill, prompt-pack, MCP, plugin or dev-CLI donor → medium. Legal overlay: injection, undisclosed persistence or an unclear skill licence raises the flag.

Host = where this run executes; recipient = the workflow being improved. A Codex host can assess Claude tooling and vice versa.

## 1. Hard rules and perimeter
| Rule | Source |
|---|---|
| The user's own instructions bind the plan: completion-proof, plan-tracking, browsing-tool, delegation and shell rules | user-level CLAUDE.md, AGENTS.md, `~/.codex/AGENTS.md` (read live; cite file:line) |
| The host's tool surface decides viability (for example a denied Bash tool or a PowerShell-only host) | `~/.claude/settings.json` and equivalents |
| Existing hooks are preserved: new hooks append, never replace (HOOK-CONFLICT) | settings hook blocks |
| Codex sandbox, Windows-sandbox and multi-agent settings shape any Codex plan | `~/.codex/config.toml` |
| Workflow patterns never cross into an application runtime governed by another profile (PERIMETER-LOCKED / profile bleed) | adopt-adapt rule |
| Persona/profile capture is opt-in only (PROFILE-CAPTURE) | adopt-adapt rule |
| No new paid elements | SKILL.md §0.3 |

## 2. Host facts (verify live on the claimed host)
- Read the target host's actual settings, skill roots, hook configuration and installed copies; record unread settings as UNKNOWN.
- Codex docs (fetched 2026-10-09): user skills load from `$HOME/.agents/skills`; same-name skills are **not merged** and can both appear; disable with `[[skills.config]] path=… enabled=false`; restart after config change; the initial skill list is capped and descriptions are shortened first. Which duplicate Codex actually loads needs a runtime trace.
- Claude Code docs (fetched 2026-10-09): personal > project for the same name; the listing truncates description text; `disable-model-invocation`, `skillOverrides` (`"off"`) and `/skill-doctor`; with/without-skill comparison via `skillOverrides` off.
- Agent Skills spec: `name` ≤64 chars and must match the directory; `description` ≤1,024; metadata values are strings; SKILL.md <500 lines; references one level deep.

## 3. Rubric (coder rubric inherited from adopt-adapt 2.11; anchors uncalibrated)
| Component | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Relevance to a real workflow pain (0-3) | none observed | generic productivity | named recurring pain in the user's files (e.g. duplicate skills, verification gaps) | pain with an observed incident/log |
| Novelty vs current hosts (0-2) | host already has it (e.g. bundled `/verify`, `/skill-doctor`) | partial | absent on every named host | — |
| Platform viability here today (0-3) | won't run (needs a tool the host denies, cargo, macOS) | runs with a named prerequisite | runs on one named host | runs on every host the user named |
| Surface / reversibility / no runtime bleed (0-2) | edits global settings/hooks irreversibly or touches an application runtime | reversible with manual steps | single folder, uninstall = delete/`enabled=false` | — |
| Penalty | −1 FOOTPRINT / HOOK-CONFLICT; −2 PLATFORM-BLOCK / SURFACE-MISMATCH | | | |

## 4. Gates and critical fails
Skill-Injection screen (SKILL.md §3) on every skill/MCP/plugin donor; SUPPLY-CHAIN-RISK for `npx …@latest` / unpinned installers (check the host's own config too); PLATFORM-BLOCK; SURFACE-MISMATCH (for example a Bash hook on a host that runs PowerShell); HOOK-CONFLICT; DUPLICATE-NAME (installing a same-name skill without disabling the other: Codex doesn't merge); `allowed-tools` self-grant in a repo skill (Claude docs: workspace trust doesn't gate it). Critical fail: recommending install without naming destination root, disable/rollback path, and load-identity check.

## 5. Seams and valid plans
Seams: a skill folder under one canonical root + per-host adapter; `[[skills.config]]` toggles; Claude `skillOverrides`; hooks (append-only); `agents/openai.yaml` `allow_implicit_invocation`. Valid plan: exact destination(s); one canonical source with byte-equality test across copies; disable path for duplicates; restart requirement; acceptance test = paired with/without-skill run on held-out prompts (Claude docs "Evaluate and iterate"), plus a trigger check that fails when the description is removed.
