# Page runs

Use the host's browser through core `browser.md` (grant, driver, environment). Load the page fresh for every run with a cache-busting query, or with the cache state the claim is about, and record which.

## What to read in the page

After load, run one script in the page and keep its JSON (stringify inside the page: performance entries do not cross the bridge as objects):

- **Navigation:** `performance.getEntriesByType("navigation")[0]` gives `ttfb_ms` (responseStart), `dom_content_loaded_ms` (domContentLoadedEventEnd) and `load_ms` (duration).
- **Paint:** the `first-contentful-paint` entry's startTime is `fcp_ms`.
- **LCP:** a buffered `PerformanceObserver` for `largest-contentful-paint`; the last entry's startTime is `lcp_ms`. Give it up to three seconds; none is N/A, never zero.
- **CLS:** a buffered observer for `layout-shift`; sum the values of entries without recent input as `cls`.
- **Resources:** count `total_requests`, sum `transfer_bytes`, and sum the transfer sizes of script and stylesheet resources as `js_bytes` and `css_bytes`; keep the fifteen slowest by duration as the limiter's first leads.

Interaction to Next Paint needs real interactions; it is N/A unless you script them and say which. When the host offers a performance trace or a Lighthouse audit (Chrome DevTools MCP), it is a stronger source for the limiter; name it in the run file.

## Budgets

`perfcheck.py budget run.json` checks medians against `thresholds.json`: FCP 1.8 s, LCP 2.5 s, CLS 0.1, JavaScript 500 KB, CSS 100 KB, transfer 2 MB, 50 requests. At or over budget fails, from 90% it warns. The grade is the share of measured metrics below budget: A all, B two-thirds, C half, D fewer. Budgets are a floor of sanity; the comparison with this page's own baseline is the verdict.
