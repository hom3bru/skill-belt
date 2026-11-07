# Harbor design record (mp-record-6a1)

## Overview

A calm plans page and app shell for a team calendar.

```json tokens
{
  "format": "westack-design-record-1",
  "colors": {"background": "#FFFFFF", "foreground": "#111827", "primary": "#1D4ED8", "on-primary": "#FFFFFF"},
  "spacing": {"base": "4px", "2": "8px", "4": "16px"},
  "rounded": {"md": "6px"},
  "motion": {
    "overshoot": "never",
    "scale": "never",
    "pointer_following": "never",
    "zoom_transition": "allowed",
    "except": {"scale": ["dock"]},
    "decided_by": "user",
    "date": "2026-10-12",
    "reason": "the owner wants nothing to bounce or grow, apart from the app dock's magnifying items"
  },
  "omitted": {"Elevation": "flat surfaces", "Components": "no component entries yet"}
}
```

## Colors

Ink on white; one blue for actions.

## Typography

System sans-serif.

## Layout

A 4px step.

## Shapes

6px corners.

## Do and Don't

Do change colour or opacity on hover. Don't let anything bounce.
