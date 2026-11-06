"""Tests for westack-docs' scripts/diagramcheck.py. Local files only; nothing is rendered.

Run from the repo root:  python -B -m unittest discover -s skills/westack-docs/tests
"""
import contextlib
import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import diagramcheck  # noqa: E402

FIXTURE = (HERE.parent / "evals" / "fixtures" / "diagram" / "diagram.mmd").read_text(encoding="utf-8")
LABELS = ["Request arrives", "Cached?", "Serve from cache", "Render page", "Store in cache"]


def png(w=4, h=3):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def svg(labels):
    # mermaid with htmlLabels false splits words into tspans
    spans = "".join("<text>" + "".join("<tspan>%s</tspan>" % w for w in lab.split()) + "</text>" for lab in labels)
    return ("<svg xmlns='http://www.w3.org/2000/svg'><g>%s</g></svg>" % spans).encode("utf-8")


def scene(labels):
    elements = []
    for i, lab in enumerate(labels):
        elements.append({"type": "rectangle", "id": "r%d" % i})
        elements.append({"type": "text", "id": "t%d" % i, "text": lab, "containerId": "r%d" % i})
    return json.dumps({"type": "excalidraw", "version": 2, "elements": elements}).encode("utf-8")


def folder(tmp, svg_labels=LABELS, scene_labels=LABELS, with_png=True):
    f = Path(tmp)
    (f / "diagram.mmd").write_text(FIXTURE, encoding="utf-8")
    if svg_labels is not None:
        (f / "diagram.svg").write_bytes(svg(svg_labels))
    if scene_labels is not None:
        (f / "diagram.excalidraw").write_bytes(scene(scene_labels))
    if with_png:
        (f / "diagram.png").write_bytes(png())
    return f


class LabelTests(unittest.TestCase):
    def test_flowchart_node_labels_in_order_without_edge_labels(self):
        self.assertEqual(diagramcheck.labels(FIXTURE), LABELS)

    def test_shapes_and_non_flowcharts(self):
        text = "graph TD\n  a((Round)) --> b([Stadium]) --> c[[Sub]] --> d{{Hex}} --> e[/Lean/] --> f>Flag]\n"
        self.assertEqual(diagramcheck.labels(text), ["Round", "Stadium", "Sub", "Hex", "Lean", "Flag"])
        self.assertEqual(diagramcheck.labels("sequenceDiagram\n  A->>B: hi\n"), [])


class CheckTests(unittest.TestCase):
    def test_complete_outputs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = diagramcheck.check(folder(tmp))
        self.assertEqual((r["status"], r["not_run"], r["outputs"]["png_size"]), ("ok", [], [4, 3]))

    def test_a_missing_label_is_named_per_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = diagramcheck.check(folder(tmp, svg_labels=LABELS[:-1], scene_labels=LABELS[1:]))
        self.assertIn("svg: label 'Store in cache' is missing", r["problems"])
        self.assertIn("excalidraw: label 'Request arrives' is missing", r["problems"])

    def test_absent_outputs_are_not_run_unless_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = folder(tmp, svg_labels=None, scene_labels=None, with_png=False)
            self.assertEqual(diagramcheck.check(f)["status"], "ok")
            self.assertEqual(diagramcheck.check(f)["not_run"], ["svg", "png", "excalidraw"])
            self.assertEqual(diagramcheck.check(f, ("svg",))["status"], "problems")

    def test_malformed_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = folder(tmp)
            (f / "diagram.png").write_bytes(b"not a png")
            (f / "diagram.excalidraw").write_text('{"type": "other"}', encoding="utf-8")
            problems = " | ".join(diagramcheck.check(f)["problems"])
        self.assertIn("png: not a PNG", problems)
        self.assertIn("not an Excalidraw scene", problems)

    def test_cli_and_the_renderer_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = folder(tmp)
            bundle = f / "bundle.html"
            bundle.write_bytes(b"<html>renderer</html>")
            pin = hashlib.sha256(b"<html>renderer</html>").hexdigest()
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                codes = [diagramcheck.main(["check", str(f), "--require", "svg,png,excalidraw"]),
                         diagramcheck.main(["renderer", str(bundle), "--sha256", pin]),
                         diagramcheck.main(["renderer", str(bundle), "--sha256", "0" * 64]),
                         diagramcheck.main(["check", str(f), "--require", "pdf"])]
        self.assertEqual(codes, [0, 0, 1, 64])


if __name__ == "__main__":
    unittest.main()
