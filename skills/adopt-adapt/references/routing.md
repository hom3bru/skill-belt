# Routing: which recipient profile(s) apply

Run this before §2 of SKILL.md. Output a **ROUTING** block before any donor work. Project-specific identity signals live in each profile's **Routing signals** section. Read them together in the routing index: `python -B "<skill-directory>/scripts/aa.py" routing-index` prints every installed profile's section, generated from the profiles so it cannot drift. Then read only the profiles you select, in full. Without Python, search `profiles/` for `## Routing signals` and read just those sections.

## 1. Signals (collect all, then decide)

| Signal | Evidence to record | Points to |
|---|---|---|
| User names a recipient ("for project X", "for my coding workflow") | quoted words | that profile, **high** |
| User names an installed skill as the recipient, or supplies its identified package root | quoted words, root and inspected `SKILL.md` identity | that skill's profile, **high** |
| Explicit mention of this skill as the object ("improve adopt-adapt", "review your skill", a path to an adopt-adapt bundle) | quoted words or path | `self`, **high, explicit** |
| cwd / repo identity or target paths matching a profile's routing signals | the matched file or path | that profile, high (medium when only wording matches) |
| Host-config paths: `~/.claude`, `~/.codex`, `~/.agents`, `config.toml`, hooks, CLAUDE.md | path | `coding-workflow`, high, unless the target is an identified named recipient package inside them |
| Donor type: agent skill, prompt pack, MCP server, Claude/Codex plugin, dev CLI | donor files (`SKILL.md`, `.mcp.json`, `plugin.json`) | `coding-workflow`, medium; `self` only as a **candidate** (never selected without explicit intent) |
| Donor domain matching a profile's stated scope | donor README/paths | that profile, medium (low for adjacency) |
| Donor is closed-source product / SaaS / binary-only | no public core LICENSE+tree; marketing+docs only | all plausible profiles; set `donor_mode: closed-source-osint` ([closed-source](closed-source.md)) |
| Donor is website / web app / docs portal | URL host; HTML app; needs HAR/DevTools | same + [web-forensics](web-forensics.md) |
| None of the above | — | `generic` (or OPPORTUNITY, no fit score); a request to build a new product from several sources → suggest frankenmine; recovering how one opaque product works → suggest reverse-engineer-anything |

Confidence: **high** = user named it or the cwd/target path is inside that recipient; **medium** = donor domain or wording matches a recipient's documented scope; **low** = plausible adjacency only. Every profile in the set carries its evidence strings (aa.py `routing[].evidence`).

## 2. Decide

1. Explicit user naming wins and is never dropped. Autodetected profiles are **added** only at medium+ unless the user asked for breadth. A named recipient package overrides generic host-path and outer launch-repository hints for that target; add another profile only for a separately requested recipient or receiving seam. A donor mentioning a recipient's name does not make it a recipient.
   An explicitly supplied recipient root/rules wins over the outer cwd. A fixture-only request does not authorize importing a live project's identity or claiming its wiring; use generic until that identity is established. Donor domain is a search/routing hint, not proof of recipient identity or a reason to reject a transferable part.
2. **Never select `self` without explicit intent** (SKILL.md §0.9). A donor that is a skill makes `self` a candidate only: mention it as "possible SELF lesson, not evaluated" and stop there.
3. Ask the user **only** when a wrong route has real consequence: (a) the plan would touch a governed, frozen or locked-perimeter path named in a profile; (b) `self` is plausible but not explicit; (c) the top two candidates have *opposite* hard rules for the same artifact and the user must pick. Otherwise proceed with all plausible profiles and mark low-confidence ones `(low)` in every heading.
4. Low-confidence profiles get the shared ledger plus a short fit note; they are not given ADOPT/ADAPT without an inspected receiving seam. Claims of actual wiring or execution still need the corresponding evidence (SKILL.md §0.7, §8).

### Named skill recipient roots

A skill recipient's profile gives root hints and seams. Resolve the user's explicit root first, read its current `SKILL.md`, README and rules, and bind the exact files/hashes and dirty state used; mirrors and old builds are not authority, and an absent root is recorded as unknown, never replaced by another build. `aa.py` validates profile names and routing evidence only (structured records need a routing entry per named skill recipient); it discovers, activates and certifies nothing. Wiring paths or routing entries starts no review and authorizes no implementation, installation, synchronization or activation; the routing update itself follows adopt-adapt's self-release gates. SELF means only adopt-adapt itself with explicit intent.

## 3. Multi-path execution

```
ROUTING block (profiles, confidence, evidence)
  └─ ONE shared donor ledger per source: identity/pin, coverage, due-diligence,
     injection screen, five lenses on the donor (SKILL.md §2, §3, §5 donor half)
  └─ per recipient R (fresh context of R's profile only):
       R snapshot · R hard rules · R gates · R rubric score · R verdict · R transfer plan + acceptance test
  └─ CROSS-RECIPIENT SUMMARY: per mechanism, verdict per recipient;
     flag CONFLICT when they differ, and say which recipient rule causes it
```

No bleed: a recipient's rule, flag, perimeter or rubric is applied only to that recipient. Refuse, for example: one recipient's egress or privacy perimeter applied to another; a no-dependency rule applied to a recipient whose dependency rule differs; one project's rule (such as deterministic extraction) applied lab-wide; a donor scored on another profile's rubric. Recipient-side claims cite only that recipient's files; `aa.py` rejects a `recipient_claims` id whose subject is another recipient, and rejects READY items for one source whose primary donor receipts differ.

Typical conflicts to surface, not resolve silently: an anti-detect crawler → algorithm-only ADAPT where a profile permits it vs not applicable where it forbids it; a Python library → attributed port where dependencies are frozen vs DISCARD where a new framework is banned; a hosted service → DISCARD everywhere unless a profile records it as already paid.

## 4. Output

State the routing set and evidence first, e.g.:
`ROUTING: project-a (high: cwd is its repo; user said "for project A") · lab-b (medium: donor is an experiment harness) · coding-workflow (low: donor is a CLI) · self: not selected (no explicit intent)`
