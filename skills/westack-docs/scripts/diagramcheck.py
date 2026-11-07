#!/usr/bin/env python3
"""westack-docs diagram helper. Standard library only; reads files, renders nothing, writes nothing.

  python diagramcheck.py labels   <diagram.mmd>                 the node labels of a mermaid flowchart
  python diagramcheck.py check    <folder> [--require svg,png,excalidraw]
                                  diagram.mmd beside diagram.svg / .png / .excalidraw: every label in each output
  python diagramcheck.py renderer <bundle.html> --sha256 HEX    the renderer bundle is the pinned one

Outputs that are absent are listed not-run (a failure only when --require names them). Labels are read from
flowchart node shapes only; other diagram types are checked for presence, not labels.
Exit codes: 0 ok; 1 a label is missing, an output is malformed, a required output is absent or the bundle differs;
64 usage or unreadable input.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import struct
import sys
from pathlib import Path
from typing import Optional

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 64
OUTPUTS = ("svg", "png", "excalidraw")
# ID followed by one of mermaid's node shapes; the label is the text inside.
SHAPES = [r"\(\(([^()]*)\)\)", r"\(\[([^\[\]]*)\]\)", r"\[\[([^\[\]]*)\]\]", r"\[\(([^()]*)\)\]", r"\{\{([^{}]*)\}\}",
          r"\[/([^/]*)/\]", r"\[\\([^\\]*)\\\]", r"\[([^\[\]]*)\]", r"\(([^()]*)\)", r"\{([^{}]*)\}", r">([^\]]*)\]"]
NODE = re.compile(r"(?<![\w-])([A-Za-z][\w-]*)\s*(?:" + "|".join(SHAPES) + r")")


class UsageError(Exception):
    pass


def read(path) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise UsageError(f"cannot read {path}: {exc}")


def labels(mmd: str) -> list:
    lines = [ln.strip() for ln in mmd.splitlines()]
    if not lines or not re.match(r"(?:flowchart|graph)\b", next((ln for ln in lines if ln and not ln.startswith("%%")), "")):
        return []
    found = []
    for line in lines:
        if line.startswith("%%"):
            continue
        line = re.sub(r"\|[^|]*\|", " ", line)  # edge labels are not nodes
        for m in NODE.finditer(line):
            text = next(g for g in m.groups()[1:] if g is not None).strip().strip('"')
            if text and text not in found:
                found.append(text)
    return found


def squash(text: str) -> str:
    return re.sub(r"\s+", "", html.unescape(text)).lower()


def svg_text(data: bytes) -> str:
    return re.sub(r"<[^>]+>", " ", data.decode("utf-8", errors="replace"))


def png_size(data: bytes) -> Optional[tuple]:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def check(folder: Path, require=()) -> dict:
    mmd_path = folder / "diagram.mmd"
    mmd = read(mmd_path).decode("utf-8", errors="replace")
    want = labels(mmd)
    problems, results, not_run = [], {}, []
    for kind in OUTPUTS:
        path = folder / f"diagram.{kind}"
        if not path.is_file():
            not_run.append(kind)
            if kind in require:
                problems.append(f"{kind}: required but absent")
            continue
        data = read(path)
        if kind == "svg":
            if b"<svg" not in data[:2000]:
                problems.append("svg: not an SVG document")
                continue
            body = squash(svg_text(data))
            missing = [lab for lab in want if squash(lab) not in body]
        elif kind == "png":
            size = png_size(data)
            if not size or 0 in size:
                problems.append("png: not a PNG with a size")
                continue
            results["png_size"] = list(size)
            missing = []
        else:
            try:
                scene = json.loads(data.decode("utf-8"))
            except ValueError:
                problems.append("excalidraw: not JSON")
                continue
            if scene.get("type") != "excalidraw" or not isinstance(scene.get("elements"), list):
                problems.append("excalidraw: not an Excalidraw scene (type excalidraw with elements)")
                continue
            texts = squash(" ".join(str(e.get("text") or e.get("originalText") or "") for e in scene["elements"]
                                    if e.get("type") == "text") + " " + json.dumps(
                [e.get("label", {}) for e in scene["elements"]]))
            missing = [lab for lab in want if squash(lab) not in texts]
            results["excalidraw_elements"] = len(scene["elements"])
        for lab in missing:
            problems.append(f"{kind}: label {lab!r} is missing")
        results[kind] = "checked"
    return {"labels": want, "outputs": results, "not_run": not_run, "problems": problems,
            "status": "ok" if not problems else "problems"}


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    usage = __doc__.split("\n\n")[1]
    try:
        if len(argv) == 2 and argv[0] == "labels":
            print(json.dumps(labels(read(argv[1]).decode("utf-8", errors="replace")), indent=2))
            return EXIT_OK
        if len(argv) in (2, 4) and argv[0] == "check":
            require = ()
            if len(argv) == 4:
                if argv[2] != "--require":
                    raise UsageError("check takes --require svg,png,excalidraw")
                require = tuple(x for x in argv[3].split(",") if x)
                if set(require) - set(OUTPUTS):
                    raise UsageError(f"--require names outputs other than {', '.join(OUTPUTS)}")
            result = check(Path(argv[1]), require)
            print(json.dumps(result, indent=2))
            return EXIT_OK if result["status"] == "ok" else EXIT_FAIL
        if len(argv) == 4 and argv[0] == "renderer" and argv[2] == "--sha256":
            actual = hashlib.sha256(read(argv[1])).hexdigest()
            ok = actual == argv[3].lower()
            print(json.dumps({"status": "pinned" if ok else "differs", "sha256": actual, "expected": argv[3].lower()}))
            return EXIT_OK if ok else EXIT_FAIL
        raise UsageError(f"unknown command or wrong arguments: {' '.join(argv)}")
    except UsageError as exc:
        print(f"diagramcheck.py: {exc}\n{usage}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
