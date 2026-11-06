# Motion

Four defaults hold in every project. Everything else is the project's own policy, recorded in its design record with its exceptions and checked against it. Never treat one project's taste as a default for another.

## The four defaults (DG-25)

1. **Hover changes colour and opacity, never a target's box.** Size, padding, margin, border width, font size and scale stay put, so a target never moves under the pointer. Measured: bounding boxes before and during hover are equal at the project's device pixel ratio ([browser](browser.md)). Static lead: rule `motion-hover-box`. An element the project deliberately grows on hover (a magnifying dock, say) is a recorded exception: a waiver on the record whose reason names the page.
2. **Reduced motion goes straight to the end state.** With the preference on, movement does not play; a short change of opacity or colour may stay, since it moves nothing. Anything that moves for more than 5 seconds has a pause control (WCAG 2.2 success criteria 2.2.2 and 2.3.3). Measured in the browser; a grep for the media query does not show that the page stops moving.
3. **One motion owner per property.** A CSS transition, a keyframe animation and a script never drive the same property of the same element at once; when two do, the result depends on timing.
4. **No per-frame layout work.** Nothing reads layout (bounding boxes, offsets, computed styles) or updates framework state on every animation frame. Animate transform and opacity, and pause work that is offscreen. Static lead: rule `motion-per-frame-layout`.

Smooth by elapsed time, never a fixed fraction per frame (DG-39): correctness, not policy (rule `motion-per-frame-lerp`, [rendering](rendering.md)).

## The project's policy (data)

The design record holds the policy in its tokens block ([system](system.md)):

```json
"motion": {
  "overshoot": "never",
  "scale": "never",
  "pointer_following": "never",
  "zoom_transition": "never",
  "except": {"scale": ["dock"]},
  "decided_by": "user",
  "date": "2026-10-30",
  "reason": "the product's motion policy, as the user set it"
}
```

Another project may allow all four. Each word is `never` or `allowed`; `except` names the selectors or components a `never` does not cover; who decided, when and why are required.

`designcheck.py rules SRC --brief B --record RECORD` checks source against it:

| Word | Rule | Finds |
| --- | --- | --- |
| overshoot | `policy-overshoot` | a cubic-bezier with a control point above 1 or below 0, a spring with bounce, back and elastic curves |
| scale | `policy-scale` | scale transforms and scale utility classes, except where the record's exceptions name the selector |
| pointer_following | `policy-pointer-following` | a pointer or mouse move handler that sets a position or transform |
| zoom_transition | none static | judged in review, from a recording |

Without `--record`, the policy rules are listed under `policy_not_run`, never passed. A policy of this kind should flag the usual demo effects: liquid and jelly surfaces, cursor and dye trails, springy defaults and camera moves used as transitions.

## Craft prompts (taste, not gates)

From emilkowalski/skills (MIT, read at its pin; ideas only, no thresholds carried):

- How often an action happens decides whether it animates. Something triggered from the keyboard many times a day should not.
- Transitions can be retargeted mid-flight while keyframe animations restart, so rapidly repeated triggers suit transitions.
- A popover grows from its trigger, not its centre; a modal stays centred.
- Touch screens fire a hover on tap, so hover motion belongs to fine pointers.

Questions for review: durations and curves are the project's choice, recorded with their basis.

## References (DG-34)

Before borrowing from a moving reference, settle what it is from runtime evidence, never its look: a live simulation (state stepped each frame, answering input), a shader-only effect (shader and uniforms driven by time), fixed keyframes (the animation list), scroll-scrubbed playback (scroll-linked rules or timelines) or pre-rendered video (a playing `video` element). Only a live simulation has physics numbers worth taking. Without a browser this is not-run and the reference's motion stays claimed.

## Evidence

Motion is judged from recordings, never stills (DG-26, [browser](browser.md)), and each evidence item names its capture class (DG-33). An easing curve stands as observed only on `exact` evidence and as present on `recovered` source; read off samples it stays claimed, since samples miss what lies between. Only a seekable renderer makes a frame `exact` (DG-43, [rendering](rendering.md)). `report` drops a `motion` finding without a recording and lowers one above its classes (`lowered`).

## Exporting a loop

An approved design filmed as a seamless MP4 (and GIF) loop, its seam checked frame against frame: [motion export](motion-export.md).
