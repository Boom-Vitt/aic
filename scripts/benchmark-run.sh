#!/bin/sh
# Plan or run the local benchmark recorder. Public suites stay blocked.
set -eu
ROOT=$(unset CDPATH; cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m aicbench.runner "$@"
