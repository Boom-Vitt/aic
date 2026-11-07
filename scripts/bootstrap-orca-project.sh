#!/bin/sh
# Create a new project directory from the Orca plus Claude Code template.
# Refuses a path that already exists. Does not touch secrets.
set -eu
ROOT=$(unset CDPATH; cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m orca_claude.bootstrap "$@"
