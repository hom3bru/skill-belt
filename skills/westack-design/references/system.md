# The design record

One plain-text file (DESIGN.md, or the name the project already uses) holds the design system: normative tokens and the prose that explains them. Later work reads it before building and follows it.

## Shape (DG-20)

- **Tokens are JSON** in one or more fenced blocks whose info string is `json tokens`, or in a sidecar `<record>.tokens.json`. The helper is standard-library only and has no YAML parser, so there is no YAML front matter.
- **Sections** are `##` headings in this order: Overview, Colors, Typography, Layout, Elevation, Shapes, Components, Do and Don't. An absent section is declared under `omitted` with its reason; an omission that contradicts the tokens (omitting Colors while defining colours) is a finding.
- **Each key is defined once.** A key repeated in one block or across blocks is a finding; the first stays.
- **Known groups:** `colors`, `typography`, `rounded`, `spacing` (with an optional `base` step), `components`, `omitted`, `derived`, `motion` ([motion](motion.md)), `references`, `invariants` and `signoff` ([direction](direction.md)). A misspelt group (`colours`) is named with its fix, since a reader would see nothing. Token-like values (colours, sizes, type settings) under a key no reader uses are flagged; a custom key holding plain text is kept.
- **References** are written `{colors.primary}`. An unresolved reference or a cycle is an error; chains stop at `ref-depth-max`.
- **Colour pairs.** A role `X` with `on-X` or `X-foreground`, plus `foreground`, `background`, `muted-foreground` and `ring`, so `designcheck.py contrast` can check each pair.
- **Components** list `backgroundColor`, `textColor`, `iconColor` and `typography`. A state is its own entry (`button-primary-hover`) and inherits whatever it does not set from its base (`button-primary`).

```json tokens
{
  "format": "westack-design-record-1",
  "colors": {"background": "#FFFFFF", "foreground": "#111827", "primary": "#1D4ED8", "on-primary": "#FFFFFF"},
  "spacing": {"base": "4px", "2": "8px", "4": "16px"},
  "components": {"button-primary": {"textColor": "{colors.on-primary}", "backgroundColor": "{colors.primary}"}},
  "omitted": {"Elevation": "flat surfaces; no shadows"},
  "derived": ["theme.css"]
}
```

## Promises and sign-off (DG-40)

A direction's invariants sit under `invariants`, one object per promise: `promise`, `widths` in px, `states` when not only the resting state, and `observed_by`, which is `measurement`, `pixel-sample` or `recording`. Acceptance sits under `signoff`: who accepted (`by`), the `date` and the capture ids accepted (`captures`). `designcheck.py record` refuses a promise with no way to observe it or no widths, and a sign-off missing a field. Sign off only valid captures ([rendering](rendering.md), DG-41).

```json
"invariants": [{"promise": "primary button text contrast at least 4.5:1", "widths": [375, 1440], "observed_by": "measurement"}],
"signoff": [{"by": "user", "date": "2026-10-31", "captures": ["C1", "C2"]}]
```

## Frames (DG-22)

Screens compose one set of frame components, and the space between regions comes only from the frame; a screen that departs from it says why in a code comment. Never hardcode a pixel value derived from a token: measure the drawn element or read the token (rule `frame-derived-px`). A data view branches pending, then error, then empty, then rows, since an empty-state sentence shown while loading says something false (rule `frame-false-empty`).

## Derived files

Theme CSS and token JSON are generated from the record and compared, never edited by hand:

```text
python "<this skill>/scripts/designcheck.py" record DESIGN.md --emit css      # print theme.css; you write it
python "<this skill>/scripts/designcheck.py" record DESIGN.md                 # checks the files under "derived"
```

A hand edit shows as a hash that differs from what the record generates. The helper prints and never writes; never load or run the project's Tailwind config or plugins to read a theme.

## Write it after the build (DG-21)

Write or update the record from the shipped artifact, in its own pass. Promote a value only when it recurs for the same role or its computed and declared values agree; a value seen once on one page stays out. Never record a pattern the review refused. Check it against the build:

```text
python "<this skill>/scripts/designcheck.py" record DESIGN.md --built dist/
```

Every colour and length in the record must be used in the built CSS, directly or through a custom property, at least twice.

## Before writing tokens

Find any existing token source first: `designcheck.py tokens SRC --writing NEW_FILE` lists `:root` and `@theme` blocks, token JSON files, a design record and a Tailwind config (named, never loaded) and stops when one exists. Extend that source, or get the user's authorisation to replace it (`--replace-authorised` with their turn).

## Changes are proposals (DG-12)

A new token, variant, suppression or screenshot baseline added to turn a check green is a design decision for the user. Keep the accepted record as the baseline:

```text
python "<this skill>/scripts/designcheck.py" record DESIGN.md --baseline accepted/DESIGN.md
```

The report lists each addition under `proposals` and exits 1 until the user accepts; the accepted record then becomes the new baseline. "0 findings" never hides one.
