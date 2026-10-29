# Web forensics for website / web-app donors

Pair with [legal.md](legal.md) and [closed-source.md](closed-source.md).

## Authorization
Only **public** pages or **user-authorized** accounts scoped for the run. No auth bypass, fuzzing, or active vuln scanning of third parties. Honor robots by default (RFC 9309: not authorization, still skill policy; a profile may make it a hard gate).

## Host tools
- **Browser DevTools tooling** (for example Chrome DevTools MCP, Apache-2.0: network requests, performance traces, Lighthouse, snapshots, console): use it only if it is already installed on the host. Installing or registering it is a separate, explicitly authorized task with a pinned version, never `@latest`, plus a disable path; it is not part of an evaluation. Prefer isolated, headless runs with usage statistics off.
- **Playwright (if present):** `tracing.start({screenshots, snapshots})`; `recordHar` / `routeFromHAR` — https://playwright.dev/docs/api/class-tracing ; https://playwright.dev/docs/mock (fetched 2026-10-09).
- Any other browser surface only within the authorized run; save artifacts under the user-selected output root and hash them.

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
Polite rate (≤1 rps default, or the profile's stricter limit); minimize PII in reports.

## Output
`web_forensics: {target, robots, artifacts[], apis_observed[], source_maps[], stack_hints[], pii_redaction}`.

## Browser-verification patterns (GREEN on owned fixtures, YELLOW on third-party sites — legal.md)
- **Privacy default `not_approved`**: accessibility text, console text and body/WebSocket shapes stay absent unless each is approved; passive inspection excludes bodies and storage. URL query tokens can still leak; redact them.
- **Armed before fire**: trigger the action only after the tool reports it is armed; fail if no armed signal arrives.
- **Test the checker**: swap two same-URL transaction IDs → the assertion must throw.
- **Request counts**: exact per-path server hit counts prove no refetch.
- **A provenance tag is not an authority claim**; associate by server-authored markers, not provider-derived expectations.
- **Ownership-aware cleanup**: an external browser is disconnected, never closed.
- **Declared-secret redaction** everywhere a value could leak, including names, pointers, base64 and hashes; test it with planted canary secrets in every channel.
- **Budget exhaustion is reported exactly** as truncated sections; shared-context popups/frames make comparisons `unknown`, not equal.

Source citations for these patterns are archived in `historical-findings.md` section F where an edition ships it.
