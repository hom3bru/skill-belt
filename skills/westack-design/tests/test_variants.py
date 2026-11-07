"""designcheck.py variants: a key-free variants board (HTML variants, screenshots, a board, the user's choice).

Run from the repo root:  python -B -m unittest discover -s skills/westack-design/tests
"""
import hashlib
import json
import pathlib
import tempfile
import unittest

from test_designcheck import broken, dc, off, run

PNG = b"\x89PNG\r\n\x1a\n" + b"fixture-bytes"


def board(tmp, n=3, generator="html", feedback=None, remote=False, board_lists=None, shots=None):
    folder = pathlib.Path(tmp)
    variants = []
    for i in range(1, n + 1):
        html = "<!doctype html><title>v%d</title><h1>Variant %d</h1>" % (i, i)
        if remote and i == 1:
            html += '<img src="https://cdn.example.test/hero.jpg">'
        (folder / ("v%d.html" % i)).write_text(html, encoding="utf-8")
        data = PNG + bytes([i])
        (folder / ("v%d.png" % i)).write_bytes(data)
        variants.append({"id": "v%d" % i, "file": "v%d.html" % i, "screenshot": "v%d.png" % i,
                         "screenshot_sha256": hashlib.sha256(data).hexdigest(), "viewport": "1280x800",
                         "direction": "direction %d" % i})
    if shots:
        shots(variants)
    listed = board_lists if board_lists is not None else [v["screenshot"] for v in variants]
    (folder / "board.html").write_text("".join('<img src="%s">' % s for s in listed), encoding="utf-8")
    manifest = {"format": "westack-design-variants-1", "surface": "pricing page", "generator": generator,
                "variants": variants, "board": "board.html"}
    if feedback is not None:
        manifest["feedback"] = feedback
    (folder / "variants.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def codes(result):
    return {f["code"] for f in result["findings"]}


class VariantsTests(unittest.TestCase):
    def check(self, module=dc, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            return run(module, "variants", board(tmp, **kw))

    def test_a_good_board_without_feedback_is_clean(self):
        code, result = self.check()
        self.assertEqual((code, result["status"], result["feedback"], result["variants"]), (0, "clean", "pending", 3))

    def test_feedback_with_taste_notes_becomes_proposals(self):
        code, result = self.check(feedback={"chosen": "v2", "reasons": "calmer, the price is easier to find",
                                            "taste": ["prefers one accent colour"]})
        self.assertEqual((code, result["status"], len(result["proposals"])), (1, "proposals", 1))

    def test_a_paid_image_generator_is_refused(self):
        self.assertIn("generator", codes(self.check(generator="openai gpt-image")[1]))

    def test_shape_problems_are_named(self):
        self.assertIn("too-few", codes(self.check(n=1)[1]))
        self.assertIn("remote-asset", codes(self.check(remote=True)[1]))
        self.assertIn("board-incomplete", codes(self.check(board_lists=["v1.png", "v2.png"])[1]))
        self.assertIn("chosen-unknown", codes(self.check(feedback={"chosen": "v9", "reasons": "x"})[1]))

        def tamper(variants):
            variants[0]["screenshot_sha256"] = "0" * 64
            variants[1]["viewport"] = "375x812"
        self.assertTrue({"screenshot-hash", "mixed-viewports"} <= codes(self.check(shots=tamper)[1]))

    def test_the_controls_a_copy_without_the_board_or_generator_check_misses_them(self):
        no_board = broken(off("str(v.get(\"screenshot\") or \"\\0\") not in text and str(v.get(\"file\") or \"\\0\") not in text"))
        self.assertNotIn("board-incomplete", codes(self.check(module=no_board, board_lists=["v1.png"])[1]))
        no_generator = broken(off("data.get(\"generator\") != \"html\""))
        self.assertNotIn("generator", codes(self.check(module=no_generator, generator="openai")[1]))


if __name__ == "__main__":
    unittest.main()
