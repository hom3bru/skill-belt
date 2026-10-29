# Target profile: westack

Use `westack` when the user names the westack workflow skill package as the recipient of an improvement. Use the existing [generic rubric](generic.md). Keep westack's own rules, evidence and transfer seam separate from Frankenmine, coding-workflow and SELF; this recipient profile does not invoke westack's engineering workflow.

## Routing signals
The user names westack as the recipient of an improvement, or supplies its package root with an inspected `SKILL.md` identity → `westack`, high; this overrides host-config paths and the outer launch repository for that target. A donor that merely mentions westack does not make it a recipient.

## Root and identity

Resolve the root in this order: (1) a root the user supplies; (2) the `westack` entry in `local-roots.json` beside this profile, when that private file is installed (current source, earlier build, fallback and installed-mirror hints; a historical build is never authoritative by default); (3) a sibling skill-belt checkout's `skills/westack`; (4) otherwise ask the user. Hints do not implement path discovery or prove authority, existence, installation or synchronization. At review time read current `SKILL.md`, README if present, applicable AGENTS.md / CLAUDE.md and package rules; snapshot the selected root, available Git identity, dirty files relied on and exact hashes. If the selected source is absent or ambiguous, record the gap rather than inventing status or silently switching to a historical build. The outer launch repository does not establish an application-code receiving seam.

## Receiving seams and scope

Follow the live entrypoint's references and inspect the actual modules, contract, examples, host declarations, validator and tests needed for the proposed transfer. Planning, evidence, review and verification are possible seams, not established behavior until inspected. Host-specific paths are local hints; claims of host capability or activation require separate evidence.

Apply westack's current rules and consent boundaries only to westack. A request just to wire its paths authorizes adopt-adapt routing maintenance; it starts no donor assessment or engineering workflow and authorizes no westack edit, helper execution, installation, mirror synchronization or activation. Applying the authorized adopt-adapt update follows its existing self-release gates. Future assessment produces a proposal unless recipient implementation is separately authorized. A skill recipient is not SELF; SELF refers only to explicit adopt-adapt improvement.
