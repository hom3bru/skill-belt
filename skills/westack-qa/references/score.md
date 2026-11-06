# The health score

`scripts/qacheck.py score` computes it from the report; `validate` refuses a report whose score disagrees. The numbers are in [thresholds](thresholds.json).

## Severity

- **critical:** data loss, a security or privacy exposure, or the app unusable for everyone.
- **high:** a core task blocked with no workaround.
- **medium:** a task impaired, with a workaround.
- **low:** cosmetic, copy or friction, with the task still done.

Take the highest that applies, and say what was lost and whether a workaround exists.

## Counting

- One root cause is one issue, even when it shows on several pages. File it under the first category that fits, in this order: links, accessibility, functional, performance, visual, content, ux, console.
- Console errors are counted by distinct message and source; warnings and errors already filed elsewhere are not counted.
- Broken links are counted by distinct destination; an expected redirect to a sign-in page is not broken.

## Category scores

- **Console:** 0 errors 100, 1-3 errors 70, 4-10 errors 40, more 10.
- **Links:** 100 less 15 per broken destination, never below 0.
- **Every other category:** 100 less 25, 15, 8 or 3 per confirmed critical, high, medium or low issue, never below 0.

## The final score

The weighted average over the tested categories only (weights: console 15, links 10, visual 10, functional 20, ux 15, performance 10, content 5, accessibility 15), rounded half up at the end. Untested categories are left out, never counted as 100. When some are left out the score is provisional; when none was tested it is "not scored". Two scores compare only when their coverage and environment match.
