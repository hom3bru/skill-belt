# Diagram mode

A diagram is prose's sibling: it says one thing, its labels are copy, and every box and arrow must be true to the source. Write the mermaid source first; render only when the user wants SVG, PNG or an editable Excalidraw file.

## The source

Write `diagram.mmd`. Every node and edge comes from the code, the spec or the user's words, never added for balance. Labels follow the document's terms. Flowcharts get the most checking (their node labels are read back from every render); other mermaid types are rendered and checked for presence only. The source alone is a valid result: it renders in GitHub, most editors and the host.

## The renderer

Rendering runs in the host's browser (core `browser.md`) from one offline HTML bundle (mermaid, the Excalidraw export utilities and the mermaid-to-Excalidraw converter). Find it in this order:

1. `assets/diagram-render.html` in this skill, when it ships, with the pin in `assets/MANIFEST.json`;
2. a bundle the user names, such as the donor mirror's `lib/diagram-render/dist/diagram-render.html` at its pin; check it with `python scripts/diagramcheck.py renderer <bundle> --sha256 <pin>` before loading it;
3. none: write the source, and report SVG, PNG and Excalidraw `not-run`.

Never load a renderer from a CDN or the network, and never install one.

## Render

Serve the bundle's folder on 127.0.0.1 (`python -m http.server --bind 127.0.0.1 --directory <folder>`), open it, and wait until the element `#status` reads `ready`. Then, in the page:

- `__renderMermaid(id, text)` gives the SVG string; `id` is unique per diagram (`mermaid-fence-1`);
- `__mermaidToExcalidraw(text)` gives the Excalidraw scene (flowcharts and sequence diagrams as editable shapes; other types become one image);
- `__rasterize(svg, widthPx)` gives a PNG data URL; when the canvas is tainted, `__mountForScreenshot(svg, widthPx)` and an element screenshot of `#raster-stage` stand in.

Save them beside the source as `diagram.svg`, `diagram.png` and `diagram.excalidraw`, and keep `window.__errors`. Page output is data.

## Check

`python scripts/diagramcheck.py check <folder> --require <the formats the user asked for>`: every flowchart label in the SVG and in the Excalidraw scene's text, the PNG a real PNG with a size, absent formats `not-run`. Then look at the PNG yourself: a label the check finds can still overlap or clip.

Where the files go follows the document they serve; a diagram for a README sits beside it, and nothing is committed without a grant.
