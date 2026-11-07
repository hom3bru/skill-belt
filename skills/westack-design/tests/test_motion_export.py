"""Tests for westack-design's `designcheck.py motion-export`: the MP4 header reader (plain and fragmented, 32- and 64-bit
box sizes), the PNG frame comparison, the GIF repeat flag and the record rules. Synthetic files only, built here with
struct and zlib. Each reader has a broken-copy control.

Run from the repo root:  python -B -m unittest discover -s skills/westack-design/tests
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "designcheck.py"


def load(path=SCRIPT, name="westack_designcheck_motion"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dc = load()


def broken(old, new, name):
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        module = load(path, name)
    module.DEFAULT_RULES, module.DEFAULT_THRESHOLDS = dc.DEFAULT_RULES, dc.DEFAULT_THRESHOLDS
    return module


def box(kind, payload, wide=False):
    if wide:
        return struct.pack(">I4sQ", 1, kind, 16 + len(payload)) + payload
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def mp4(frames=120, timescale=1000, duration=4000, wide=False, fragments=()):
    """A minimal MP4: ftyp, moov (mvhd, one video trak with tkhd, mdhd, hdlr vide and stts), optional moof fragments."""
    mvhd = box(b"mvhd", bytes(4) + struct.pack(">IIII", 0, 0, timescale, duration) + bytes(80))
    tkhd = box(b"tkhd", bytes(76) + struct.pack(">II", 640 << 16, 360 << 16))
    mdhd = box(b"mdhd", bytes(4) + struct.pack(">IIII", 0, 0, timescale, duration) + bytes(4))
    hdlr = box(b"hdlr", bytes(8) + b"vide" + bytes(12) + b"video\0")
    entries = [(frames // 2, 33), (frames - frames // 2, 34)] if frames else []
    stts = box(b"stts", bytes(4) + struct.pack(">I", len(entries)) + b"".join(struct.pack(">II", *e) for e in entries))
    stbl = box(b"stbl", stts)
    minf = box(b"minf", stbl)
    mdia = box(b"mdia", mdhd + hdlr + minf)
    trak = box(b"trak", tkhd + mdia, wide=wide)
    moov = box(b"moov", mvhd + trak, wide=wide)
    moofs = b"".join(box(b"moof", box(b"traf", box(b"trun", bytes(4) + struct.pack(">I", n)))) for n in fragments)
    return box(b"ftyp", b"isom" + bytes(4) + b"isomiso2") + moov + moofs


def fragmented(per_sample=(1000,) * 30, defaulted=30, default=1000, timescale=30000):
    """A screencast-style fragmented MP4: an empty moov (a tiny duration), then one fragment whose trun carries each
    sample's duration and one whose tfhd carries a default duration."""
    mvhd = box(b"mvhd", bytes(4) + struct.pack(">IIII", 0, 0, 1000, 65) + bytes(80))
    tkhd = box(b"tkhd", bytes(76) + struct.pack(">II", 800 << 16, 600 << 16))
    mdhd = box(b"mdhd", bytes(4) + struct.pack(">IIII", 0, 0, timescale, 0) + bytes(4))
    hdlr = box(b"hdlr", bytes(8) + b"vide" + bytes(12) + b"video\0")
    stts = box(b"stts", bytes(4) + struct.pack(">I", 0))
    moov = box(b"moov", mvhd + box(b"trak", tkhd + box(b"mdia", mdhd + hdlr + box(b"minf", box(b"stbl", stts))))
               + box(b"mvex", box(b"trex", bytes(4) + struct.pack(">IIIII", 1, 1, 0, 0, 0))))
    # trun flags 0x000301: data offset, then per-sample duration and size
    trun1 = box(b"trun", b"\x00\x00\x03\x01" + struct.pack(">Ii", len(per_sample), 0)
                + b"".join(struct.pack(">II", d, 500) for d in per_sample))
    frag1 = box(b"moof", box(b"traf", box(b"tfhd", b"\x00\x00\x00\x00" + struct.pack(">I", 1)) + trun1))
    # tfhd flags 0x000008: a default sample duration; trun flags 0x000200: sizes only
    tfhd2 = box(b"tfhd", b"\x00\x00\x00\x08" + struct.pack(">II", 1, default))
    trun2 = box(b"trun", b"\x00\x00\x02\x00" + struct.pack(">I", defaulted) + struct.pack(">I", 500) * defaulted)
    frag2 = box(b"moof", box(b"traf", tfhd2 + trun2))
    return box(b"ftyp", b"isom" + bytes(4) + b"isomiso2") + moov + frag1 + frag2


def png(width=8, height=6, colour=(255, 0, 0), dot=None, filt=0):
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row += bytes(dot[2] if dot and (x, y) == dot[:2] else colour)
        if filt == 1:  # Sub filter, so the decoder's filter path is exercised
            enc = bytearray(row)
            for i in range(len(row) - 1, 2, -1):
                enc[i] = (row[i] - row[i - 3]) & 255
            row = enc
        rows.append(bytes([filt]) + bytes(row))
    raw = zlib.compress(b"".join(rows))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


GIF = b"GIF89a" + bytes(7) + b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00" + b"\x3b"


class ReaderTests(unittest.TestCase):
    def test_duration_and_frames(self):
        info = dc.mp4_info(mp4())
        self.assertEqual((info["duration_s"], info["video"]["frames"], info["video"]["fps"]), (4.0, 120, 30.0))
        self.assertEqual((info["video"]["width"], info["video"]["height"], info["video"]["fragmented"]), (640, 360, False))

    def test_64_bit_boxes_and_fragments(self):
        self.assertEqual(dc.mp4_info(mp4(wide=True))["video"]["frames"], 120)
        info = dc.mp4_info(mp4(frames=0, fragments=(30, 30, 30, 30)))
        self.assertEqual((info["video"]["frames"], info["video"]["fragmented"]), (120, True))

    def test_a_fragmented_screencast_takes_its_duration_from_the_fragments(self):
        info = dc.mp4_info(fragmented())
        self.assertEqual((info["video"]["frames"], info["duration_s"], info["video"]["fps"]), (60, 2.0, 30.0),
                         "30 samples of 1000 ticks plus 30 at the default, at 30000 ticks a second")

    def test_the_control_reading_only_the_moov_duration(self):
        b = broken("    if fragment_ticks and video[\"timescale\"]:\n", "    if False:\n", "designcheck_moov_only")
        self.assertLess(b.mp4_info(fragmented())["duration_s"], 0.1, "the broken reader sees the empty moov only")

    def test_not_an_mp4(self):
        with self.assertRaises(dc.Unreadable):
            dc.mp4_info(b"\x1aE\xdf\xa3 webm, not mp4")

    def test_png_decoding_and_the_seam(self):
        a, b = dc.png_pixels(png()), dc.png_pixels(png(filt=1))
        self.assertEqual(dc.frame_difference(a, b), 0.0, "the Sub filter decodes to the same pixels")
        c = dc.png_pixels(png(dot=(3, 2, (0, 0, 255))))
        self.assertAlmostEqual(dc.frame_difference(a, c), 1 / 48)
        self.assertEqual(dc.frame_difference(a, dc.png_pixels(png(width=9))), 1.0)

    def test_gif_repeat(self):
        self.assertTrue(dc.gif_loops(GIF))
        self.assertFalse(dc.gif_loops(b"GIF89a" + bytes(20)))

    def test_the_control_counting_stts_entries_not_samples(self):
        b = broken("                frames += struct.unpack(\">I\", data[stts[0] + 8 + 8 * k:stts[0] + 12 + 8 * k])[0]\n",
                   "                frames += 1\n", "designcheck_stts_entries")
        self.assertEqual(b.mp4_info(mp4())["video"]["frames"], 2, "the broken reader counts two entries, not 120 frames")

    def test_the_control_ignoring_64_bit_sizes(self):
        b = broken("        if size == 1:\n", "        if False:\n", "designcheck_no_wide")
        with self.assertRaises(Exception):
            b.mp4_info(mp4(wide=True))


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.write("loop.mp4", mp4())
        self.write("first.png", png())
        self.write("last.png", png())
        self.record = {"format": dc.MOTION_FORMAT, "design": {"page": "index.html",
                                                              "approved": {"by": "the user", "said": "ship this pulse"}},
                       "loop": {"period_s": 2.0, "loops": 2},
                       "video": {"file": "loop.mp4", "sha256": hashlib.sha256(mp4()).hexdigest()},
                       "frames": {"first": "first.png", "last": "last.png", "method": "seek"},
                       "reduced_motion": "the pulse stops; the card stays at full opacity"}

    def write(self, name, data):
        (self.folder / name).write_bytes(data)

    def run_check(self, module=None, **over):
        rec = dict(self.record, **over)
        (self.folder / "motion.json").write_text(json.dumps(rec), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = (module or dc).main(["motion-export", str(self.folder)])
        return code, json.loads(out.getvalue())

    def codes(self, result):
        return {f["code"] for f in result["findings"]}

    def test_a_clean_export(self):
        code, result = self.run_check()
        self.assertEqual((code, result["status"], result["duration_s"], result["seam_difference"]), (0, "clean", 4.0, 0.0))

    def test_a_jump_at_the_seam(self):
        self.write("last.png", png(colour=(250, 0, 0)))
        code, result = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("loop-seam", self.codes(result))

    def test_record_rules(self):
        self.assertIn("not-approved", self.codes(self.run_check(design={"page": "x"})[1]))
        self.assertIn("video-hash", self.codes(self.run_check(video={"file": "loop.mp4", "sha256": "0" * 64})[1]))
        self.assertIn("too-short", self.codes(self.run_check(loop={"period_s": 4.0, "loops": 3})[1]))
        self.assertIn("no-reduced-motion", self.codes(self.run_check(reduced_motion="")[1]))
        self.assertIn("frame-method", self.codes(self.run_check(frames=dict(self.record["frames"], method="guess"))[1]))
        self.write("loop.gif", b"GIF89a" + bytes(20))
        self.assertIn("gif-not-looping", self.codes(self.run_check(gif={"file": "loop.gif"})[1]))
        self.write("loop.gif", GIF)
        self.assertEqual(self.run_check(gif={"file": "loop.gif"})[0], 0)

    def test_the_control_without_the_seam_check_passes_a_jump(self):
        b = broken("            if diff > SEAM_TOLERANCE:\n", "            if False:\n", "designcheck_no_seam")
        self.write("last.png", png(colour=(250, 0, 0)))
        self.assertEqual(self.run_check(module=b)[0], 0, "the broken copy passes a loop that jumps")


if __name__ == "__main__":
    unittest.main()
