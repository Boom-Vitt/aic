#!/usr/bin/env python3
"""Host-started stdio launcher using the same namespace as the installed wheel."""
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    print("AIC requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(2)
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from aic.scripts.aiclib.mcp_server import main

raise SystemExit(main())
