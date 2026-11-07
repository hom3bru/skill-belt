# Modes and the run

## Before the first page

- **Target.** A URL the user gave, or the app the user asked you to test. With neither, ask; do not go looking on the network.
- **A local server.** When the user asks you to test their app and it is not running, propose the project's own start command and run it only once they agree; it is a process this session starts. On diff-aware runs with no URL, you may probe the usual local ports (3000, 4000, 5173, 8000, 8080) with one request each, and say which answered.
- **Driver.** Follow core `browser.md`: one harmless probe picks the driver; none answering makes the run degraded. Record the environment before the first capture.
- **Time cap.** quick about 3 minutes, the others about 15 (`thresholds.json`). At the cap, stop probing and report what was not covered.

## Diff-aware scope

Find the base branch, then list what changed: `git diff <base>...HEAD --name-only` and `git log <base>..HEAD --oneline`. Map changed routes, views, components, styles and the services behind them to pages, and add each page's neighbours (what links to it, what it links to). A change with no page behind it (configuration, a backend job) gets a quick run plus the interactions it could affect. Say which files mapped to which pages.

## Orient (every page)

1. Before loading the page, install a console capture where the driver allows it (an init script that keeps `console.error`, uncaught errors and unhandled rejections); otherwise read the driver's console messages after load.
2. Load the page and wait until it is idle. Take the accessibility snapshot (the page's text record) and a screenshot; record their SHA-256.
3. Collect the page's links. Keep same-origin links and drop ones that sign out, delete, remove, cancel or unsubscribe. On a local target, request each once (HEAD, or GET when HEAD is refused): a 4xx, 5xx or error is broken. On a target that is not local, list links as unverified rather than requesting them, unless the grant covers it.
4. Note interactive elements that the snapshot lacks (core `browser.md`): accessibility leads.

## Explore: the per-page checklist

quick skips this; full, diff-aware and regression do it for each page, core flows first.

- **Look.** Layout breaks, clipped or overlapping text, horizontal scrolling, broken images, theme problems.
- **Use.** Every button, link and control: does it do what its label says? A control whose click changes nothing in the snapshot diff is a dead control.
- **Forms.** Empty, invalid and long inputs (local targets, or with a grant). Validation messages, error states.
- **Move.** Back button, deep links, menus; dead ends with no way back.
- **States.** Empty, loading, error and overflowing content.
- **Console.** New errors or failed requests after each interaction.
- **Sizes.** When layout matters, a phone width (375px) and a tablet width as well as the desktop one.

## Document

Reproduce each issue once more before writing it up. For an interaction, keep the before and after snapshots and the diff between them; for something static, one annotated screenshot. Write the issue straight away, with its steps, its evidence and the page. An issue that did not reproduce stays in the report with `confirmed: false`.

## Regression

Run full, then `qacheck.py compare <baseline.json> <report.json>`. It lists fixed issues (in the baseline only) and new ones (in this run only) and the score delta, and refuses when the tested categories or the environment differ. A missing or unreadable baseline blocks the comparison, not the run.
