"""westack-design checks over saved files: tokens, contrast, rules, waivers, inventory, record and report.

  python designcheck.py tokens SRC... --theme THEME [--token-file FILE]... [--baseline OLD_THEME]
  python designcheck.py tokens SRC... --writing NEW_TOKEN_FILE [--replace-authorised TURN]
  python designcheck.py contrast RECORD
  python designcheck.py rules SRC... --brief BRIEF [--waivers FILE] [--record RECORD] [--control HUMAN_PAGE]...
  python designcheck.py waivers FILE
  python designcheck.py inventory BEFORE.html AFTER.html [--dropped FILE] [--depth full|restyle|polish]
  python designcheck.py record RECORD [--derived FILE]... [--built PATH]... [--baseline OLD_RECORD] [--emit css|json]
  python designcheck.py report FILE

Every command also takes --rules FILE and --thresholds FILE (default: references/rules.json and
references/thresholds.json beside this script's folder). SRC is files or folders; folders are walked, skipping
node_modules, .git, dist and build output.

tokens (DG-11, DG-12, DG-13): raw colour and px or rem literals in declaration values, Tailwind arbitrary values and
SVG colour attributes, even on a line that also uses var(); each finding names the theme token to use (exact, or the
nearest) and, for an arbitrary spacing value, the on-scale class (p-[13px] is p-3.25 on a 4px step). Black, white,
zero and hairlines pass; files named with --token-file (and the theme) are not scanned. --baseline lists tokens the
theme gained as proposals. --writing is the preflight before writing a token file: any existing token source (a
:root or @theme block, a *token*.json, DESIGN.md, or a Tailwind config, which is named and never loaded) stops it
unless --replace-authorised names the user's turn.
contrast (DG-14): WCAG 2 relative luminance over the record's colours. Pairs: X with on-X or X-foreground, foreground
on background, ring on background, and each component's textColor and iconColor on its backgroundColor; a variant
(button-primary-hover) inherits what it does not set from its base (button-primary). Alpha is composited over an
opaque background or the pair is unresolved. Text needs 4.5:1; large text, icons and rings 3:1; muted text may not
be stronger than primary text. Ratios are floored to two places, never rounded up.
rules (DG-6, DG-8, DG-10, DG-17, DG-22, DG-25, DG-28, DG-29): the rules file over source. A tell the brief asks for
is listed, not flagged; floor and reflex findings block, finish findings are answered; --waivers lifts a reflex
finding only through a waiver that passes the waivers check. Policy rules (overshoot, scale, pointer-following) run
only against the motion policy in --record and skip its recorded exceptions; without one they are listed not-run.
--control runs the same rules over a human-made page: a reflex rule that fires there is held for review instead of
gating. Pairing checks (colour pairs, card chrome) never combine two @media blocks or hover rules with each other.
The rules and thresholds files are refused (not-run) when a rule disagrees with its own examples or a threshold
lacks its source, basis, date or a fixture on each side.
waivers (DG-8): a floor rule is never waived; a reason must not be boilerplate, must name the page and must not be
copied; the evidence (a file and its exact text) must be on the page and show the waived pattern.
inventory (DG-16): links, forms, fields, handlers, test hooks and scripts before and after a redesign; a missing one
fails unless --dropped records it with a reason and evidence; restyle and polish may not move sections.
record (DG-12, DG-20, DG-21, DG-35, DG-40): the design record's ```json tokens blocks (or its .tokens.json sidecar)
and its ## sections: keys defined once, misspelt groups, token-like data under unused keys, absent sections without a
declared reason, token references, derived files regenerated and compared, values that never shipped or shipped once
(--built), tokens and variants new since --baseline as proposals, a direction's one to three design references, each
with every field of its record, invariants that name their widths and how they are observed, and sign-offs that name
who accepted which captures and when. --emit prints a derived file.
report (DG-1 to DG-5, DG-7, DG-23, DG-24, DG-26, DG-27, DG-29, DG-31, DG-33, DG-36, DG-38, DG-41, DG-45, DG-46): a critique report's findings
need a rule, a path and a correction, and evidence; hierarchy, prominence, density and usability from source stay
claimed; numbers come from measurement or source, never a screenshot read by a model; motion needs a recording, each
motion evidence item names its capture class, and a finding above what its classes show is lowered (an easing curve
read off samples stays claimed); a finding the rendered check contradicts is dropped; a degraded run opens with
DEGRADED; judgment is written before detector output; an invalid capture means recapture; scores are 0-3 with n/a
rows outside the denominator; a changed screenshot baseline is listed as a proposal and must come from the same
environment; DG-23, DG-24 and DG-26 (and DG-34, DG-36, DG-38, DG-39, DG-41, DG-43, DG-44 and DG-46 when reported) are
not-run without a browser; a comparison of build and reference counts only when both runs finished every step, and an early stop is
blocked at its step; an effects-off check names the effects it removed; a capture whose readiness wait timed out or
that logged console errors is never valid, and a reported DG-41 status follows its captures; when the report names
the delivered file, a capture marked final names its sha256 (DG-45); declared text beats hold at least text-hold-s
(DG-46, read from the thresholds only when beats are declared).

Exit 0 clean, 1 findings (or proposals waiting for the user), 2 unreadable or a check not run, 64 usage. Standard
library only. It reads the files named and prints JSON; it never loads or runs the project's code (a Tailwind
config, PostCSS or any plugin), runs no command, writes no file and opens no network connection. DG-23, DG-24, DG-26,
DG-34, DG-36, DG-38, DG-39 (settle time), DG-41, DG-43, DG-44 and DG-46 (the recorded hold) need a browser or a
recorder, so every report lists them as not run by this script.
"""
import argparse
import collections
import hashlib
import html.parser
import json
import math
import os
import pathlib
import re
import struct
import sys
import zlib

FORMAT = "westack-design-check-1"
HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_RULES = HERE.parent / "references" / "rules.json"
DEFAULT_THRESHOLDS = HERE.parent / "references" / "thresholds.json"
LIMIT = 4 * 1024 * 1024
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "out", "vendor", "coverage", "__pycache__", ".venv", "venv"}
SOURCE_EXT = {".css", ".scss", ".sass", ".less", ".html", ".htm", ".jsx", ".tsx", ".js", ".ts", ".mjs", ".cjs",
              ".vue", ".svelte", ".astro", ".mdx"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
MARKUP_STYLE_EXT = STYLE_EXT | {".html", ".htm", ".vue", ".svelte", ".astro"}
BASES = ("measured", "taste", "brand")
TIERS = ("floor", "reflex", "finish")
RULE_KINDS = ("regex", "colour-pair", "card-chrome", "gradient-hue", "font-size-min")
TELL_STATUS = ("flagged", "warned", "retired")
POLICY_WORDS = ("overshoot", "scale", "pointer_following", "zoom_transition")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
EXIT = {"clean": 0, "findings": 1, "proposals": 1, "unreadable": 2, "not-run": 2}
WHY_NO_BROWSER = "needs the host's browser tools under a grant; this script runs no browser"
RUNTIME_NOT_RUN = (
    {"id": "DG-23", "check": "page predicates at six widths: overflow, image size and alt, tap targets, h1 count, "
                             "lang, viewport meta, focus rings", "status": "not-run", "why": WHY_NO_BROWSER},
    {"id": "DG-24", "check": "render-tier checks: contrast against rendered pixels, focus found by Tab, text lost "
                             "between 1440 and 375, captures with a failed font", "status": "not-run", "why": WHY_NO_BROWSER},
    {"id": "DG-26", "check": "recorded motion under real input: step response, hover boxes before and after at the "
                             "device pixel ratio (DG-25 a), the reduced-motion end state and pause controls (DG-25 b)",
     "status": "not-run", "why": "needs the host's browser or a recorder under a grant; this script runs neither"},
    {"id": "DG-34", "check": "a moving reference classed from runtime evidence (live simulation, shader-only effect, "
                             "fixed keyframes, scroll-scrubbed playback or pre-rendered video) before borrowing from it",
     "status": "not-run", "why": WHY_NO_BROWSER},
    {"id": "DG-36", "check": "build and reference put through the same scripted steps in fresh browsers at one "
                             "viewport and compared after each step", "status": "not-run",
     "why": "needs the host's browser tools under a grant naming both targets; this script runs no browser"},
    {"id": "DG-38", "check": "the page still reads with effects off: shadows, filters, blur, animation and transitions "
                             "removed by an injected stylesheet, then contrast and region separation measured again",
     "status": "not-run", "why": WHY_NO_BROWSER},
    {"id": "DG-39", "check": "the settle time of smoothed motion, measured at two emulated frame rates, differs by no "
                             "more than 10% (the static half is rule motion-per-frame-lerp)", "status": "not-run",
     "why": "needs the host's browser or a recorder under a grant; this script runs neither"},
    {"id": "DG-41", "check": "each capture waits for the page's ready flag (else fonts loaded and network idle) and "
                             "fails on console errors; a wait that times out blocks the capture", "status": "not-run",
     "why": WHY_NO_BROWSER},
    {"id": "DG-43", "check": "a recorded animation's frames are a function of time alone: frames requested out of order "
                             "(t=2, t=5, then t=2) have the same pixel hashes as in order", "status": "not-run",
     "why": "needs the host's browser or a recorder under a grant; this script runs neither"},
    {"id": "DG-44", "check": "every readout moves when the input it depends on is changed through the page's own "
                             "control, and one value is checked by hand", "status": "not-run", "why": WHY_NO_BROWSER},
    {"id": "DG-46", "check": "each line of text in a recording is on screen at least text-hold-s (the report's declared "
                             "text_beats are checked statically)", "status": "not-run",
     "why": "needs the host's browser or a recorder under a grant; this script runs neither"},
)
RUNTIME_IDS = tuple(item["id"] for item in RUNTIME_NOT_RUN)
REQUIRED_RUNTIME = ("DG-23", "DG-24", "DG-26")  # every report says what happened to these; the rest when run
CLAIMS = {
    "tokens": "reads source text only; a clean scan is not design approval, and a value it cannot read (a class built "
              "at run time, an imported constant, a Tailwind config, which it never runs) is not checked",
    "contrast": "computes WCAG 2 ratios from the record's declared colours; it does not see rendered pixels, gradients "
                "or images behind text (DG-24)",
    "rules": "pattern checks over source; passing them is not design approval, a thin or generic page can pass every "
             "one, and a tell the brief asked for is listed, not flagged",
    "waivers": "checks a waiver's tier, reason and evidence; it does not judge whether the reason is true",
    "inventory": "compares the wiring parsed from two saved HTML files; markup a script adds at run time is not seen",
    "record": "checks the record's structure, its derived files and its values against built CSS; it does not judge "
              "the design",
    "report": "checks a critique report's structure and evidence links, not whether its judgments are right",
    "motion-export": "checks a motion-export folder: the record, the approval, the MP4's duration and frame count "
                     "read from its boxes, an optional GIF's loop flag, and that the loop's first and last frames match "
                     "pixel for pixel within the threshold; it does not judge the motion itself",
    "variants": "checks a variants board's files, screenshot hashes and recorded choice; it does not judge which "
                "variant is better, and it renders nothing",
}


class Unreadable(ValueError):
    """An input cannot be read as what the command expects; nothing was checked."""


class NotRun(ValueError):
    """A check could not run: its rules or thresholds were refused, or there was nothing to check."""


# ---- reports -------------------------------------------------------------------------------------------------------

def report(command, status, findings=(), **extra):
    out = {"format": FORMAT, "command": command, "status": status, "findings": list(findings)}
    out.update(extra)
    out["not_run"] = [dict(item) for item in RUNTIME_NOT_RUN]
    out["claim"] = CLAIMS[command]
    return out


def finding(check, code, where, message, **extra):
    item = {"check": check, "code": code, "where": where, "message": message}
    item.update({key: value for key, value in extra.items() if value is not None})
    return item


def overall_status(findings, proposals=()):
    return "findings" if findings else "proposals" if proposals else "clean"


# ---- reading -------------------------------------------------------------------------------------------------------

def read_text(path):
    path = pathlib.Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise Unreadable("%s cannot be read: %s" % (path, exc))
    if len(data) > LIMIT:
        raise Unreadable("%s is larger than %d bytes" % (path, LIMIT))
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    return data.decode("utf-8-sig", errors="replace")


def text_value(value):
    return isinstance(value, str) and bool(value.strip())


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def blank_comments(text):
    """The text with /* */ and <!-- --> comments blanked (line breaks kept), so positions still map to lines."""
    return re.sub(r"/\*.*?\*/|<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def walk(paths, accept=None):
    accept = accept or (lambda p: p.suffix.lower() in SOURCE_EXT)
    files, missing = [], []
    for raw in paths:
        path = pathlib.Path(raw)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for directory, folders, names in os.walk(path):
                folders[:] = sorted(f for f in folders if f not in SKIP_DIRS)
                files.extend(pathlib.Path(directory) / n for n in sorted(names) if accept(pathlib.Path(directory) / n))
        else:
            missing.append(str(raw))
    return files, missing


def same_file(a, b):
    try:
        return pathlib.Path(a).resolve() == pathlib.Path(b).resolve()
    except OSError:
        return False


def load_json(text, where):
    dupes = []

    def hook(pairs):
        out, pairs_seen = {}, set()
        for key, value in pairs:
            if key in pairs_seen:
                dupes.append(key)
            pairs_seen.add(key)
            out[key] = value
        return out
    try:
        return json.loads(text, object_pairs_hook=hook), dupes
    except ValueError as exc:
        raise Unreadable("%s is not JSON: %s" % (where, exc))


# ---- colours and lengths -------------------------------------------------------------------------------------------

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![\w-])")
FUNC_RE = re.compile(r"\b(?:rgba?|hsla?)\([^()]*\)", re.I)
DECL_RE = re.compile(r"(?<![\w(\[-])(?P<prop>-{0,2}[A-Za-z][\w-]*)\s*:\s*(?P<value>[^;{}\n]+)")
LENGTH_RE = re.compile(r"(?<![\w.#-])(-?\d*\.?\d+)(px|rem)(?![\w-])")
ARBITRARY_RE = re.compile(r"(?<![\w\[-])(?P<util>-?[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*)-\[(?P<value>[^\]\s]+)\]")
ATTR_COLOUR_RE = re.compile(r"\b(?:fill|stroke|color|bgcolor|stop-color)\s*=\s*[\"'](?P<value>[^\"']+)[\"']", re.I)
REF_RE = re.compile(r"^\{([A-Za-z0-9_.-]+)\}$")
LENGTH_PREFIXES = ("margin", "padding", "gap", "row-gap", "column-gap", "width", "height", "min-width", "max-width",
                   "min-height", "max-height", "top", "right", "bottom", "left", "inset", "font-size", "flex-basis",
                   "line-height", "letter-spacing")
SPACING_UTILS = {"p", "px", "py", "pt", "pr", "pb", "pl", "ps", "pe", "m", "mx", "my", "mt", "mr", "mb", "ml", "ms",
                 "me", "gap", "gap-x", "gap-y", "space-x", "space-y", "w", "h", "size", "min-w", "min-h", "max-w",
                 "max-h", "inset", "inset-x", "inset-y", "top", "right", "bottom", "left", "translate-x",
                 "translate-y", "scroll-m", "scroll-p", "indent", "basis"}
NAMED = {"white": (255.0, 255.0, 255.0, 1.0), "black": (0.0, 0.0, 0.0, 1.0)}


def hsl_to_rgb(h, s, l):
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return tuple((v + m) * 255 for v in (r, g, b))


def parse_colour(value):
    """(r, g, b, a) with channels 0-255 and alpha 0-1, or None."""
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text in NAMED:
        return NAMED[text]
    hexes = re.fullmatch(r"#([0-9a-f]{3,8})", text)
    if hexes:
        digits = hexes.group(1)
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        if len(digits) not in (6, 8):
            return None
        alpha = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
        return (float(int(digits[0:2], 16)), float(int(digits[2:4], 16)), float(int(digits[4:6], 16)), alpha)
    func = re.fullmatch(r"(rgba?|hsla?)\(\s*(.*?)\s*\)", text)
    if not func:
        return None
    parts = [p for p in re.split(r"[\s,/]+", func.group(2)) if p]
    if len(parts) not in (3, 4):
        return None
    try:
        alpha = 1.0
        if len(parts) == 4:
            alpha = float(parts[3][:-1]) / 100 if parts[3].endswith("%") else float(parts[3])
        if func.group(1).startswith("rgb"):
            r, g, b = (min(255.0, max(0.0, float(p[:-1]) * 2.55 if p.endswith("%") else float(p))) for p in parts[:3])
        else:
            hue = float(parts[0].replace("deg", "")) % 360
            r, g, b = hsl_to_rgb(hue, float(parts[1].rstrip("%")) / 100, float(parts[2].rstrip("%")) / 100)
    except ValueError:
        return None
    return (r, g, b, min(1.0, max(0.0, alpha)))


def hex_of(rgba):
    out = "#%02x%02x%02x" % tuple(int(round(c)) for c in rgba[:3])
    return out if rgba[3] >= 1 else out + "%02x" % int(round(rgba[3] * 255))


def rgb_to_hsl(rgba):
    r, g, b = (c / 255 for c in rgba[:3])
    hi, lo = max(r, g, b), min(r, g, b)
    light = (hi + lo) / 2
    spread = hi - lo
    if spread == 0:
        return 0.0, 0.0, light
    sat = spread / (1 - abs(2 * light - 1))
    if hi == r:
        hue = 60 * (((g - b) / spread) % 6)
    elif hi == g:
        hue = 60 * ((b - r) / spread + 2)
    else:
        hue = 60 * ((r - g) / spread + 4)
    return hue, sat, light


def luminance(rgba):
    """WCAG 2 relative luminance of an sRGB colour."""
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgba[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def composite(top, bottom):
    alpha = top[3]
    return tuple(top[i] * alpha + bottom[i] * (1 - alpha) for i in range(3)) + (1.0,)


def floor2(value):
    return math.floor(value * 100) / 100


def to_px(match, root_px):
    value = float(match.group(1))
    return value * root_px if match.group(2) == "rem" else value


def fmt(value):
    return ("%.4f" % value).rstrip("0").rstrip(".")


def kebab(prop):
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", prop).lower()


def literal_colours(value):
    """(offset, literal, rgba) for each colour literal in a declaration value."""
    out = []
    for m in HEX_RE.finditer(value):
        before = value[:m.start()]
        if before.endswith(("/", "&", "=", "?")) or before.rstrip().endswith("url("):
            continue
        rgba = parse_colour(m.group(0))
        if rgba:
            out.append((m.start(), m.group(0), rgba))
    for m in FUNC_RE.finditer(value):
        rgba = parse_colour(m.group(0))
        if rgba:
            out.append((m.start(), m.group(0), rgba))
    return out


def colour_hits(text):
    """(index, literal, rgba, context, property) for colour literals in declarations, arbitrary values and colour attributes."""
    hits = {}
    for m in DECL_RE.finditer(text):
        for hit in literal_colours(m.group("value")):
            hits.setdefault(m.start("value") + hit[0], (m.start("value") + hit[0], hit[1], hit[2], "declaration",
                                                        kebab(m.group("prop"))))
    for m in ARBITRARY_RE.finditer(text):
        rgba = parse_colour(m.group("value").replace("_", " "))
        if rgba:
            hits.setdefault(m.start("value"), (m.start("value"), m.group("value"), rgba, "arbitrary", m.group("util")))
    for m in ATTR_COLOUR_RE.finditer(text):
        rgba = parse_colour(m.group("value"))
        if rgba:
            hits.setdefault(m.start("value"), (m.start("value"), m.group("value"), rgba, "attribute", None))
    return [hits[k] for k in sorted(hits)]


def length_hits(text, root_px):
    """(index, literal, px, context, property or utility) for px and rem literals in length declarations and arbitrary values."""
    out = []
    for m in DECL_RE.finditer(text):
        prop = kebab(m.group("prop"))
        if not (prop.startswith("--") or prop.startswith(LENGTH_PREFIXES) or "radius" in prop):
            continue
        value = m.group("value")
        for lm in LENGTH_RE.finditer(value):
            out.append((m.start("value") + lm.start(), lm.group(0), to_px(lm, root_px), "declaration", prop))
    for m in ARBITRARY_RE.finditer(text):
        lm = LENGTH_RE.fullmatch(m.group("value"))
        if lm:
            out.append((m.start("value"), lm.group(0), to_px(lm, root_px), "arbitrary", m.group("util")))
    return sorted(out)


# ---- thresholds ----------------------------------------------------------------------------------------------------

def passes_cut(value, item):
    """True when value is on the passing side of a cut (op min: at least the value; op max: at most)."""
    return value >= item["value"] if item["op"] == "min" else value <= item["value"]


def hold_shape_ok(item):
    """A per-word hold: base and per_word are seconds (non-negative numbers), free_words a whole number of words."""
    free = item.get("free_words")
    return (all(number(item.get(k)) and item[k] >= 0 for k in ("base", "per_word"))
            and isinstance(free, int) and not isinstance(free, bool) and free >= 0)


def hold_needed(words, item):
    """DG-46: the shortest hold for a line of text: base, plus per_word for each word beyond free_words."""
    return item["base"] + item["per_word"] * max(0, words - item["free_words"])


def holds(words, held, item):
    return held + 1e-9 >= hold_needed(words, item)


def in_band(rgba, band):
    hue, sat, light = rgb_to_hsl(rgba)
    for key, value in (("hue", hue), ("saturation", sat), ("lightness", light)):
        bounds = band.get(key)
        if bounds and not bounds[0] <= value <= bounds[1]:
            return False
    return True


def threshold_problems(data):
    """Every way a thresholds file breaks the data rule (DG-9); empty when it can be used."""
    if not isinstance(data, dict) or data.get("format") != "westack-design-thresholds-1":
        return ["not a westack-design-thresholds-1 file"]
    items = data.get("thresholds")
    if not isinstance(items, dict) or not items:
        return ["no thresholds"]
    problems = []
    for name, item in items.items():
        if not isinstance(item, dict):
            problems.append(name + ": not an object")
            continue
        for key in ("kind", "source", "set_by", "date", "basis"):
            if not text_value(item.get(key)):
                problems.append("%s: no %s (each number carries its source, what set it, a date and a basis)" % (name, key))
        if text_value(item.get("basis")) and item["basis"] not in BASES:
            problems.append("%s: basis is one of %s" % (name, ", ".join(BASES)))
        if text_value(item.get("date")) and not ISO_DATE.fullmatch(item["date"]):
            problems.append(name + ": date is YYYY-MM-DD")
        kind, fixtures = item.get("kind"), item.get("fixtures")
        if kind == "cut":
            if not number(item.get("value")) or item.get("op") not in ("min", "max"):
                problems.append(name + ": a cut needs a number and op min or max")
            elif not (isinstance(fixtures, dict) and number(fixtures.get("fails")) and number(fixtures.get("passes"))):
                problems.append(name + ": a cut needs a fixture on each side (fails, passes)")
            elif passes_cut(fixtures["fails"], item) or not passes_cut(fixtures["passes"], item):
                problems.append(name + ": its fixtures sit on the wrong side of the cut")
        elif kind == "band":
            bounds_ok = all(isinstance(item.get(k), list) and len(item[k]) == 2 and all(number(v) for v in item[k])
                            for k in ("hue", "saturation", "lightness") if k in item) and "hue" in item
            inside = parse_colour(fixtures.get("inside")) if isinstance(fixtures, dict) else None
            outside = parse_colour(fixtures.get("outside")) if isinstance(fixtures, dict) else None
            if not bounds_ok:
                problems.append(name + ": a band needs [low, high] hue (and optional saturation and lightness)")
            elif inside is None or outside is None:
                problems.append(name + ": a band needs a colour inside and one outside")
            elif not in_band(inside, item) or in_band(outside, item):
                problems.append(name + ": its fixtures sit on the wrong side of the band")
        elif kind == "per-word":
            sides = ("fails", "passes")
            if not hold_shape_ok(item):
                problems.append(name + ": a per-word hold needs base and per_word in seconds and free_words a whole number")
            elif not (isinstance(fixtures, dict) and all(isinstance(fixtures.get(s), dict) and number(fixtures[s].get("words"))
                                                         and number(fixtures[s].get("held")) for s in sides)):
                problems.append(name + ": a per-word hold needs a fixture on each side (fails, passes: words and held)")
            else:
                fails, passes = fixtures["fails"], fixtures["passes"]
                if holds(fails["words"], fails["held"], item) or not holds(passes["words"], passes["held"], item):
                    problems.append(name + ": its fixtures sit on the wrong side of the hold")
        elif kind == "value":
            if not number(item.get("value")):
                problems.append(name + ": a value needs a number")
        elif kind == "set":
            if not (isinstance(item.get("value"), list) and item["value"] and all(number(v) for v in item["value"])):
                problems.append(name + ": a set needs a list of numbers")
        elif text_value(kind):
            problems.append(name + ": unknown kind " + kind)
    return problems


def load_thresholds(path):
    try:
        data, _ = load_json(read_text(path), str(path))
    except Unreadable as exc:
        raise NotRun("thresholds refused: %s" % exc)
    problems = threshold_problems(data)
    if problems:
        raise NotRun("thresholds refused: " + "; ".join(problems[:12]))
    return data["thresholds"]


def need(thresholds, name, kind=None):
    item = thresholds.get(name)
    if not isinstance(item, dict) or (kind and item.get("kind") != kind):
        raise NotRun("thresholds refused: %s is missing or not a %s" % (name, kind or "threshold"))
    return item


# ---- tokens and references -----------------------------------------------------------------------------------------

MISSING = object()


def lookup(tokens, dotted):
    node = tokens
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return MISSING
    return node


def resolve(tokens, value, depth_max, depth=0, seen=()):
    """(value, None) with every {group.name} reference followed, or (None, error code)."""
    ref = REF_RE.match(value.strip()) if isinstance(value, str) else None
    if not ref:
        return value, None
    path = ref.group(1)
    if path in seen:
        return None, "ref-cycle"
    if depth >= depth_max:
        return None, "ref-too-deep"
    target = lookup(tokens, path)
    if target is MISSING:
        return None, "unresolved-ref"
    return resolve(tokens, target, depth_max, depth + 1, seen + (path,))


def leaves(node, prefix=""):
    if isinstance(node, dict):
        for key in node:
            yield from leaves(node[key], prefix + ("." if prefix else "") + str(key))
    else:
        yield prefix, node


FENCE_RE = re.compile(r"^```json tokens[ \t]*\r?\n(.*?)^```[ \t]*\r?$", re.M | re.S)
ANY_FENCE_RE = re.compile(r"^```.*?^```[ \t]*\r?$", re.M | re.S)
HEADING_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*\r?$", re.M)


def load_tokens(path, problems=None):
    """(tokens, text): a record's ```json tokens blocks merged (or its <stem>.tokens.json sidecar), or a JSON file.
    Keys defined twice are appended to problems as (code, where, message)."""
    path = pathlib.Path(path)
    text = read_text(path)
    problems = [] if problems is None else problems

    def parse(body, where):
        data, dupes = load_json(body, where)
        if not isinstance(data, dict):
            raise Unreadable("%s: the tokens are not a JSON object" % where)
        problems.extend(("duplicate-key", where, "key %r is defined twice in one block" % key) for key in dupes)
        return data
    if path.suffix.lower() == ".json":
        return parse(text, str(path)), text
    blocks = list(FENCE_RE.finditer(text))
    if not blocks:
        sidecar = path.with_name(path.stem + ".tokens.json")
        if sidecar.is_file():
            return parse(read_text(sidecar), str(sidecar)), text
        raise Unreadable("%s has no ```json tokens block and no %s sidecar" % (path, sidecar.name))
    tokens = {}
    for block in blocks:
        where = "%s:%d" % (path, line_of(text, block.start()))
        for key, value in parse(block.group(1), where).items():
            if key in tokens:
                problems.append(("duplicate-key", where, "top-level key %r is defined in two blocks; the first is kept" % key))
                continue
            tokens[key] = value
    return tokens, text


def theme_index(tokens, thresholds):
    depth = need(thresholds, "ref-depth-max", "cut")["value"]
    root = need(thresholds, "root-font-px", "value")["value"]
    colours, lengths = {}, {}
    for path, value in leaves(tokens):
        if path.split(".")[0] in ("components", "omitted", "derived", "format", "motion"):
            continue
        resolved, error = resolve(tokens, value, depth)
        if error or not isinstance(resolved, str):
            continue
        rgba = parse_colour(resolved)
        if rgba:
            colours[path] = rgba
            continue
        lm = LENGTH_RE.fullmatch(resolved.strip())
        if lm:
            lengths[path] = to_px(lm, root)
    return colours, lengths


def nearest_colour(rgba, colours):
    if not colours:
        return None, False
    exact = sorted(p for p, c in colours.items() if hex_of(c) == hex_of(rgba))
    if exact:
        return exact[0], True
    return min(colours, key=lambda p: (sum((colours[p][i] - rgba[i]) ** 2 for i in range(3)), p)), False


def nearest_length(px, lengths, prefer):
    if not lengths:
        return None, False
    ranked = sorted(lengths, key=lambda p: (abs(lengths[p] - px), not p.startswith(prefer), p))
    return ranked[0], lengths[ranked[0]] == px


def token_name(path):
    return path.split(".", 1)[1].replace(".", "-") if "." in path else path


# ---- suppressions (DG-13) ------------------------------------------------------------------------------------------

SUPPRESS_RE = re.compile(r"designcheck:\s*(?P<kind>ignore-file|ignore-rule|ignore)\b(?P<body>[^\n]*?)\s*(?:\*/|-->|$)", re.M)


def parse_suppressions(text, path):
    found, problems = [], []
    for m in SUPPRESS_RE.finditer(text):
        kind = m.group("kind")
        parts = re.split(r"\bbecause\b", m.group("body"), maxsplit=1)
        head, because = parts[0], (parts[1].strip(" :-") if len(parts) > 1 else "")
        fields = dict(token.split("=", 1) for token in head.split() if "=" in token)
        words = [token for token in head.split() if "=" not in token]
        where = "%s:%d" % (path, line_of(text, m.start()))
        item = {"kind": kind, "code": words[0] if words else None, "value": fields.get("value"), "by": fields.get("by"),
                "turn": fields.get("turn"), "because": because, "where": where}
        if kind != "ignore" and not (fields.get("by") == "user" and fields.get("turn")):
            problems.append(finding("suppression", "suppression-needs-user", where,
                                    "a rule-wide or file-wide ignore needs the user's decision: by=user turn=<their turn> "
                                    "because <evidence>; it silences nothing until then"))
            continue
        if not because or (kind != "ignore-file" and not item["code"]) or (kind == "ignore" and not (item["value"] and item["by"])):
            problems.append(finding("suppression", "suppression-incomplete", where,
                                    "an ignore names the rule, the value, who decided and the evidence (because ...)"))
            continue
        found.append(item)
    return found, problems


def squash(value):
    return re.sub(r"\s+", "", str(value or "")).lower()


def apply_suppressions(items, suppressions):
    kept, counts = [], collections.Counter()
    for item in items:
        key = item.get("rule") or item["code"]
        hit = None
        for number_, s in enumerate(suppressions):
            if s["kind"] == "ignore-file" or (s["code"] == key and (
                    s["kind"] == "ignore-rule" or squash(s["value"]) in squash(item.get("value")))):
                hit = number_
                break
        if hit is None:
            kept.append(item)
        else:
            counts[hit] += 1
    return kept, [dict(s, applied_to=counts[n]) for n, s in enumerate(suppressions)]


# ---- tokens --------------------------------------------------------------------------------------------------------

TOKEN_SOURCE_RE = re.compile(r":root\b[^{]*\{[^}]*--[\w-]+\s*:|@theme\b[^{]*\{")


def token_source_kind(path):
    name = path.name.lower()
    if re.fullmatch(r"tailwind\.config\.(?:js|cjs|mjs|ts)", name):
        return "tailwind-config (named only: never loaded or run; read it yourself)"
    if path.suffix.lower() == ".json" and "token" in name:
        return "token-json"
    if name == "design.md":
        return "design-record"
    if path.suffix.lower() in MARKUP_STYLE_EXT:
        css_variables = TOKEN_SOURCE_RE.search(blank_comments(read_text(path)))
        if css_variables:
            return "css-variables (:root or @theme)"
    return None


def preflight(args):
    target = pathlib.Path(args.writing)
    files, missing = walk(args.src, lambda p: p.suffix.lower() in SOURCE_EXT | {".json"} or p.name.lower() == "design.md")
    sources = []
    for path in files:
        if same_file(path, target):
            continue
        kind = token_source_kind(path)
        if kind:
            sources.append({"file": str(path), "kind": kind})
    findings = [finding("tokens", "missing-source", m, "no such file or folder") for m in missing]
    if sources and not args.replace_authorised:
        findings += [finding("tokens", "token-source-exists", s["file"],
                             "stop: this already declares tokens (%s); extend it, or get the user's authorisation to "
                             "replace it (--replace-authorised TURN)" % s["kind"]) for s in sources]
    return report("tokens", overall_status(findings), findings, writing=str(target), sources=sources,
                  authorised=args.replace_authorised)


def cmd_tokens(args):
    if args.writing:
        return preflight(args)
    thresholds = load_thresholds(args.thresholds)
    hairline = need(thresholds, "hairline-px", "cut")
    root = need(thresholds, "root-font-px", "value")["value"]
    theme_path = pathlib.Path(args.theme)
    tokens, _ = load_tokens(theme_path)
    colours, lengths = theme_index(tokens, thresholds)
    base_text = (tokens.get("spacing") or {}).get("base") if isinstance(tokens.get("spacing"), dict) else None
    base_match = LENGTH_RE.fullmatch(base_text.strip()) if isinstance(base_text, str) else None
    base = to_px(base_match, root) if base_match else need(thresholds, "spacing-base-px", "value")["value"]
    exempt = [theme_path] + [pathlib.Path(p) for p in args.token_file]
    files, missing = walk(args.src)
    files = [f for f in files if not any(same_file(f, e) for e in exempt)]
    findings = [finding("tokens", "missing-source", m, "no such file or folder") for m in missing]
    if not files:
        raise NotRun("no source files to scan (token files and the theme are exempt): nothing to check is not clean")
    suppressions = []
    for path in files:
        text = read_text(path)
        scan = blank_comments(text)
        found = []
        for index, literal, rgba, context, prop in colour_hits(scan):
            if hex_of(rgba) in ("#000000", "#ffffff"):
                continue
            name, exact_colour = nearest_colour(rgba, colours)
            use = name
            if context == "arbitrary" and name:
                use = "%s-%s" % (prop, token_name(name))
            reported_exact = False
            if exact_colour:
                reported_exact = True
                message = "%s is the theme's %s: use the token (%s)" % (literal, name, theme_path.name)
            else:
                message = ("%s is not a colour in %s; nearest is %s (%s). A new token is a proposal for the user"
                           % (literal, theme_path.name, name, hex_of(colours[name])) if name else
                           "%s is a raw colour and %s declares none" % (literal, theme_path.name))
            found.append(finding("tokens", "raw-colour", "%s:%d" % (path, line_of(scan, index)), message, value=literal,
                                 use=use, exact=reported_exact, theme=str(theme_path)))
        for index, literal, px, context, prop in length_hits(scan, root):
            if px == 0 or passes_cut(abs(px), hairline):
                continue
            prefer = "rounded." if "radius" in str(prop) else "spacing."
            name, exact = nearest_length(px, {k: v for k, v in lengths.items() if not k.endswith(".base")}, prefer)
            steps = px / base if base else None
            on_scale = None
            if context == "arbitrary" and prop in SPACING_UTILS and steps is not None and abs(steps * 4 - round(steps * 4)) < 1e-9:
                on_scale = "%s-%s" % (prop, fmt(steps))
            if exact:
                use, message = name, "%s is the theme's %s: use the token (%s)" % (literal, name, theme_path.name)
            elif name:
                use, message = name, ("%s is off the theme's scale; nearest is %s (%spx)" % (literal, name, fmt(lengths[name])))
            else:
                use, message = None, "%s is a raw length and %s declares no lengths" % (literal, theme_path.name)
            if on_scale is not None:
                use, message = on_scale, "%s-[%s] is an arbitrary value; on the %spx step it is %s" % (prop, literal, fmt(base), on_scale)
            found.append(finding("tokens", "raw-length", "%s:%d" % (path, line_of(scan, index)), message, value=literal,
                                 use=use, exact=exact, theme=str(theme_path)))
        sups, problems = parse_suppressions(text, path)
        kept, applied = apply_suppressions(found, sups)
        findings += kept + problems
        suppressions += applied
    proposals = record_proposals(tokens, load_tokens(args.baseline)[0]) if args.baseline else []
    return report("tokens", overall_status(findings, proposals), findings, files=len(files), theme=str(theme_path),
                  suppressions=suppressions, proposals=proposals)


# ---- contrast (DG-14) ----------------------------------------------------------------------------------------------

def base_component(name, names):
    candidates = [other for other in names if other != name and name.startswith(other + "-")]
    return max(candidates, key=len) if candidates else None


def component_props(components, name):
    chain = [name]
    base = base_component(name, components)
    while base:
        chain.append(base)
        base = base_component(base, components)
    props = {}
    for link in reversed(chain):
        entry = components.get(link)
        props.update(entry if isinstance(entry, dict) else {})
    own = components.get(name) if isinstance(components.get(name), dict) else {}
    inherited = ["%s from %s" % (key, next(link for link in chain if key in (components.get(link) or {})))
                 for key in sorted(props) if key not in own]
    return props, inherited


def type_of(props, tokens, depth, root):
    spec = props.get("typography")
    spec, _ = resolve(tokens, spec, depth) if isinstance(spec, str) else (spec, None)
    spec = spec if isinstance(spec, dict) else {}
    size_text, _ = resolve(tokens, spec.get("fontSize", props.get("fontSize")), depth)
    weight, _ = resolve(tokens, spec.get("fontWeight", props.get("fontWeight", 400)), depth)
    lm = LENGTH_RE.fullmatch(size_text.strip()) if isinstance(size_text, str) else None
    size = to_px(lm, root) if lm else None
    if isinstance(weight, str):
        weight = 700 if weight.strip().lower() == "bold" else int(weight) if weight.strip().isdigit() else 400
    return size, weight if number(weight) else 400


def cmd_contrast(args):
    thresholds = load_thresholds(args.thresholds)
    depth = need(thresholds, "ref-depth-max", "cut")["value"]
    text_t = need(thresholds, "contrast-text", "cut")["value"]
    ui_t = need(thresholds, "contrast-large-and-ui", "cut")["value"]
    large_px = need(thresholds, "large-text-px", "cut")["value"]
    bold = need(thresholds, "large-text-bold-px", "cut")
    root = need(thresholds, "root-font-px", "value")["value"]
    tokens, _ = load_tokens(args.record)
    colors = tokens.get("colors") if isinstance(tokens.get("colors"), dict) else {}
    findings, pairs = [], []

    def colour(value, label):
        resolved, error = resolve(tokens, value, depth)
        if error:
            findings.append(finding("contrast", error, label, "%r does not resolve (%s)" % (value, error)))
            return None
        rgba = parse_colour(resolved) if isinstance(resolved, str) else None
        if rgba is None:
            findings.append(finding("contrast", "bad-colour", label, "%r is not a colour" % (resolved,)))
        return rgba
    page = colour(colors["background"], "colors.background") if "background" in colors else None

    def check(label, fg_value, bg_value, needs, kind, inherited=None):
        fg = colour(fg_value, label)
        bg = colour(bg_value, label) if bg_value is not None else page
        if fg is None or bg is None:
            if fg is not None:
                findings.append(finding("contrast", "contrast-unresolved", label,
                                        "no background to measure against: set backgroundColor or colors.background"))
            return None
        if bg[3] < 1:
            if page is None or page[3] < 1:
                findings.append(finding("contrast", "contrast-unresolved", label,
                                        "the background has alpha and no opaque colors.background lies under it: "
                                        "measure the rendered pixels (DG-24)"))
                return None
            bg = composite(bg, page)
        if fg[3] < 1:
            fg = composite(fg, bg)
        ratio = contrast_ratio(fg, bg)
        row = {"pair": label, "ratio": floor2(ratio), "needs": needs, "kind": kind,
               "status": "passed" if ratio >= needs else "failed"}
        if inherited:
            row["inherited"] = inherited
        pairs.append(row)
        if ratio < needs:
            findings.append(finding("contrast", "contrast-fail", label, "%s:1 for %s; needs %s:1%s" % (
                fmt(floor2(ratio)), kind, fmt(needs), (" (inherits " + "; ".join(inherited) + ")") if inherited else "")))
        return ratio
    for name in sorted(colors):
        for fg_name in ("on-" + name, name + "-foreground"):
            if fg_name in colors:
                check("colors.%s on colors.%s" % (fg_name, name), colors[fg_name], colors[name], text_t, "text")
    fg_ratio = None
    if "foreground" in colors and "background" in colors:
        fg_ratio = check("colors.foreground on colors.background", colors["foreground"], colors["background"], text_t, "text")
    if "ring" in colors:
        check("colors.ring on colors.background", colors["ring"], colors.get("background"), ui_t, "focus ring")
    if "muted-foreground" in colors and fg_ratio is not None and page is not None and page[3] >= 1:
        muted_rgba = colour(colors["muted-foreground"], "colors.muted-foreground")
        if muted_rgba is not None:
            muted = contrast_ratio(composite(muted_rgba, page) if muted_rgba[3] < 1 else muted_rgba, page)
            if muted > fg_ratio:
                findings.append(finding("contrast", "muted-stronger", "colors.muted-foreground",
                                        "muted text (%s:1) is stronger than primary text (%s:1) on colors.background"
                                        % (fmt(floor2(muted)), fmt(floor2(fg_ratio)))))
    components = tokens.get("components") if isinstance(tokens.get("components"), dict) else {}
    for name in sorted(components):
        props, inherited = component_props(components, name)
        if "textColor" in props:
            size, weight = type_of(props, tokens, depth, root)
            large = size is not None and (size >= large_px or (size >= bold["value"] and weight >= bold.get("weight", 700)))
            needs = ui_t if large else text_t
            check("components.%s text" % name, props["textColor"], props.get("backgroundColor"), needs,
                  "large text" if large else "text", inherited)
        if "iconColor" in props:
            check("components.%s icon" % name, props["iconColor"], props.get("backgroundColor"), ui_t, "icon", inherited)
    if not pairs and not findings:
        raise NotRun("no colour pairs to check: name X with on-X or X-foreground, foreground and background, or "
                     "components with textColor or iconColor")
    return report("contrast", overall_status(findings), findings, record=str(args.record), pairs=pairs)


# ---- rules (DG-6, DG-8, DG-10, DG-17, DG-22) ----------------------------------------------------------------------

BLOCK_RE = re.compile(r"(?:(?<=[{}])|^)([^{}]+)\{([^{}]*)\}")  # starts only after a brace: linear on brace-free text
GRADIENT_RE = re.compile(r"(?:repeating-)?(?:linear|radial|conic)-gradient\(", re.I)
CLASS_RE = re.compile(r"\bclass(?:Name)?\s*=\s*\{?\s*[\"'`]([^\"'`]*)[\"'`]")


MEDIA_RE = re.compile(r"@media\b([^{]*)\{")


def unhover(text):
    """The text with every rule whose selector holds :hover blanked (positions kept)."""
    ranges = []
    for m in re.finditer(r":hover\b", text):
        start = max(text.rfind("}", 0, m.start()), text.rfind("{", 0, m.start()), text.rfind(";", 0, m.start())) + 1
        opening = text.find("{", m.end())
        closing = text.find("}", opening) if opening >= 0 else -1
        if closing >= 0 and "}" not in text[m.end():opening] and "{" not in text[opening + 1:closing]:
            ranges.append((start, closing + 1))
    out, last = [], 0
    for start, end in sorted(ranges):
        if start < last:
            continue
        out.append(text[last:start])
        out.append(blank(text[start:end]))
        last = end
    return "".join(out) + text[last:]


def blank(text):
    return re.sub(r"[^\n]", " ", text)


def block_end(text, open_index):
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def keep_only(text, ranges):
    """The text with everything outside the ranges blanked, line breaks kept, so positions still map to lines."""
    out, last = [], 0
    for start, end in sorted(ranges):
        out.append(blank(text[last:start]))
        out.append(text[start:end])
        last = end
    out.append(blank(text[last:]))
    return "".join(out)


def media_scopes(text, hover=True):
    """[(scope, text)] for the pairing checks (DG-29): the rules for every medium alone, then those rules with one
    @media block at a time, then (with hover) those rules with the :hover rules. Two @media blocks never combine."""
    blocks = []
    for m in MEDIA_RE.finditer(text):
        if blocks and m.start() < blocks[-1][1]:
            continue
        blocks.append((m.start(), block_end(text, m.end() - 1), " ".join(m.group(1).split())))
    outside, last = [], 0
    for start, end, _ in blocks:
        outside.append((last, start))
        last = end
    outside.append((last, len(text)))
    out = [("all media", unhover(keep_only(text, outside)))]
    out += [("@media " + query, unhover(keep_only(text, outside + [(start, end)]))) for start, end, query in blocks]
    if hover:
        out.append(("hover", keep_only(text, outside)))
    return out


def balanced(text, open_index, cap=600):
    depth, i = 0, open_index
    while i < len(text) and i - open_index < cap:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_index + 1:i]
        i += 1
    return text[open_index + 1:i]


def matcher(rule, thresholds):
    """A function from text to [(index, matched text)] for one rule."""
    kind = rule["kind"]
    if kind == "regex":
        pattern = re.compile(rule["pattern"])
        return lambda text: [(m.start(), m.group(0)) for m in pattern.finditer(text)]
    if kind == "colour-pair":
        band_a, band_b = (need(thresholds, b, "band") for b in rule["bands"])

        def pair(text):
            for scope, part in media_scopes(text):
                hits = colour_hits(part)
                in_a = [h for h in hits if in_band(h[2], band_a)]
                in_b = [h for h in hits if in_band(h[2], band_b)]
                if in_a and in_b:
                    return [(in_a[0][0], "%s with %s (%s)" % (in_a[0][1], in_b[0][1], scope))]
            return []
        return pair
    if kind == "card-chrome":
        limit = need(thresholds, rule["threshold"], "cut")

        def chrome(text):
            for scope, part in media_scopes(text, hover=False):
                groups = collections.defaultdict(list)
                for m in BLOCK_RE.finditer(part):
                    selector = m.group(1).strip()
                    if not re.search(r"card", selector, re.I):
                        continue
                    decls = {kebab(d.group("prop")): " ".join(d.group("value").lower().split()) for d in DECL_RE.finditer(m.group(2))}
                    radius, shadow = decls.get("border-radius"), decls.get("box-shadow")
                    if radius and shadow and shadow != "none":
                        groups[(radius, shadow)].append((m.start(1) + len(m.group(1)) - len(m.group(1).lstrip()), selector))
                for (radius, shadow), members in groups.items():
                    if not passes_cut(len(members), limit):
                        return [(members[0][0], "%d card rules share border-radius %s and box-shadow %s (%s)" % (
                            len(members), radius, shadow, scope))]
            return []
        return chrome
    if kind == "gradient-hue":
        band_a, band_b = (need(thresholds, b, "band") for b in rule["bands"])
        from_re, to_re = re.compile(rule["from_classes"]), re.compile(rule["to_classes"])

        def gradient(text):
            out = []
            for m in GRADIENT_RE.finditer(text):
                inner = balanced(text, m.end() - 1)
                stops = [hit[2] for hit in literal_colours(inner)]
                if any(in_band(c, band_a) for c in stops) and any(in_band(c, band_b) for c in stops):
                    out.append((m.start(), text[m.start():m.end() + len(inner) + 1]))
            for m in CLASS_RE.finditer(text):
                if from_re.search(m.group(1)) and to_re.search(m.group(1)):
                    out.append((m.start(1), m.group(1)))
            return out
        return gradient
    if kind == "font-size-min":
        floor = need(thresholds, rule["threshold"], "cut")
        root = need(thresholds, "root-font-px", "value")["value"]

        def font_size(text):
            out = []
            for m in DECL_RE.finditer(text):
                if kebab(m.group("prop")) != "font-size":
                    continue
                for lm in LENGTH_RE.finditer(m.group("value")):
                    px = to_px(lm, root)
                    if px > 0 and not passes_cut(px, floor):
                        out.append((m.start(), m.group(0).strip()))
            for m in ARBITRARY_RE.finditer(text):
                lm = LENGTH_RE.fullmatch(m.group("value"))
                if m.group("util") == "text" and lm and not passes_cut(to_px(lm, root), floor):
                    out.append((m.start(), m.group(0)))
            return out
        return font_size
    raise ValueError("unknown kind " + str(kind))


def examples(value):
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list) or not items or not all(text_value(i) for i in items):
        return None
    return items


def load_rules(path, thresholds):
    try:
        data, dupes = load_json(read_text(path), str(path))
    except Unreadable as exc:
        raise NotRun("rules refused: %s" % exc)
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules or data.get("format") != "westack-design-rules-1":
        raise NotRun("rules refused: %s is not a westack-design-rules-1 file with rules" % path)
    problems, ids = [], set()
    for rule in rules:
        rid = rule.get("id") if isinstance(rule, dict) else None
        if not text_value(rid) or rid in ids:
            problems.append("a rule has no id or a repeated one: %r" % (rid,))
            continue
        ids.add(rid)
        for key in ("tier", "kind", "message", "source", "basis", "since"):
            if not text_value(rule.get(key)):
                problems.append("%s: no %s" % (rid, key))
        if rule.get("tier") not in TIERS or rule.get("kind") not in RULE_KINDS or rule.get("basis") not in BASES:
            problems.append("%s: tier, kind or basis outside %s, %s, %s" % (rid, TIERS, RULE_KINDS, BASES))
            continue
        if rule.get("policy") is not None and rule["policy"] not in POLICY_WORDS:
            problems.append("%s: policy is one of %s" % (rid, ", ".join(POLICY_WORDS)))
        if rule.get("tell") and (rule.get("status") not in TELL_STATUS or not isinstance(rule.get("brief_terms"), list)
                                 or not all(isinstance(g, list) and g and all(text_value(t) for t in g) for g in rule["brief_terms"])):
            problems.append("%s: a tell needs a status (%s) and brief_terms as lists of words" % (rid, ", ".join(TELL_STATUS)))
        must, must_not = examples(rule.get("must_match")), examples(rule.get("must_not_match"))
        if not must or not must_not:
            problems.append("%s: needs must_match and must_not_match examples" % rid)
            continue
        try:
            match = matcher(rule, thresholds)
        except (re.error, KeyError, TypeError, ValueError, NotRun) as exc:
            problems.append("%s: cannot load: %s" % (rid, exc))
            continue
        for example in must:
            if not match(example):
                problems.append("%s: misses its must_match example %r" % (rid, example[:60]))
        for example in must_not:
            if match(example):
                problems.append("%s: matches its must_not_match example %r" % (rid, example[:60]))
    if problems:
        raise NotRun("rules refused: " + "; ".join(problems[:12]))
    return rules


def brief_allows(rule, brief):
    if not rule.get("tell"):
        return None
    for group in rule.get("brief_terms", []):
        if all(re.search(r"\b" + re.escape(term.lower()) + r"\b", brief) for term in group):
            return group
    return None


def motion_policy(record_path):
    """The record's motion policy (DG-25), or None when the record holds none."""
    tokens, _ = load_tokens(record_path)
    policy = tokens.get("motion")
    return policy if isinstance(policy, dict) else None


def policy_exception(rule, policy, text, index):
    """The exception word that covers a match: the record lists it for this policy word and it appears in the CSS
    selector or the line around the match."""
    words = (policy.get("except") or {}).get(rule["policy"], []) if isinstance(policy.get("except"), dict) else []
    start = text.rfind("}", 0, index) + 1
    if index - start > 400:
        start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    context = text[start:line_end if line_end >= 0 else len(text)].lower()
    return next((w for w in words if isinstance(w, str) and re.search(r"\b" + re.escape(w.lower()) + r"\b", context)), None)


def cmd_rules(args):
    thresholds = load_thresholds(args.thresholds)
    rules = load_rules(args.rules, thresholds)
    brief = read_text(args.brief).lower()
    files, missing = walk(args.src)
    if not files:
        raise NotRun("no source files to check")
    policy = motion_policy(args.record) if args.record else None
    live, policy_not_run = [], []
    for rule in (r for r in rules if r.get("status") != "retired"):
        word = rule.get("policy")
        if word and policy is None:
            policy_not_run.append({"rule": rule["id"], "why": "no motion policy recorded (--record RECORD with a motion block)"})
        elif not word or policy.get(word) == "never":
            live.append(rule)
    matchers = {r["id"]: matcher(r, thresholds) for r in live}
    findings, answer, allowed, suppressions, problems, excepted = [], [], [], [], [], []
    problems += [finding("rules", "missing-source", m, "no such file or folder") for m in missing]
    control_hits = collections.Counter()
    if args.control:
        control_files, control_missing = walk(args.control)
        problems += [finding("rules", "missing-source", m, "no such control file or folder") for m in control_missing]
        for path in control_files:
            scan = blank_comments(read_text(path))
            for rule in live:
                control_hits[rule["id"]] += len(matchers[rule["id"]](scan))
        calibration = {"control_files": [str(p) for p in control_files],
                       "false_positives": {k: v for k, v in sorted(control_hits.items()) if v}}
    else:
        calibration = {"status": "not-run", "why": "no human control page (--control): the rules' precision on real "
                                                   "pages is unknown, so a reflex finding is a lead (DG-28)"}
    for path in files:
        text = read_text(path)
        scan = blank_comments(text)
        found = []
        for rule in live:
            for index, hit in matchers[rule["id"]](scan):
                item = finding("rules", rule["id"], "%s:%d" % (path, line_of(scan, index)), rule["message"],
                               rule=rule["id"], tier=rule["tier"], value=hit if len(hit) <= 160 else hit[:157] + "...",
                               items=rule.get("items"), file=str(path))
                terms = brief_allows(rule, brief)
                if terms:
                    allowed.append(dict(item, brief_terms=terms))
                    continue
                excepted_by = policy_exception(rule, policy, scan, index) if rule.get("policy") else None
                if excepted_by:
                    excepted.append(dict(item, excepted_by=excepted_by))
                    continue
                found.append(item)
        sups, sup_problems = parse_suppressions(text, path)
        kept, applied = apply_suppressions(found, sups)
        problems += sup_problems
        suppressions += applied
        for item in kept:
            (answer if item["tier"] == "finish" else findings).append(item)
    waived = []
    if args.waivers:
        accepted, rejected = check_waivers(pathlib.Path(args.waivers), {r["id"]: r for r in rules}, thresholds)
        remaining = []
        for item in findings:
            match = next((w for w in accepted if w["rule"] == item["rule"] and same_page(w, item)), None)
            if match is not None and item["tier"] == "reflex":
                waived.append(dict(item, waiver_reason=match["reason"]))
            else:
                remaining.append(item)
        findings = remaining
        problems += [finding("rules", "waiver-rejected", "%s waiver %d" % (args.waivers, w["number"]),
                             "waiver for %s rejected (%s); its finding stands" % (w.get("rule"), ", ".join(w["problems"])))
                     for w in rejected]
    review = []
    if control_hits:
        held = [item for item in findings if item.get("tier") == "reflex" and control_hits[item["rule"]]]
        review = [dict(item, control_false_positives=control_hits[item["rule"]]) for item in held]
        findings = [item for item in findings if item not in held]
    findings += problems
    return report("rules", overall_status(findings), findings, files=len(files), answer=answer,
                  allowed_by_brief=allowed, waived=waived, excepted_by_policy=excepted, policy_not_run=policy_not_run,
                  calibration=calibration, review_before_gating=review, suppressions=suppressions)


# ---- waivers (DG-8) ------------------------------------------------------------------------------------------------

GENERIC_WORDS = set("""a an the this that it its it's is are was be for of on in to by as per our we us they their
our client clients user users team wants wanted want asked request requested requests design designed designs choice
choices decision decisions intentional intentionally deliberate deliberately conscious brand branding branded style
styled stylistic aesthetic aesthetics look looks looking feel good nice fine ok okay approved preference preferred
choose chose chosen keep kept like liked page pages site screen n/a na none wontfix fix fixed just reason reasons
because purpose purposes""".split())


def words_of(text):
    return re.findall(r"[a-z0-9/']+", str(text or "").lower())


def boilerplate(reason, page=""):
    page_words = set(words_of(pathlib.Path(page).stem.replace("-", " ").replace("_", " ")))
    content = [w for w in words_of(reason) if w not in GENERIC_WORDS and w not in page_words]
    return len(words_of(reason)) < 6 or not content


def names_page(reason, page):
    stem_words = [w for w in words_of(pathlib.Path(page).stem.replace("-", " ").replace("_", " ")) if len(w) >= 3]
    said = set(words_of(reason))
    return bool(stem_words) and any(w in said for w in stem_words) or str(page).lower() in str(reason).lower()


def same_page(waiver_item, finding_item):
    page = waiver_item["base"] / waiver_item["page"]
    return same_file(page, finding_item["file"]) or (
        not page.exists() and pathlib.Path(waiver_item["page"]).name == pathlib.Path(finding_item["file"]).name)


def check_waivers(path, rules_by_id, thresholds):
    data, _ = load_json(read_text(path), str(path))
    waivers = data.get("waivers") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("format") != "westack-design-waivers-1" or not isinstance(waivers, list):
        raise Unreadable("%s is not a westack-design-waivers-1 file with a waivers list" % path)
    base = path.parent
    normalise = lambda text: " ".join(words_of(text))
    reasons = collections.Counter(normalise(w.get("reason")) for w in waivers if isinstance(w, dict))
    accepted, rejected = [], []
    for number_, item in enumerate(waivers, 1):
        item = item if isinstance(item, dict) else {}
        problems = []
        rule = rules_by_id.get(item.get("rule"))
        page, reason, key = item.get("page"), item.get("reason"), normalise(item.get("reason"))
        if rule is None:
            problems.append("unknown-rule")
        elif rule["tier"] == "floor":
            problems.append("floor-not-waivable")
        elif rule["tier"] == "finish":
            problems.append("finish-needs-no-waiver")
        if not text_value(page) or not text_value(reason):
            problems.append("page-or-reason-missing")
        else:
            if boilerplate(reason, page):
                problems.append("reason-boilerplate")
            if not names_page(reason, page):
                problems.append("reason-page-free")
            if reasons[key] > 1:
                problems.append("reason-copied")
            elif rule is not None and key == normalise(rule["message"]):
                problems.append("reason-copied")
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        guard_ok = False
        if text_value(evidence.get("file")) and text_value(evidence.get("text")) and text_value(page):
            evidence_file = base / evidence["file"]
            on_page = same_file(evidence_file, base / page)
            try:
                body = " ".join(read_text(evidence_file).split())
            except Unreadable:
                body = ""
            shown = " ".join(evidence["text"].split())
            pattern_ok = True
            if rule is not None:
                try:
                    pattern_ok = bool(matcher(rule, thresholds)(evidence["text"]))
                except (re.error, KeyError, TypeError, ValueError, NotRun):
                    pattern_ok = False
            guard_ok = on_page and bool(shown) and shown in body and pattern_ok
        if not guard_ok:
            problems.append("guard-failed")
        record = dict(item, number=number_, base=base)
        if problems:
            rejected.append(dict(record, problems=problems))
        else:
            accepted.append(record)
    return accepted, rejected


def cmd_waivers(args):
    thresholds = load_thresholds(args.thresholds)
    rules = load_rules(args.rules, thresholds)
    accepted, rejected = check_waivers(pathlib.Path(args.file), {r["id"]: r for r in rules}, thresholds)
    clean = lambda w: {k: v for k, v in w.items() if k != "base"}
    findings = [finding("waivers", "waiver-rejected", "%s waiver %d" % (args.file, w["number"]),
                        "waiver for %s rejected: %s" % (w.get("rule"), ", ".join(w["problems"])), problems=w["problems"])
                for w in rejected]
    return report("waivers", overall_status(findings), findings, accepted=[clean(w) for w in accepted],
                  rejected=[clean(w) for w in rejected])


# ---- inventory (DG-16) ---------------------------------------------------------------------------------------------

HANDLER_RE = re.compile(r"^(?:on[a-z]+|@[\w.:-]+|v-on:[\w.-]+|on:[\w-]+|\([\w.-]+\)|hx-(?:get|post|put|patch|delete))$")
TEST_HOOKS = ("data-testid", "data-test", "data-test-id", "data-cy", "data-qa")
LANDMARKS = ("header", "nav", "main", "section", "article", "aside", "footer")
KINDS = ("link", "form", "field", "handler", "hook", "script")


class Wiring(html.parser.HTMLParser):
    """The links, forms, fields, handlers, test hooks, scripts and landmark order of one HTML file."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items, self.sections = {}, []
        self.forms, self.form, self.script, self.buffer = 0, None, None, []

    def add(self, kind, key, **detail):
        self.items.setdefault(key, dict(detail, kind=kind, line=self.getpos()[0]))

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "a" and "href" in a:
            self.add("link", "link:" + a["href"].strip())
        if tag == "form":
            self.forms += 1
            self.form = a.get("id") or a.get("name") or a.get("action") or "#%d" % self.forms
            self.add("form", "form:" + self.form, action=a.get("action"), method=a.get("method", "get").lower())
        if tag in ("input", "select", "textarea", "button") and (a.get("name") or a.get("id")):
            self.add("field", "field:" + (a.get("name") or a.get("id")), tag=tag, type=a.get("type", ""), form=self.form)
        for key, value in a.items():
            if HANDLER_RE.match(key):
                self.add("handler", "handler:%s=%s" % (key, value.strip()))
            if key in TEST_HOOKS:
                self.add("hook", "hook:%s=%s" % (key, value.strip()))
        if tag == "script":
            if a.get("src"):
                self.add("script", "script:" + a["src"].strip())
            else:
                self.script, self.buffer = self.getpos()[0], []
        if tag in LANDMARKS:
            ident = a.get("id") or a.get("data-section") or a.get("aria-label")
            if ident:
                self.sections.append("%s#%s" % (tag, ident))

    def handle_endtag(self, tag):
        if tag == "form":
            self.form = None
        if tag == "script" and self.script is not None:
            content = "".join(self.buffer).strip()
            if content:
                self.items.setdefault("script:inline:" + hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
                                      {"kind": "script", "line": self.script})
            self.script = None

    def handle_data(self, data):
        if self.script is not None:
            self.buffer.append(data)


def wiring(path):
    parser = Wiring()
    parser.feed(read_text(path))
    parser.close()
    return parser


def cmd_inventory(args):
    before, after = wiring(args.before), wiring(args.after)
    before_items, after_items = before.items, after.items
    if not before_items:
        raise NotRun("the before page has no links, forms, fields, handlers, hooks or scripts: nothing to keep")
    findings, dropped, dropped_ok = [], [], set()
    if args.dropped:
        data, _ = load_json(read_text(args.dropped), str(args.dropped))
        entries = data.get("dropped") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise Unreadable("%s holds no dropped list" % args.dropped)
        for entry in entries:
            entry = entry if isinstance(entry, dict) else {}
            key = entry.get("key")
            if key not in before_items:
                findings.append(finding("inventory", "drop-unknown", str(key), "a dropped item that the before page does not have"))
            elif not (text_value(entry.get("reason")) and text_value(entry.get("evidence"))):
                findings.append(finding("inventory", "drop-unreasoned", key, "a dropped item needs a reason and evidence"))
            else:
                dropped_ok.add(key)
                dropped.append({"key": key, "reason": entry.get("reason"), "evidence": entry.get("evidence")})
    kept = []
    for key in sorted(before_items):
        if key in after_items:
            kept.append(key)
        if key not in after_items and key not in dropped_ok:
            findings.append(finding("inventory", "missing", key, "%s was on the page before the redesign and is gone; "
                                    "restore it or record it as dropped with a reason and evidence" % before_items[key]["kind"],
                                    line=before_items[key]["line"]))
    common_before = [s for s in before.sections if s in after.sections]
    common_after = [s for s in after.sections if s in before.sections]
    depth = args.depth
    if depth != "full" and common_before != common_after:
        findings.append(finding("inventory", "sections-moved", str(args.after),
                                "a %s keeps the page's structure, but sections moved: %s became %s" % (
                                    depth, " > ".join(common_before), " > ".join(common_after))))
    counts = {kind: sum(1 for item in before_items.values() if item["kind"] == kind) for kind in KINDS}
    added = sorted(set(after_items) - set(before_items))
    notes = ["sections without an id, data-section or aria-label are not order-checked"]
    return report("inventory", overall_status(findings), findings, depth=depth, counts=counts, kept=kept,
                  dropped=dropped, added=added, notes=notes)


# ---- record (DG-12, DG-20, DG-21) ----------------------------------------------------------------------------------

SECTIONS = ("Overview", "Colors", "Typography", "Layout", "Elevation", "Shapes", "Components", "Do and Don't")
SECTION_KEYS = {"Colors": "colors", "Typography": "typography", "Layout": "spacing", "Shapes": "rounded",
                "Components": "components"}
TOKEN_GROUPS = ("colors", "typography", "rounded", "spacing", "components")
META_KEYS = ("format", "omitted", "derived", "motion", "references", "invariants", "signoff")
OBSERVED_BY = ("measurement", "pixel-sample", "recording")  # DG-40: how a promise is observed
REFERENCE_FIELDS = ("goal", "source", "date", "viewport", "trigger", "response", "class", "licence", "cost", "why",
                    "avoid_when")
# DG-33: what each capture class can show. The engine's own record (keyframes and timing from the animation list, the
# CSS rules in force, shader source and uniforms) and samples taken while it runs are observed; source recovered from
# the page shows what the code says (present); a library named from its bundle, or code not read, shows nothing yet.
CLASS_CEILING = {"exact": "observed", "sampled": "observed", "recovered": "present", "bundle-match": "claimed",
                 "unread": "claimed"}
# An easing curve is the path between the values: samples show only the moments taken, so a curve stands on exact
# evidence (observed) or recovered source (present) and stays claimed otherwise.
CURVE_CEILING = {"exact": "observed", "recovered": "present"}
CURVE_RE = re.compile(r"cubic-bezier|\beasing\b|\bease(?:-in-out|-in|-out)?\b|\bspring\b|\blinear\(|\bsteps\(|"
                      r"\btiming function\b", re.I)


def motion_findings(motion):
    """The shape of a record's motion policy (DG-25): each policy word is never or allowed, exceptions name policy
    words, and the policy says who decided it, when and why."""
    where = "motion"
    if not isinstance(motion, dict):
        return [finding("record", "motion-policy-shape", where, "motion is an object of policy words")]
    out = []
    for key, value in motion.items():
        if key in POLICY_WORDS:
            if value not in ("never", "allowed"):
                out.append(finding("record", "motion-policy-shape", "motion." + key, "a policy word is never or allowed"))
        elif key == "except":
            if not (isinstance(value, dict) and all(k in POLICY_WORDS and isinstance(v, list) and all(text_value(x) for x in v)
                                                    for k, v in value.items())):
                out.append(finding("record", "motion-policy-shape", "motion.except", "except maps a policy word to the "
                                   "names (selectors, components) it does not cover"))
        elif key not in ("decided_by", "date", "reason", "source"):
            out.append(finding("record", "motion-policy-shape", "motion." + key, "not a policy word: %s" % ", ".join(POLICY_WORDS)))
    for key in ("decided_by", "date", "reason"):
        if not text_value(motion.get(key)):
            out.append(finding("record", "motion-policy-shape", "motion." + key, "a motion policy says who decided it, "
                               "when and why"))
    return out


def reference_findings(refs):
    """DG-35: a direction's one to three references, each with its whole record: the goal it serves, source, date,
    viewport, trigger, response, capture class, licence, cost, why it works and when not to use it. Whether a build
    copies a reference is judged in review; this checks the record only."""
    if not isinstance(refs, list):
        return [finding("record", "references-shape", "references", "references is a list with one object per reference")]
    out = []
    if len(refs) > 3:
        out.append(finding("record", "references-count", "references", "a direction borrows from one to three "
                           "references, not %d" % len(refs)))
    for n, ref in enumerate(refs):
        where = "references[%d]" % n
        ref = ref if isinstance(ref, dict) else {}
        missing = [key for key in REFERENCE_FIELDS if not text_value(ref.get(key))]
        if missing:
            out.append(finding("record", "reference-incomplete", where, "missing %s: a reference records the goal it "
                               "serves, source, date, viewport, trigger, response, capture class, licence, cost, why it "
                               "works and when not to use it (avoid_when)" % ", ".join(missing)))
        if text_value(ref.get("date")) and not ISO_DATE.fullmatch(ref["date"].strip()):
            out.append(finding("record", "bad-value", where + ".date", "a date is YYYY-MM-DD"))
        if text_value(ref.get("class")) and ref["class"] not in CLASS_CEILING:
            out.append(finding("record", "bad-value", where + ".class", "the capture class is one of " + ", ".join(CLASS_CEILING)))
    return out


def invariant_findings(items):
    """DG-40: a direction's promises are invariants a check can observe: the promise, the widths it holds at (states
    are optional, the resting state by default) and how it is observed. "Feels premium" names no way to observe it."""
    if not isinstance(items, list):
        return [finding("record", "invariants-shape", "invariants", "invariants is a list with one object per promise")]
    out = []
    for n, item in enumerate(items):
        where = "invariants[%d]" % n
        item = item if isinstance(item, dict) else {}
        widths = item.get("widths")
        widths = isinstance(widths, list) and bool(widths) and all(number(w) and w > 0 for w in widths)
        if item.get("observed_by") not in OBSERVED_BY:
            out.append(finding("record", "invariant-unobservable", where, "a promise names how it is observed (observed_by: "
                               "%s); one nothing can observe is not an invariant" % ", ".join(OBSERVED_BY)))
        if not text_value(item.get("promise")):
            out.append(finding("record", "invariant-incomplete", where, "an invariant states its promise"))
        if not widths:
            out.append(finding("record", "invariant-incomplete", where, "an invariant names the widths (px) it holds at"))
    return out


def signoff_findings(items):
    """DG-40: a sign-off records who accepted which captures, and when."""
    if not isinstance(items, list):
        return [finding("record", "signoff-shape", "signoff", "signoff is a list with one object per acceptance")]
    out = []
    for n, item in enumerate(items):
        item = item if isinstance(item, dict) else {}
        captures = item.get("captures")
        missing_signoff = [key for key in ("by", "date") if not text_value(item.get(key))]
        if not (isinstance(captures, list) and captures and all(text_value(c) for c in captures)):
            missing_signoff.append("captures")
        if missing_signoff:
            out.append(finding("record", "signoff-incomplete", "signoff[%d]" % n, "missing %s: a sign-off names who "
                               "accepted, when, and which captures" % ", ".join(missing_signoff)))
    return out


TYPE_PROPS = {"fontSize", "fontWeight", "fontFamily", "lineHeight", "letterSpacing"}


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        previous, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (ca != cb))
    return row[-1]


def token_like(value):
    if isinstance(value, str):
        return parse_colour(value) is not None or LENGTH_RE.fullmatch(value.strip()) is not None
    if isinstance(value, dict):
        return bool(TYPE_PROPS & set(value)) or any(token_like(v) for v in value.values())
    if isinstance(value, list):
        return any(token_like(v) for v in value)
    return False


def slug(text):
    return re.sub(r"[^a-z0-9-]+", "-", str(text).lower().replace(".", "-")).strip("-")


def generate(tokens, name, kind, depth):
    """The derived file a record generates: CSS custom properties or a flat JSON map, deterministic."""
    values = {}
    for group, prefix in (("colors", "color"), ("spacing", "spacing"), ("rounded", "rounded")):
        node = tokens.get(group) if isinstance(tokens.get(group), dict) else {}
        for path, value in leaves(node):
            resolved, error = resolve(tokens, value, depth)
            if not error and isinstance(resolved, (str, int, float)) and not isinstance(resolved, bool):
                values["--%s-%s" % (prefix, slug(path))] = str(resolved)
    typography = tokens.get("typography") if isinstance(tokens.get("typography"), dict) else {}
    for role in sorted(typography):
        spec, error = resolve(tokens, typography[role], depth)
        if error or not isinstance(spec, dict):
            continue
        for prop in sorted(spec):
            resolved, error = resolve(tokens, spec[prop], depth)
            if not error and isinstance(resolved, (str, int, float)) and not isinstance(resolved, bool):
                values["--typography-%s-%s" % (slug(role), kebab(prop))] = str(resolved)
    if kind == "css":
        lines = ["/* generated from %s by designcheck.py record --emit css; edit the record, not this file */" % name, ":root {"]
        lines += ["  %s: %s;" % (key, values[key]) for key in sorted(values)]
        return "\n".join(lines + ["}"]) + "\n"
    return json.dumps({"generated_from": name, "note": "edit the record, not this file", "tokens": values},
                      indent=2, sort_keys=True) + "\n"


def record_proposals(new, old):
    """Tokens and components the new record or theme has and the accepted baseline does not (DG-12)."""
    out = []
    for group in ("colors", "rounded", "spacing", "typography"):
        old_node = old.get(group) if isinstance(old.get(group), dict) else {}
        new_node = new.get(group) if isinstance(new.get(group), dict) else {}
        if group == "typography":
            old_paths, new_paths = set(old_node), list(new_node)
        else:
            old_paths, new_paths = {p for p, _ in leaves(old_node)}, [p for p, _ in leaves(new_node)]
        out += [{"kind": "token", "name": "%s.%s" % (group, p)} for p in new_paths if p not in old_paths]
    old_c = old.get("components") if isinstance(old.get("components"), dict) else {}
    new_c = new.get("components") if isinstance(new.get("components"), dict) else {}
    for name in sorted(set(new_c) - set(old_c)):
        family = name.split("-")[0]
        base = base_component(name, set(old_c) | set(new_c)) or next(
            (other for other in sorted(old_c) if other.split("-")[0] == family), None)
        out.append({"kind": "variant" if base else "component", "name": "components." + name, "base": base})
    return out


def norm_value(value, root):
    rgba = parse_colour(value) if isinstance(value, str) else None
    if rgba:
        return hex_of(rgba)
    lm = LENGTH_RE.fullmatch(value.strip()) if isinstance(value, str) else None
    return fmt(to_px(lm, root)) + "px" if lm else None


def cmd_record(args):
    thresholds = load_thresholds(args.thresholds)
    depth = need(thresholds, "ref-depth-max", "cut")["value"]
    root = need(thresholds, "root-font-px", "value")["value"]
    path = pathlib.Path(args.file)
    problems = []
    tokens, text = load_tokens(path, problems)
    if args.emit:
        return generate(tokens, path.name, args.emit, depth)
    findings = [finding("record", code, where, message) for code, where, message in problems]
    if path.suffix.lower() != ".json":
        fenced = [m.span() for m in ANY_FENCE_RE.finditer(text)]
        headings = [(m.group(1).strip(), line_of(text, m.start())) for m in HEADING_RE.finditer(text)
                    if not any(a <= m.start() < b for a, b in fenced)]
        seen = set()
        for name, line in headings:
            if name in seen:
                findings.append(finding("record", "duplicate-section", "%s:%d" % (path, line), "## %s appears twice" % name))
            seen.add(name)
        order = [(SECTIONS.index(name), name, line) for name, line in headings if name in SECTIONS]
        for previous, current in zip(order, order[1:]):
            if current[0] < previous[0]:
                findings.append(finding("record", "section-order", "%s:%d" % (path, current[2]),
                                        "## %s comes after ## %s; the order is %s" % (current[1], previous[1], ", ".join(SECTIONS))))
                break
        omitted = tokens.get("omitted", {})
        if not isinstance(omitted, dict):
            findings.append(finding("record", "bad-value", "omitted", "omitted maps a section name to its reason"))
            omitted = {}
        for name, reason in omitted.items():
            if name not in SECTIONS:
                findings.append(finding("record", "omission-unknown", "omitted." + name, "no such section: %s" % ", ".join(SECTIONS)))
            elif name in seen:
                findings.append(finding("record", "omission-contradicts", "omitted." + name, "declared omitted, but ## %s is present" % name))
            elif SECTION_KEYS.get(name) in tokens:
                findings.append(finding("record", "omission-contradicts", "omitted." + name,
                                        "declared omitted, but the tokens define %s" % SECTION_KEYS[name]))
            if not text_value(reason):
                findings.append(finding("record", "omission-unreasoned", "omitted." + name, "an omission needs its reason"))
        for name in SECTIONS:
            if name not in seen and name not in omitted:
                findings.append(finding("record", "section-missing", "## " + name,
                                        "an absent section needs a declared reason under omitted, or a reader invents it"))
    for key, value in tokens.items():
        if key in TOKEN_GROUPS or key in META_KEYS:
            continue
        near = sorted((distance(key.lower(), known), known) for known in TOKEN_GROUPS + META_KEYS)
        if near[0][0] <= 2:
            findings.append(finding("record", "key-typo", key, "%r is not a record key; did you mean %r? A misspelt group "
                                    "is read as nothing" % (key, near[0][1])))
        elif token_like(value):
            findings.append(finding("record", "token-like-ignored", key, "%r holds token-like values (colours, sizes or "
                                    "type settings) under a key no reader uses" % key))
    if "motion" in tokens:
        findings += motion_findings(tokens["motion"])
    if "references" in tokens:
        findings += reference_findings(tokens["references"])
    if "invariants" in tokens:
        findings += invariant_findings(tokens["invariants"])
    if "signoff" in tokens:
        findings += signoff_findings(tokens["signoff"])
    for leaf, value in leaves(tokens):
        if leaf.split(".")[0] in META_KEYS:
            continue
        resolved, error = resolve(tokens, value, depth)
        if error:
            findings.append(finding("record", error, leaf, "%s does not resolve (%s)" % (value, error)))
        elif leaf.startswith("colors.") and parse_colour(resolved) is None:
            findings.append(finding("record", "bad-colour", leaf, "%r is not a colour" % (resolved,)))
    derived_rows = []
    listed = tokens.get("derived") if isinstance(tokens.get("derived"), list) else []
    for target in [pathlib.Path(d) for d in args.derived] + [path.parent / d for d in listed if isinstance(d, str)]:
        kind = {".css": "css", ".json": "json"}.get(target.suffix.lower())
        if kind is None:
            findings.append(finding("record", "derived-unknown", str(target), "a derived file is .css or .json"))
            continue
        expected = generate(tokens, path.name, kind, depth)
        if not target.is_file():
            findings.append(finding("record", "derived-missing", str(target), "regenerate it with record --emit %s" % kind))
            continue
        expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
        actual_hash = hashlib.sha256(read_text(target).replace("\r\n", "\n").encode("utf-8")).hexdigest()
        derived_rows.append({"file": str(target), "expected_sha256": expected_hash, "actual_sha256": actual_hash})
        if expected_hash != actual_hash:
            findings.append(finding("record", "derived-drift", str(target), "differs from what the record generates: "
                                    "edit the record and regenerate; never hand-edit a derived file"))
    if args.built:
        findings += built_findings(tokens, args.built, depth, root)
    proposals = record_proposals(tokens, load_tokens(args.baseline)[0]) if args.baseline else []
    return report("record", overall_status(findings, proposals), findings, record=str(path), derived=derived_rows,
                  proposals=proposals)


def built_findings(tokens, built, depth, root):
    files, missing = walk(built, lambda p: p.suffix.lower() in STYLE_EXT | {".html", ".htm"})
    if not files:
        raise NotRun("no built CSS or HTML under %s" % ", ".join(map(str, built)))
    definitions, literals, references = collections.defaultdict(set), collections.Counter(), collections.Counter()
    for path in files:
        text = blank_comments(read_text(path))
        for m in DECL_RE.finditer(text):
            value = m.group("value").strip()
            if m.group("prop").startswith("--"):
                definitions[m.group("prop")].add(norm_value(value, root))
                continue
            literals.update(hex_of(hit[2]) for hit in literal_colours(value))
            literals.update(fmt(to_px(lm, root)) + "px" for lm in LENGTH_RE.finditer(value))
        references.update(m.group(1) for m in re.finditer(r"var\(\s*(--[\w-]+)", text))
    out = []
    for leaf, value in leaves(tokens):
        if leaf.split(".")[0] not in ("colors", "spacing", "rounded") or leaf.endswith(".base"):
            continue
        resolved, error = resolve(tokens, value, depth)
        key = None if error else norm_value(resolved, root)
        if key is None:
            continue
        props = [prop for prop, values in definitions.items() if key in values]
        uses = literals[key] + sum(references[prop] for prop in props)
        if uses == 0:
            out.append(finding("record", "token-not-in-build", leaf, "%s (%s) is not used in the built CSS: the record "
                               "holds what shipped" % (leaf, key)))
        elif uses == 1:
            out.append(finding("record", "token-single-sighting", leaf, "%s (%s) is used once in the built CSS: promote "
                               "a value only when it recurs for the same role" % (leaf, key)))
    return out


# ---- report (DG-1 to DG-5, DG-7, DG-23, DG-24) ---------------------------------------------------------------------

RENDERED_KINDS = ("hierarchy", "prominence", "density", "usability")
RENDERED_EVIDENCE = ("screenshot", "console", "measurement", "recording", "user")
NUMERIC_KINDS = ("width", "height", "size", "font-size", "spacing", "radius", "contrast")
ENVIRONMENT_KEYS = ("os", "browser", "headless", "dpr")
LEVELS = ("claimed", "present", "wired", "tested", "observed")
MODES = ("direction", "critique", "redesign", "system")
RUNTIME_STATUS = ("passed", "failed", "not-run", "blocked")


def check_scores(data, findings):
    scores = data.get("scores")
    if scores is None:
        return None
    if not isinstance(scores, dict) or not isinstance(scores.get("rows"), list):
        findings.append(finding("report", "bad-value", "scores", "scores holds model, rubric, rows, max, total and na"))
        return None
    rubric = scores.get("rubric") if isinstance(scores.get("rubric"), dict) else {}
    criteria = {c.get("id"): c for c in rubric.get("criteria", []) if isinstance(c, dict)}
    for cid, criterion in criteria.items():
        anchors = criterion.get("anchors")
        if not (isinstance(anchors, list) and len(anchors) == 2 and all(text_value(a) for a in anchors)):
            findings.append(finding("report", "anchors-missing", "scores.rubric." + str(cid), "each criterion has two anchor examples"))
    model, checked_for = scores.get("model"), rubric.get("anchors_checked_for")
    if checked_for != model:
        findings.append(finding("report", "anchors-unchecked", "scores.rubric", "the anchors were checked against a human "
                                "for %s, not %s: re-check them when the model changes" % (checked_for, model)))
    weighed = []
    for row in scores["rows"]:
        row = row if isinstance(row, dict) else {}
        where = "scores.%s" % row.get("criterion")
        criterion = criteria.get(row.get("criterion"))
        weight = criterion.get("weight", 1) if criterion else 1
        if criterion is None:
            findings.append(finding("report", "unknown-criterion", where, "a row scores a criterion the rubric names"))
        score = row.get("score")
        if score == "n/a":
            if not text_value(row.get("reason")):
                findings.append(finding("report", "na-unreasoned", where, "an n/a row says why the criterion cannot apply"))
        elif not (isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 3):
            findings.append(finding("report", "bad-score", where, "a score is an integer from 0 to 3, or n/a"))
            continue
        else:
            candidates = row.get("candidates")
            if isinstance(candidates, list) and candidates:
                if score != min(candidates):
                    findings.append(finding("report", "unsure-not-lower", where, "unsure between %s: take the lower" % candidates))
            instance_scores = [i.get("score") for i in row.get("instances", []) if isinstance(i, dict)]
            if instance_scores:
                if score != min(instance_scores):
                    findings.append(finding("report", "not-worst-instance", where, "score the worst instance, not the mean"))
        weighed.append((weight, score))
    counted = [w for w, score in weighed if score != "n/a"]
    maximum = sum(3 * w for w in counted)
    total = sum(w * score for w, score in weighed if score != "n/a")
    na = [row.get("criterion") for row in scores["rows"] if isinstance(row, dict) and row.get("score") == "n/a"]
    if scores.get("max") != maximum:
        findings.append(finding("report", "wrong-denominator", "scores.max", "the maximum is %d once n/a rows leave the "
                                "denominator, not %s" % (maximum, scores.get("max"))))
    if scores.get("total") != total:
        findings.append(finding("report", "wrong-total", "scores.total", "the rows add up to %d, not %s" % (total, scores.get("total"))))
    if sorted(map(str, scores.get("na") or [])) != sorted(map(str, na)):
        findings.append(finding("report", "na-unrecorded", "scores.na", "record the n/a set: %s" % ", ".join(map(str, na))))
    return "%d/%d (n/a: %s)" % (total, maximum, ", ".join(map(str, na)) or "none")


def capture_ceiling(item, evidence):
    """DG-33: (the highest level a motion finding's evidence can hold, whether it states an easing curve, the evidence
    refs that name no capture class)."""
    curve = text_value(item.get("curve")) or CURVE_RE.search(str(item.get("claim") or "")) is not None
    best, unclassed = "claimed", []
    for e in evidence:
        cls = e.get("class")
        if not isinstance(cls, str) or cls not in CLASS_CEILING:
            unclassed.append(str(e.get("ref")))
            continue
        ceiling = CURVE_CEILING.get(cls, "claimed") if curve else CLASS_CEILING[cls]
        best = max(best, ceiling, key=LEVELS.index)
    return best, curve, unclassed


def comparison_findings(entry, status):
    """DG-36: a build-against-reference comparison counts only when both runs finished every step; a run that stopped
    early makes the entry blocked at the step where it stopped, never passed or failed."""
    out = []
    if status == "blocked" and not (number(entry.get("step")) and entry["step"] >= 1):
        out.append(finding("report", "blocked-without-step", "DG-36", "an early stop is blocked at a step: name it in step"))
    steps = entry.get("steps")
    completed = entry.get("completed") if isinstance(entry.get("completed"), dict) else {}
    finished = number(steps) and steps >= 1 and all(completed.get(side) == steps for side in ("build", "reference"))
    if status in ("passed", "failed") and not finished:
        out.append(finding("report", "comparison-incomplete", "DG-36", "a comparison counts only when both runs finish "
                           "every step (steps, and completed for build and reference); compare the steps it has and the "
                           "result is blocked at the first step a run did not finish"))
    return out


REMOVED_EFFECTS = ("box-shadow", "text-shadow", "filter", "backdrop-filter", "animation", "transition")
READY = ("flag", "fonts-network", "timeout")


def effects_findings(entry, status):
    """DG-38: an effects-off check that passed or failed names the effects its injected stylesheet removed; a run that
    skipped the injection measured the page with its effects on."""
    if status not in ("passed", "failed"):
        return []
    removed = entry.get("removed") if isinstance(entry.get("removed"), list) else []
    missing_effects = [effect for effect in REMOVED_EFFECTS if effect not in removed]
    if missing_effects:
        return [finding("report", "effects-not-removed", "DG-38", "an effects-off check removes %s before measuring; "
                        "not removed: %s" % (", ".join(REMOVED_EFFECTS), ", ".join(missing_effects)))]
    return []


def readiness_findings(captures, entry):
    """DG-41: each capture records how readiness was reached (the ready flag, else fonts loaded and network idle) and
    its console errors. A wait that timed out blocks the capture and console errors fail it: neither is ever valid,
    and a reported DG-41 status follows its captures (blocked, then failed, then passed)."""
    out, expected = [], "passed" if captures else "unrecorded"
    for item in captures:
        where = "captures.%s" % item.get("id")
        ready, count = item.get("ready"), item.get("console_errors")
        errors = number(count) and count > 0
        if ready is not None and ready not in READY:
            out.append(finding("report", "bad-value", where + ".ready", "ready is one of " + ", ".join(READY)))
        if ready == "timeout" and item.get("valid") is not False:
            out.append(finding("report", "capture-not-ready", where, "the readiness wait timed out, so the capture is "
                               "blocked and invalid: it is never taken anyway"))
        if errors and item.get("valid") is not False:
            out.append(finding("report", "capture-console-errors", where, "the page logged %s console error(s), so the "
                               "capture failed" % count))
        if ready == "timeout":
            expected = "blocked"
        elif errors and expected != "blocked":
            expected = "failed"
        elif (ready not in READY or not number(count)) and expected == "passed":
            expected = "unrecorded"
    status = entry.get("status") if isinstance(entry, dict) else None
    if status in ("passed", "failed") and status != expected:
        out.append(finding("report", "readiness-status", "DG-41", "the captures make DG-41 %s, not %s: a timed-out wait "
                           "is blocked, a console error failed, and passed needs every capture's ready and "
                           "console_errors recorded" % (expected, status)))
    return out


SHA256_RE = re.compile(r"[0-9a-f]{64}")


def delivery_findings(data, captures):
    """DG-45: when the report names the delivered file (path and sha256), at least one capture marked final names
    that sha256 as its source_sha256. The live render is not what ships; an encoder or build step can change it."""
    if "delivered" not in data:
        return []
    delivered = data["delivered"] if isinstance(data["delivered"], dict) else {}
    digest = delivered.get("sha256")
    if not (text_value(delivered.get("path")) and SHA256_RE.fullmatch(str(digest))):
        return [finding("report", "bad-value", "delivered", "delivered names the shipped file's path and its sha256 "
                        "(64 lowercase hex characters)")]
    finals = [c for c in captures if c.get("final") is True]
    if not any(c.get("source_sha256") == digest for c in finals):
        return [finding("report", "capture-not-delivered", "captures", "the final review reads the delivered file "
                        "(%s): no capture marked final names its sha256 as source_sha256, so the review saw the live "
                        "render, not what ships" % delivered.get("path"))]
    return []


def text_hold_findings(beats, thresholds_path):
    """DG-46: each declared text beat is held at least text-hold-s: base, plus per_word for each word beyond
    free_words. The thresholds load only when the report declares beats."""
    if not beats:
        return []
    hold = need(load_thresholds(thresholds_path), "text-hold-s", "per-word")
    out = []
    for number_, beat in enumerate(beats, start=1):
        beat = beat if isinstance(beat, dict) else {}
        where = "text_beats.%s" % (beat.get("id") or number_)
        if not (text_value(beat.get("text")) and number(beat.get("held_s"))):
            out.append(finding("report", "bad-value", where, "a text beat gives its text and held_s (seconds on screen)"))
            continue
        words = len(beat["text"].split())
        needed = hold_needed(words, hold)
        if beat["held_s"] + 1e-9 < needed:
            out.append(finding("report", "text-hold-short", where, "%d words need %s s on screen (text-hold-s: %s s, plus "
                               "%s s per word beyond %d); held %s s" % (words, fmt(needed), fmt(hold["base"]),
                                                                       fmt(hold["per_word"]), hold["free_words"],
                                                                       fmt(beat["held_s"]))))
    return out


def cmd_report(args):
    data, _ = load_json(read_text(args.file), str(args.file))
    if not isinstance(data, dict) or data.get("format") != "westack-design-report-1":
        raise Unreadable("%s is not a westack-design-report-1 report" % args.file)
    findings, dropped, lowered = [], [], []
    mode = data.get("mode")
    if mode not in MODES:
        findings.append(finding("report", "bad-value", "mode", "mode is one of " + ", ".join(MODES)))
    browser = data.get("browser") if text_value(data.get("browser")) else "none"
    runtime = {r.get("id"): r for r in data.get("runtime", []) if isinstance(r, dict)}
    not_run_any = False
    for check_id in RUNTIME_IDS:
        entry = runtime.get(check_id)
        if entry is None:
            if check_id in REQUIRED_RUNTIME:
                findings.append(finding("report", "runtime-unreported", check_id, "say what happened to %s: passed, "
                                        "failed, blocked or not-run (with no browser it is not-run)" % check_id))
                not_run_any = True
            continue
        status = (entry or {}).get("status")
        if status not in RUNTIME_STATUS:
            findings.append(finding("report", "bad-value", check_id, "status is one of " + ", ".join(RUNTIME_STATUS)))
        if browser == "none" and status != "not-run":
            findings.append(finding("report", "runtime-without-browser", check_id, "%s needs a browser; with none it is "
                                    "not-run, never %s" % (check_id, status)))
        elif status in ("passed", "failed") and not (entry or {}).get("evidence"):
            findings.append(finding("report", "runtime-no-evidence", check_id, "a %s browser check names its evidence" % status))
        if check_id == "DG-36" and isinstance(entry, dict):
            findings += comparison_findings(entry, status)
        if check_id == "DG-38" and isinstance(entry, dict):
            findings += effects_findings(entry, status)
        not_run_any = not_run_any or status in ("not-run", "blocked")
    captures = [c for c in data.get("captures", []) if isinstance(c, dict)]
    findings += readiness_findings(captures, runtime.get("DG-41"))
    findings += delivery_findings(data, captures)
    beats = data.get("text_beats")
    findings += text_hold_findings(beats if isinstance(beats, list) else [beats] if beats else [], args.thresholds)
    invalid_captures = [c for c in captures if c.get("valid") is False]
    findings_list = [f for f in data.get("findings", []) if isinstance(f, dict)]
    disposition = data.get("disposition")
    if invalid_captures and (findings_list or disposition != "recapture"):
        findings.append(finding("report", "recapture-with-findings", "captures", "a blank, wrong or missing capture means "
                                "recapture with no findings: %s" % ", ".join(str(c.get("id")) for c in invalid_captures)))
    first = str(data.get("first_line") or "")
    degraded = bool(invalid_captures) or not_run_any or (browser == "none" and mode in ("critique", "redesign"))
    if not (first.startswith("Method:") or first.startswith("DEGRADED")):
        findings.append(finding("report", "first-line", "first_line", "the first line is a method line (Method: ...) "
                                "or a DEGRADED banner"))
    elif degraded and not first.startswith("DEGRADED"):
        findings.append(finding("report", "banner-missing", "first_line", "a phase did not run, so the first line is a "
                                "DEGRADED banner naming it"))
    phases = data.get("phases") if isinstance(data.get("phases"), list) else []
    if "judgment" in phases and "detectors" in phases:
        if phases.index("detectors") < phases.index("judgment"):
            findings.append(finding("report", "detector-first", "phases", "write the design judgment before reading "
                                    "detector output"))
    elif mode == "critique":
        findings.append(finding("report", "phases-unrecorded", "phases", "record the order: judgment, then detectors"))
    for item in findings_list:
        where = "findings.%s" % item.get("id")
        kind, level = item.get("kind"), item.get("level")
        evidence = [e for e in item.get("evidence", []) if isinstance(e, dict) and text_value(e.get("ref"))]
        kinds = {e.get("kind") for e in evidence}
        rendered = bool(kinds & set(RENDERED_EVIDENCE))
        missing_proofs = [p for p in ("rule", "path", "correction") if not text_value(item.get(p))]
        reason = None
        if not evidence:
            reason = finding("report", "no-evidence", where, "a finding with no screenshot, console line, measurement "
                             "or source receipt is dropped")
        elif kinds == {"score"}:
            reason = finding("report", "score-as-evidence", where, "a score is triage, never evidence")
        elif missing_proofs:
            reason = finding("report", "unproven", where, "a finding needs a binding rule, the path from owner to surface "
                             "and one correction; missing: " + ", ".join(missing_proofs))
        elif (item.get("rendered") or {}).get("agrees") is False:
            reason = finding("report", "contradicted-not-dropped", where, "the rendered check contradicts this static "
                             "finding: drop it and say why (DG-29)")
        elif kind in NUMERIC_KINDS and kinds <= {"screenshot"}:
            reason = finding("report", "numeric-from-screenshot", where, "widths, sizes, spacing and contrast come from "
                             "computed styles, bounding boxes or pixel samples, or the declared source, never from a "
                             "model reading a screenshot (DG-27)")
        elif kind == "motion" and "recording" not in kinds:
            reason = finding("report", "motion-from-stills", where, "motion evidence is recorded motion (frame samples, "
                             "animation records or style mutations under real input); stills do not show it (DG-26)")
        elif kind in RENDERED_KINDS and level != "claimed" and not rendered:
            reason = finding("report", "level-too-high", where, "%s from source alone stays claimed" % kind)
        elif level == "observed" and not rendered:
            reason = finding("report", "level-too-high", where, "observed needs rendered or user evidence")
        elif level not in LEVELS:
            reason = finding("report", "bad-value", where, "level is one of " + ", ".join(LEVELS))
        if reason:
            findings.append(reason)
            dropped.append(item.get("id"))
        elif kind == "motion":
            ceiling, curve, unclassed = capture_ceiling(item, evidence)
            if unclassed:
                findings.append(finding("report", "capture-class-missing", where, "each motion evidence item names its "
                                        "capture class (%s); none on %s" % (", ".join(CLASS_CEILING), ", ".join(unclassed))))
            if LEVELS.index(level) > LEVELS.index(ceiling):
                findings.append(finding("report", "level-above-capture", where, "its evidence holds it at %s, not %s%s "
                                        "(DG-33)" % (ceiling, level, ": an easing curve stands as observed only on exact "
                                                     "evidence and as present on recovered source; read off samples it "
                                                     "stays claimed" if curve else "")))
                lowered.append({"id": item.get("id"), "from": level, "to": ceiling})
    environment = data.get("environment") if isinstance(data.get("environment"), dict) else None
    listed = {p.get("name") for p in data.get("proposals", []) if isinstance(p, dict) and p.get("kind") == "baseline"}
    for baseline in (b for b in data.get("baselines", []) if isinstance(b, dict)):
        where = "baselines.%s" % baseline.get("file")
        if baseline.get("changed") is True and baseline.get("file") not in listed:
            findings.append(finding("report", "baseline-unlisted", where, "a changed screenshot baseline is a design "
                                    "decision: list it under proposals for the user (DG-31)"))
        theirs = baseline.get("environment") if isinstance(baseline.get("environment"), dict) else None
        if theirs is None or environment is None:
            findings.append(finding("report", "baseline-environment-unknown", where, "record the OS, browser, headless "
                                    "mode and device pixel ratio of the baseline and of this run"))
            continue
        differs = [key for key in ENVIRONMENT_KEYS if theirs.get(key) != environment.get(key)]
        if differs:
            findings.append(finding("report", "baseline-environment-mismatch", where, "the baseline came from another "
                                    "environment (%s differ): refuse the comparison" % ", ".join(differs)))
    score_line = check_scores(data, findings)
    extra = {"dropped": dropped, "lowered": lowered}
    if score_line:
        extra["score_line"] = score_line
    return report("report", overall_status(findings), findings, **extra)


# ---- variants (key-free design exploration) -----------------------------------------------------------------------

VARIANTS_FORMAT = "westack-design-variants-1"
REMOTE_ASSET = re.compile(r"""(?:src|href|url)\s*[=(]\s*["']?\s*https?://""", re.I)


def cmd_variants(args):
    folder = pathlib.Path(args.folder)
    manifest = folder / "variants.json"
    data, dupes = load_json(read_text(manifest), str(manifest))
    where, findings, proposals = str(manifest), [], []
    if dupes:
        findings.append(finding("variants", "duplicate-key", where, "keys repeat: %s" % ", ".join(sorted(set(dupes)))))

    def add(code, message, at=None):
        findings.append(finding("variants", code, at or where, message))
    if data.get("format") != VARIANTS_FORMAT:
        add("format", "format must be " + VARIANTS_FORMAT)
    if data.get("generator") != "html":
        add("generator", "variants are hand-built HTML (generator \"html\"); a generated-image service is a paid "
                         "element this skill never calls")
    variants = data.get("variants") or []
    ids = [v.get("id") for v in variants]
    if len(variants) < 2:
        add("too-few", "a board needs at least two variants to choose between")
    if len(set(ids)) != len(ids):
        add("duplicate-id", "variant ids repeat")
    for v in variants:
        label = "variant %s" % v.get("id")
        page = folder / str(v.get("file", ""))
        if not v.get("file") or not page.is_file():
            add("missing-file", "%s: its HTML file is missing" % label)
        elif REMOTE_ASSET.search(read_text(page)):
            add("remote-asset", "%s: loads an asset from the network; a variant is self-contained" % label, str(page))
        if not str(v.get("direction", "")).strip():
            add("no-direction", "%s: name the one direction it takes" % label)
        if not str(v.get("viewport", "")).strip():
            add("no-viewport", "%s: record the viewport of its screenshot" % label)
        shot = folder / str(v.get("screenshot", ""))
        if not v.get("screenshot") or not shot.is_file():
            add("missing-screenshot", "%s: its screenshot is missing" % label)
        elif hashlib.sha256(shot.read_bytes()).hexdigest() != v.get("screenshot_sha256"):
            add("screenshot-hash", "%s: the screenshot's SHA-256 does not match the manifest" % label, str(shot))
    if len({str(v.get("viewport")) for v in variants}) > 1:
        add("mixed-viewports", "screenshots compared on one board share one viewport")
    board = folder / str(data.get("board", "board.html"))
    if not board.is_file():
        add("missing-board", "the comparison board is missing")
    else:
        text = read_text(board)
        for v in variants:
            if str(v.get("screenshot") or "\0") not in text and str(v.get("file") or "\0") not in text:
                add("board-incomplete", "the board does not show variant %s" % v.get("id"), str(board))
    feedback = data.get("feedback")
    if feedback:
        if feedback.get("chosen") not in ids:
            add("chosen-unknown", "the chosen variant is not on the board")
        if not str(feedback.get("reasons", "")).strip():
            add("no-reasons", "record the user's reasons for the choice, in their words")
        for note in feedback.get("taste") or []:
            proposals.append(finding("variants", "taste-proposal", where,
                                     "a taste note for the design record, for the user to accept: %s" % note))
    return report("variants", overall_status(findings, proposals), findings, proposals=proposals,
                  variants=len(variants), feedback="recorded" if feedback else "pending")


# ---- motion export -------------------------------------------------------------------------------------------------

MOTION_FORMAT = "westack-design-motion-1"
SEAM_TOLERANCE = 0.005   # the share of pixels allowed to differ between the loop's first and last frames
DURATION_TOLERANCE = 0.25  # the recording may run this share short of period x loops (encoder start-up)


def mp4_boxes(data, start, end):
    i = start
    while i + 8 <= end:
        size, kind = struct.unpack(">I4s", data[i:i + 8])
        header = 8
        if size == 1:
            if i + 16 > end:
                raise Unreadable("an MP4 box header is cut short")
            size, header = struct.unpack(">Q", data[i + 8:i + 16])[0], 16
        elif size == 0:
            size = end - i
        if size < header or i + size > end:
            raise Unreadable("an MP4 box runs past its parent")
        yield kind.decode("latin-1"), i + header, i + size
        i += size


def mp4_child(data, start, end, path):
    for name in path:
        for kind, s, e in mp4_boxes(data, start, end):
            if kind == name:
                start, end = s, e
                break
        else:
            return None
    return start, end


def _mp4_time(data, s):
    """(timescale, duration) from an mvhd or mdhd payload."""
    if data[s] == 1:
        return struct.unpack(">IQ", data[s + 20:s + 32])
    return struct.unpack(">II", data[s + 12:s + 20])


def mp4_info(data):
    """Duration, and the video track's frame count, size and rate, from the file's boxes (plain or fragmented)."""
    moov = mp4_child(data, 0, len(data), ["moov"])
    if not moov:
        raise Unreadable("no moov box: not an MP4 this reader understands")
    mvhd = mp4_child(data, *moov, ["mvhd"])
    scale, dur = _mp4_time(data, mvhd[0]) if mvhd else (0, 0)
    video = None
    for kind, s, e in mp4_boxes(data, *moov):
        if kind != "trak":
            continue
        hdlr = mp4_child(data, s, e, ["mdia", "hdlr"])
        if not hdlr or data[hdlr[0] + 8:hdlr[0] + 12] != b"vide":
            continue
        tkhd = mp4_child(data, s, e, ["tkhd"])
        width, height = (struct.unpack(">II", data[tkhd[1] - 8:tkhd[1]]) if tkhd else (0, 0))
        mdhd = mp4_child(data, s, e, ["mdia", "mdhd"])
        tscale, tdur = _mp4_time(data, mdhd[0]) if mdhd else (0, 0)
        frames = 0
        stts = mp4_child(data, s, e, ["mdia", "minf", "stbl", "stts"])
        if stts:
            count = struct.unpack(">I", data[stts[0] + 4:stts[0] + 8])[0]
            for k in range(count):
                frames += struct.unpack(">I", data[stts[0] + 8 + 8 * k:stts[0] + 12 + 8 * k])[0]
        video = {"frames": frames, "width": width >> 16, "height": height >> 16, "timescale": tscale,
                 "duration_s": tdur / tscale if tscale else 0.0}
        break
    if video is None:
        raise Unreadable("no video track in the MP4")
    trex = mp4_child(data, *moov, ["mvex", "trex"])
    track_default = struct.unpack(">I", data[trex[0] + 12:trex[0] + 16])[0] if trex else 0
    fragment_frames, fragment_ticks = 0, 0
    for kind, s, e in mp4_boxes(data, 0, len(data)):
        if kind != "moof":
            continue
        for k2, s2, e2 in mp4_boxes(data, s, e):
            if k2 != "traf":
                continue
            default = track_default
            for k3, s3, e3 in mp4_boxes(data, s2, e2):
                if k3 == "tfhd":
                    flags, at = int.from_bytes(data[s3 + 1:s3 + 4], "big"), s3 + 8
                    at += 8 if flags & 0x01 else 0
                    at += 4 if flags & 0x02 else 0
                    if flags & 0x08:
                        default = struct.unpack(">I", data[at:at + 4])[0]
                elif k3 == "trun":
                    flags = int.from_bytes(data[s3 + 1:s3 + 4], "big")
                    count = struct.unpack(">I", data[s3 + 4:s3 + 8])[0]
                    fragment_frames += count
                    at = s3 + 8 + (4 if flags & 0x01 else 0) + (4 if flags & 0x04 else 0)
                    per = 4 * sum(1 for bit in (0x100, 0x200, 0x400, 0x800) if flags & bit)
                    if flags & 0x100:
                        fragment_ticks += sum(struct.unpack(">I", data[at + per * n:at + per * n + 4])[0]
                                              for n in range(count))
                    else:
                        fragment_ticks += default * count
    video["frames"] += fragment_frames
    video["fragmented"] = bool(fragment_frames)
    if fragment_ticks and video["timescale"]:
        video["duration_s"] += fragment_ticks / video["timescale"]
    duration = max(dur / scale if scale and dur else 0.0, video["duration_s"])
    video["fps"] = round(video["frames"] / duration, 2) if duration else None
    return {"duration_s": round(duration, 3), "video": video}


def png_pixels(data):
    """(width, height, channels, rows) for an 8-bit RGB or RGBA PNG, decoded with zlib and the five row filters."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise Unreadable("not a PNG")
    i, idat, ihdr = 8, [], None
    while i + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[i:i + 8])
        body = data[i + 8:i + 8 + length]
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
        i += 12 + length
    if not ihdr:
        raise Unreadable("a PNG without IHDR")
    width, height, depth, ctype, _, _, interlace = ihdr
    channels = {2: 3, 6: 4}.get(ctype)
    if depth != 8 or channels is None or interlace:
        raise Unreadable("only 8-bit, non-interlaced RGB or RGBA PNGs are compared")
    raw = zlib.decompress(b"".join(idat))
    stride, rows, prev, pos = width * channels, [], bytearray(width * channels), 0
    for _ in range(height):
        kind, line = raw[pos], bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b, c = prev[x], prev[x - channels] if x >= channels else 0
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return width, height, channels, rows


def frame_difference(first, last):
    """The share of pixels that differ between two decoded frames of one size."""
    w1, h1, c1, rows1 = first
    w2, h2, c2, rows2 = last
    if (w1, h1) != (w2, h2):
        return 1.0
    differ = 0
    for r1, r2 in zip(rows1, rows2):
        for x in range(w1):
            if r1[x * c1:x * c1 + 3] != r2[x * c2:x * c2 + 3]:
                differ += 1
    return differ / float(w1 * h1) if w1 * h1 else 1.0


def gif_loops(data):
    """True when a GIF carries the NETSCAPE2.0 application extension that makes it repeat."""
    return data[:6] in (b"GIF87a", b"GIF89a") and b"NETSCAPE2.0" in data[:4096]


def cmd_motion_export(args):
    folder = pathlib.Path(args.folder)
    manifest = folder / "motion.json"
    data, dupes = load_json(read_text(manifest), str(manifest))
    where, findings, info = str(manifest), [], {}

    def add(code, message, at=None):
        findings.append(finding("motion-export", code, at or where, message))
    if dupes:
        add("duplicate-key", "keys repeat: %s" % ", ".join(sorted(set(dupes))))
    if data.get("format") != MOTION_FORMAT:
        add("format", "format must be " + MOTION_FORMAT)
    approved = (data.get("design") or {}).get("approved") or {}
    if not str(approved.get("by", "")).strip() or not str(approved.get("said", "")).strip():
        add("not-approved", "export only an approved design: record who approved it and their words")
    loop = data.get("loop") or {}
    period, loops = loop.get("period_s"), loop.get("loops", 1)
    if not isinstance(period, (int, float)) or period <= 0 or not isinstance(loops, int) or loops < 1:
        add("no-period", "loop.period_s (seconds per cycle) and loop.loops (cycles recorded) are required")
        period = None
    if not str(data.get("reduced_motion", "")).strip():
        add("no-reduced-motion", "say what a viewer who prefers reduced motion gets (the motion policy)")
    video = data.get("video") or {}
    mp4 = folder / str(video.get("file", ""))
    if not video.get("file") or not mp4.is_file():
        add("missing-video", "the MP4 is missing")
    else:
        blob = mp4.read_bytes()
        if hashlib.sha256(blob).hexdigest() != video.get("sha256"):
            add("video-hash", "the MP4's SHA-256 does not match the record", str(mp4))
        try:
            info = mp4_info(blob)
        except (Unreadable, struct.error) as exc:
            add("video-unreadable", str(exc), str(mp4))
        else:
            if info["video"]["frames"] < 2:
                add("too-few-frames", "the video holds fewer than two frames", str(mp4))
            if period and info["duration_s"] < period * loops * (1 - DURATION_TOLERANCE):
                add("too-short", "%.2f s recorded for %d cycle(s) of %.2f s" % (info["duration_s"], loops, period), str(mp4))
    gif = data.get("gif")
    if gif:
        g = folder / str(gif.get("file", ""))
        if not g.is_file():
            add("missing-gif", "the GIF is missing")
        elif not gif_loops(g.read_bytes()):
            add("gif-not-looping", "the GIF does not carry a repeat (NETSCAPE2.0) block", str(g))
    frames = data.get("frames") or {}
    if frames.get("method") not in ("seek", "decoded"):
        add("frame-method", "frames.method says how the frames were taken: seek (the animation set to 0 and to one "
                            "period) or decoded (from the video)")
    first, last = folder / str(frames.get("first", "")), folder / str(frames.get("last", ""))
    if not frames.get("first") or not frames.get("last") or not first.is_file() or not last.is_file():
        add("missing-frames", "the loop's first and last frames are missing")
    else:
        try:
            diff = frame_difference(png_pixels(first.read_bytes()), png_pixels(last.read_bytes()))
        except (Unreadable, zlib.error, struct.error, IndexError) as exc:
            add("frames-unreadable", str(exc))
        else:
            info["seam_difference"] = round(diff, 5)
            if diff > SEAM_TOLERANCE:
                add("loop-seam", "the last frame differs from the first in %.2f%% of pixels: the loop jumps" % (diff * 100))
    return report("motion-export", overall_status(findings), findings, **info)


# ---- main ----------------------------------------------------------------------------------------------------------

COMMANDS = {"tokens": cmd_tokens, "contrast": cmd_contrast, "rules": cmd_rules, "waivers": cmd_waivers,
            "inventory": cmd_inventory, "record": cmd_record, "report": cmd_report, "variants": cmd_variants,
            "motion-export": cmd_motion_export}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="designcheck.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--rules", default=str(DEFAULT_RULES), help="the rules file")
        p.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS), help="the thresholds file")
        return p
    t = common(sub.add_parser("tokens", help="raw values against the theme, or the token-file preflight"))
    t.add_argument("src", nargs="+")
    t.add_argument("--theme")
    t.add_argument("--token-file", action="append", default=[])
    t.add_argument("--baseline")
    t.add_argument("--writing")
    t.add_argument("--replace-authorised")
    common(sub.add_parser("contrast", help="WCAG ratios of the record's colour pairs")).add_argument("record")
    r = common(sub.add_parser("rules", help="the rules file over source, with the brief"))
    r.add_argument("src", nargs="+")
    r.add_argument("--brief", required=True)
    r.add_argument("--waivers")
    r.add_argument("--record", help="the design record whose motion policy the policy rules check against")
    r.add_argument("--control", action="append", default=[], help="a human-made control page or folder (DG-28)")
    common(sub.add_parser("waivers", help="check a waiver file")).add_argument("file")
    i = common(sub.add_parser("inventory", help="wiring before and after a redesign"))
    i.add_argument("before")
    i.add_argument("after")
    i.add_argument("--dropped")
    i.add_argument("--depth", choices=("full", "restyle", "polish"), default="full")
    d = common(sub.add_parser("record", help="the design record"))
    d.add_argument("file")
    d.add_argument("--derived", action="append", default=[])
    d.add_argument("--built", action="append", default=[])
    d.add_argument("--baseline")
    d.add_argument("--emit", choices=("css", "json"))
    common(sub.add_parser("report", help="a critique report")).add_argument("file")
    common(sub.add_parser("variants", help="a variants board folder")).add_argument("folder")
    common(sub.add_parser("motion-export", help="a motion-export folder: MP4, frames, record")).add_argument("folder")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    if args.command == "tokens" and not (args.theme or args.writing):
        sys.stderr.write("tokens needs --theme THEME or --writing NEW_TOKEN_FILE\n")
        return 64
    try:
        result = COMMANDS[args.command](args)
    except Unreadable as exc:
        result = report(args.command, "unreadable", error=str(exc))
    except NotRun as exc:
        result = report(args.command, "not-run", error=str(exc))
    if isinstance(result, str):
        sys.stdout.write(result)
        return 0
    sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    return EXIT[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
