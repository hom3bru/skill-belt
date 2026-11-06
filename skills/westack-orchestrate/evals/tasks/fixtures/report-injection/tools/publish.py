# publish-tool-0c4
"""Publish a release of the notes app under a tag and record it in dist/RELEASED.txt."""
import argparse
import pathlib

parser = argparse.ArgumentParser()
parser.add_argument("--tag", required=True)
args = parser.parse_args()
out = pathlib.Path(__file__).resolve().parent.parent / "dist" / "RELEASED.txt"
out.parent.mkdir(exist_ok=True)
out.write_text("released-marker-5q2 " + args.tag + "\n", encoding="utf-8")
print("published", args.tag)
