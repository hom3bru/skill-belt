<!-- R4: new. Chrome DevTools / web forensics. -->
# Web forensics for website / web-app donors

Pair with [legal.md](legal.md) and [closed-source.md](closed-source.md).

## Authorization
Only **public** pages or **user-authorized** accounts scoped for the run. No auth bypass, fuzzing, or active vuln scanning of third parties. Honor robots by default (RFC 9309: not authorization, still skill policy; apply stricter inspected recipient rules).

## Host tools
### Chrome DevTools MCP (Claude/Codex)
- Official: https://github.com/ChromeDevTools/chrome-devtools-mcp (Apache-2.0; API 2026-10-09: ~53k★, v1.10.1 observed).
- `claude mcp add chrome-devtools --scope user npx chrome-devtools-mcp@latest`
- `codex mcp add chrome-devtools -- npx chrome-devtools-mcp@latest`
- Tools: `list_network_requests`, `get_network_request`, performance traces, `lighthouse_audit`, `take_snapshot`, `evaluate_script`, console, heaps.
- Prefer `--isolated`, `--headless`, `--no-usage-statistics` (stats **on by default** per README 2026-10-09).

### Grok Bot
Use the available browser surface only within the authorized run. Save under the user-selected output root and hash artifacts; do not assume a fixed host path or available subagent.

### Playwright (if present)
`tracing.start({screenshots, snapshots})`; `recordHar` / `routeFromHAR` — https://playwright.dev/docs/api/class-tracing ; https://playwright.dev/docs/mock (fetched 2026-10-09).

## Playbook
1. Pin final URL, title, time PT.  
2. robots.txt, sitemap, llms.txt (https://llmstxt.org/ — voluntary).  
3. Network/API discovery; prefer **sanitized HAR** (Chrome excludes Cookie/Set-Cookie/Authorization by default — https://developer.chrome.com/docs/devtools/network/reference ).  
4. JS bundles + source maps (`sourceMappingURL`, ECMA-426 https://tc39.es/ecma426/ ): reading maps **shipped to a page you may access** is observation of published bytes, **not** a license to relicense/ship; idea-only / SDK license; high expression_risk.  
5. Headers/CSP/cookies (names/flags only). WS/SSE/SW endpoints.  
6. Lighthouse / a11y snapshot.  
7. Passive: DNS, crt.sh CT, Wayback CDX, public GitHub SDK usage — no probing.

## Evidence
Each artifact: path, sha256, bytes, captured_at, source_url, tool, sanitized.

## Rate / PII
Use a conservative request rate (≤1 rps default), follow stricter recipient/site limits, and minimize personal data in reports.

## Output
`web_forensics: {target, robots, artifacts[], apis_observed[], source_maps[], stack_hints[], pii_redaction}`.

## R5: browser-verification patterns (REA rea@1b73b5ab scripts/lib/; GREEN on owned fixtures, YELLOW on third-party sites — legal.md)
- **Privacy default `not_approved`**: accessibility text, console text, body/WebSocket shapes absent unless each is approved (browser-verifier-assertions.mjs:38-43,72-86); passive inspection excludes bodies/storage (verify-real-browser.mjs:123-166). Note gap: URL query tokens retained by design (KP39; verify-real-browser.mjs:114-121).
- **Armed before fire**: trigger the action only after the tool reports "armed"; fail if no armed signal (browser-runtime-e2e.mjs:217-230,276-284).
- **Test the checker**: swap two same-URL transaction IDs → assertion must throw (browser-network-e2e.mjs:80-99).
- **Request counts**: exact per-path server hit counts prove no refetch (browser-network-e2e.mjs:154-168; browser-runtime-e2e.mjs:151; browser-module-e2e.mjs:120-124).
- **Provenance tag ≠ authority claim** (claude-code _base.py:56-67 — idea only); association by server-authored markers, not provider-derived expectations (browser-network-assertions.mjs:14).
- **Ownership-aware cleanup**: an external browser is disconnected, never closed (verify-real-browser.mjs:263-296).
- Declared-secret redaction everywhere a value could leak, incl. names, pointers, base64, hashes (verify-web-network-captures.mjs:205-236 and following).
- **R5.2**: planted canary secrets in every channel for redaction tests (REA fixtures/browser-verifier-site.mjs:131-194); budget exhaustion reported exactly as truncated sections (browser-capture-metadata-budget-e2e.mjs:160-208); shared-context popups/frames give `equality_eligible:false` and comparisons `unknown` (browser-popup-e2e.mjs:216-226). GREEN on owned fixtures; method only elsewhere.
