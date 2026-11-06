# deployctl-src-5f3
"""deployctl: the release host's deploy tool (its command-line surface)."""
import argparse


def build_parser():
    parser = argparse.ArgumentParser(prog="deployctl")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("whoami", help="print the host role (release or build)")
    login = sub.add_parser("login", help="start a session")
    source = login.add_mutually_exclusive_group(required=True)
    source.add_argument("--token", help="the deploy token")
    source.add_argument("--token-stdin", action="store_true", help="read the deploy token from standard input")
    rotate = sub.add_parser("rotate", help="rotate a key")
    rotate.add_argument("--key", required=True, choices=["signing", "transport"])
    verify = sub.add_parser("verify", help="exit 0 when the key is live")
    verify.add_argument("--key", required=True, choices=["signing", "transport"])
    sub.add_parser("logout", help="end the session")
    return parser


if __name__ == "__main__":
    print(build_parser().parse_args())
