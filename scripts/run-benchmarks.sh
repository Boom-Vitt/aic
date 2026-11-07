#!/bin/sh
# Run the pinned AIC-versus-baseline comparison.
# --dry-run prints the token-budget ceiling and does not call a model.
set -eu
ROOT=$(unset CDPATH; cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  printf '%s\n' 'ANTHROPIC_API_KEY is required.' >&2
  exit 3
fi
exec python3 -m benchmarks.run "$@"
