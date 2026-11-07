#!/bin/sh
# ci/unit.sh - the CI "unit" job (cwd-sh-1e8)
set -e
cd tests
python -B -m unittest discover -s . -t ..
