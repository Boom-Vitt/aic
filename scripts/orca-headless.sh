#!/bin/sh
# Validate an Orca plan, or run one bounded headless Claude Code session.
# Dry-run is the default. --apply is opt-in and never pushes or deletes.
set -eu
ROOT=$(unset CDPATH; cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m orca_claude.loop "$@"
