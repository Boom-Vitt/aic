#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${AIC_PYTHON:-}" ]; then
  PY=$AIC_PYTHON
elif [ -x "$ROOT/.venv/bin/python" ]; then
  PY=$ROOT/.venv/bin/python
else
  PY=python3
fi
export PYTHONDONTWRITEBYTECODE=1
exec "$PY" "$ROOT/scripts/verify.py"
