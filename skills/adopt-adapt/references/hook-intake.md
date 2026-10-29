<!-- Policy for any hook transplanted from a donor. Evidence for each rule (Codex and gstack hook implementations at their reviewed pins) is archived in historical-findings.md section D. -->
# Hook intake policy

A donor hook is never "adopted as-is". A plan that transplants a hook must state each rule below as met, or the result is ADAPT-with-prerequisite. aa.py checks `ledger.hooks[]`.

| # | Rule |
|---|---|
| H1 | **Trust by content hash — of the config entry AND every file it runs or loads.** Record `content_sha256` of event+matcher+command, plus `files[]` = sha256 of the hook script and every file it sources/imports; run only when all equal the approved values |
| H2 | **Any edit to the config entry or to any hashed file revokes approval** — only true when H1 hashes the files; Codex alone does not give this |
| H3 | **Project config cannot approve.** `approved_by ∈ user|session-flag` only |
| H4 | **Strict output schema**: non-object/unknown fields/wrong types rejected; every block needs a non-empty reason; unsupported fields fail the run |
| H5 | **Deny wins**, then most-specific allow, else no verdict |
| H6 | **Visible log of every approval naming the hook** (`source=hook:<id>`), durable on disk |
| H7 | **Environment allowlist**, not full env or deny-list |
| H8 | **Fail toward asking, never fail open**: errors/ambiguity pass through to the user; guards fail closed |
| H9 | **Bound everything**: stdin cap (1 MiB), bounded walk (bound hit = unscanned, not clean), output cap (8 KiB at UTF-8 boundary), one deadline under host kill, process-group kill on timeout |
| H10 | **Untrusted envelope**: only a string context field accepted from a vendor; decision/continue/systemMessage dropped; control chars stripped |
| H11 | **Fail-closed egress receipt** (sha256 + bytes) before any data leaves; secret scan raw + decoded |
| H12 | **Parse-check before going live** with the shebang's interpreter; registration list equals checked list |
| H13 | **No auto-answer.** A hook may not answer the user's question; env-var auto-choose is INJECTION-RISK |
| H14 | **Stop hooks need a hard iteration cap > 0** |
| H15 | **Abstain correctly** (empty stdout, exit 0; not `defer`) |

| H16 | **Invalid matcher is an error, never match-all** |
| H17 | **Quote substituted paths**; `${PLUGIN_ROOT}`-style values are shell-quoted before use |
| H18 | **Broken hook config fails closed** (bad hooks.json/TOML, empty command → error, not warning) |
| H19 | **Managed/forced hooks are listed in the ledger with source and cannot be silently auto-trusted by allowlist name** |
| H20 | **Durable per-session record of every hook run and decision** (adopt-adapt ledger, not host logs) |

Donor licences still decide whether any hook text may be copied; rule wording here is policy, not a licence finding about a donor.
