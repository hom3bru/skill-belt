# Variants board

In direction mode, when the user wants to choose by looking, build a few variants of one surface and put them side by side. Key-free: every variant is hand-built HTML and CSS. No image-generation or vision service is ever called (those are paid), and no variant loads anything from the network.

## Build

1. **One brief, several directions.** From the surface brief, write three variants by default (two to five), each taking one named direction (for example "editorial, one accent", "dense table", "card grid"), and the same content in each. A variant is one self-contained HTML file: inline CSS, local or inline images, system fonts unless the brief names others that are already in the project.
2. **Screenshots.** Load each variant through the host's browser (core `browser.md`) at one viewport and capture it; record the viewport and the screenshot's SHA-256. A hidden or headless pane that cannot paint gives no screenshot: say so and use a driver that can.
3. **The board.** `board.html` shows every variant's screenshot (or the variant itself in a frame) with its id and direction. Open it as a local file, or serve the folder with `python -m http.server --bind 127.0.0.1` when the browser cannot open files.
4. **Manifest.** `variants.json` (format `westack-design-variants-1`): `surface`, `generator` (always `html`), `variants` (id, file, direction, viewport, screenshot, screenshot_sha256), `board`, and once the user has chosen, `feedback` (`chosen`, `reasons` in the user's words, `taste` notes).

The folder goes where the user says, or the evidence folder; never into the product's source tree unless the user asks.

## Choose

Show the board and ask which direction to take and why. Record the answer in `feedback`. A taste note ("prefers one accent colour", "no gradients") is a proposal for the design record ([system](system.md)): list it for the user to accept, never write it silently. A mix ("the header of v1 with the cards of v3") is a new variant to build and show, not a decision.

## Check

`python scripts/designcheck.py variants <folder>`: at least two variants with distinct ids, each file present and self-contained, each with a direction, one viewport for all, screenshots whose SHA-256 matches, a board that shows every variant, a chosen id that is on the board with reasons, and `generator` `html`. Taste notes come back as proposals. It renders nothing and does not judge which variant is better.

The chosen variant is a direction, not a build: implementing it is westack-build's job, and a critique of what gets built is critique mode.
