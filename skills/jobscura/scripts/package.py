"""Build a deterministic ZIP from the hash-pinned public inventory only."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = "package-files.json"
LOCAL_OUTPUT = ("__pycache__",)
EVAL_RESULTS = ("evals", "results")


def declared_version(root=ROOT):
    """The toolkit version is declared once, in SKILL.md metadata."""
    text = (Path(root) / "SKILL.md").read_text(encoding="utf-8")
    found = re.search(r'^\s+version:\s*"(\d+\.\d+\.\d+)"\s*$', text, re.M)
    if not found:
        raise ValueError("Toolkit version missing from SKILL.md metadata")
    return found.group(1)


def payload(root=ROOT):
    root = Path(root).resolve()
    expected = json.loads((root / INVENTORY).read_text(encoding="utf-8"))
    if expected.get("format") != "jobscura-public-files-1" or not isinstance(expected.get("files"), dict):
        raise ValueError("Invalid public inventory")
    actual = set()
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked package path")
        parts = path.relative_to(root).parts
        if any(p in LOCAL_OUTPUT for p in parts) or parts[:2] == EVAL_RESULTS:
            continue  # local caches and model-eval results are never packaged
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(expected["files"]) | {INVENTORY}:
        raise ValueError("Unexpected or missing files; public inventory does not match")
    result = {INVENTORY: (root / INVENTORY).read_bytes()}
    for name, digest in expected["files"].items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("Unsafe inventory path")
        if any(part in {".private", "private-context", "packets", ".git"} for part in path.parts):
            raise ValueError("Private package path")
        if path.name.startswith(".env") and path.name != ".env.example":
            raise ValueError("Private environment file")
        if path.name.endswith((".local.json", ".zip")) or path.name == "user-context.json" or path.parts[:2] == EVAL_RESULTS:
            raise ValueError("Private or generated file")
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Public file hash mismatch")
        result[name] = data
    version = declared_version(root)
    for name in ("plugin.json", ".codex-plugin/plugin.json"):
        metadata = json.loads(result[name])
        if metadata["name"] != "application-assistant-workflows" or metadata["version"] != version:
            raise ValueError("Plugin identity or version mismatch")
    return result


def build(output, root=ROOT):
    files = payload(root)
    output = Path(output).resolve()
    if output.is_relative_to(Path(root).resolve()):
        raise ValueError("Keep generated archives outside the toolkit")
    # Exclusive creation prevents overwriting an earlier result.
    with output.open("xb") as stream:
        with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = ZipInfo(name, date_time=(2026, 11, 2, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
    return {"status": "packaged", "files": len(files), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output), indent=2))
        return 0
    except (OSError, ValueError, KeyError):
        parser.exit(2, "Package blocked: verify public inventory, identity and output location.\n")


if __name__ == "__main__":
    raise SystemExit(main())
