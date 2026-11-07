# tracker-cli-8f0
"""The team tracker's command line, project SRCH. Issues are kept in tracker/store.json.

  python tools/tracker.py list
  python tools/tracker.py create --title TITLE [--body BODY] [--blocked-by SRCH-N ...]
"""
import argparse
import json
import pathlib

STORE = pathlib.Path(__file__).resolve().parent.parent / "tracker" / "store.json"


def load():
    return json.loads(STORE.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="team tracker, project SRCH")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    create = sub.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--body", default="")
    create.add_argument("--blocked-by", nargs="*", default=[])
    args = parser.parse_args(argv)
    data = load()
    if args.command == "list":
        for issue in data["issues"]:
            if issue["status"] == "open":
                print(issue["key"], issue["title"])
        return 0
    key = "%s-%d" % (data["project"], len(data["issues"]) + 1)
    data["issues"].append({"key": key, "title": args.title, "body": args.body, "blocked_by": args.blocked_by,
                           "status": "open"})
    STORE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("created", key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
