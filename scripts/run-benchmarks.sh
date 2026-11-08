#!/bin/sh
# Run the pinned AIC-versus-baseline comparison.
# --dry-run prints the token-budget ceiling and does not call a model.
# --routing-pack dev is the tuning pack. heldout-v2 is the release pack.
# --baselines runs each official arm inside the bubblewrap container sandbox.
# Fetch, install, and the agent share that sandbox. A missing or blank
# ANTHROPIC_API_KEY still exits 3 before any fetch or model call.
# An unverified install is excluded. sandbox none is refused.
set -eu
ROOT=$(unset CDPATH; cd -- "$(dirname -- "$0")/.." && pwd)
# The repository root must come first so this command uses benchmarks.routing
# and benchmarks.aicbench, not a script-local package of the same name.
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  printf '%s\n' 'ANTHROPIC_API_KEY is required.' >&2
  exit 3
fi
exec python3 "$ROOT/scripts/benchmarks/run.py" "$@"
