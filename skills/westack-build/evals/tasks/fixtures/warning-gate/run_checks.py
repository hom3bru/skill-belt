"""The project's checks: the unit tests, with every warning raised as an error. checks-script-8b3"""
import subprocess
import sys


def main():
    command = [sys.executable, "-W", "error", "-m", "unittest", "discover", "-s", "tests", "-v"]
    return subprocess.call(command)


if __name__ == "__main__":
    sys.exit(main())
