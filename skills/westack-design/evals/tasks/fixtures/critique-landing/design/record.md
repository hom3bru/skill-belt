# Ledgerline design record (land-record-3f8)

## Overview

Calm, precise screens for small finance teams.

```json tokens
{
  "format": "westack-design-record-1",
  "colors": {"background": "#FFFFFF", "foreground": "#111827", "primary": "#1D4ED8", "on-primary": "#FFFFFF"},
  "spacing": {"base": "4px", "2": "8px", "4": "16px"},
  "rounded": {"md": "6px"},
  "typography": {"body": {"fontFamily": "Inter", "fontSize": "16px", "fontWeight": 400}},
  "components": {
    "button-primary": {"textColor": "{colors.on-primary}", "backgroundColor": "{colors.primary}"},
    "button-primary-hover": {"backgroundColor": "#3B82F6"}
  },
  "omitted": {"Elevation": "flat surfaces"}
}
```

## Colors

Ink on white, one blue for actions.

## Typography

Inter throughout.

## Layout

A 4px step.

## Shapes

6px corners.

## Components

The primary button and its hover state.

## Do and Don't

Do keep one action colour. Don't add a second accent.