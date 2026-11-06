# Exporting an approved design as a loop

For a design the user has approved, when they want it as a video loop: a pitch, a README, a launch post. The loop must play forever without a visible jump, so its last frame has to equal its first. Only an approved design is exported; a draft is critiqued, not filmed.

## Record

1. **Serve it** locally under the usual grant (core `browser.md`), at the viewport the user will show it at.
2. **Check the cycle.** `document.getAnimations()` lists each animation's duration; the loop period is their common multiple. A cycle whose 100% keyframe differs from its 0% keyframe jumps on repeat: say so before filming, and suggest the fix (end where it starts).
3. **Film it** with the host's screencast tool (Chrome DevTools MCP `screencast_start` and `screencast_stop` write an MP4) for at least two cycles. No screencast tool: `not-run`, never a stitched slideshow called a video.
4. **Take the seam frames.** Pause every animation and set its time to 0, screenshot `first.png`; set it to one period less one millisecond, screenshot `last.png` (`frames.method: seek`). Frames decoded from the video instead are `decoded`.
5. **A GIF only when the host or the user's own tools make one.** It must carry the repeat (NETSCAPE2.0) block; westack installs no encoder.

## Check

Write `motion.json` beside the files:

```json
{"format": "westack-design-motion-1",
 "design": {"page": "...", "approved": {"by": "...", "said": "their words"}},
 "loop": {"period_s": 2, "loops": 2},
 "video": {"file": "loop.mp4", "sha256": "..."}, "gif": {"file": "loop.gif"},
 "frames": {"first": "first.png", "last": "last.png", "method": "seek"},
 "reduced_motion": "what a viewer who prefers reduced motion gets"}
```

`python scripts/designcheck.py motion-export <folder>` reads the MP4's boxes (plain or fragmented, as screencasts are) for its duration, frame count and rate; checks the hash, the approval, that the recording covers the loops, the GIF's repeat flag, and that the first and last frames differ in no more than 0.5% of pixels. A `loop-seam` finding means the loop jumps: fix the keyframes, not the threshold.

Provenance: gstack's design-motion at the mirror pin (absorption.json `gstack.design-motion`), in westack's words.
