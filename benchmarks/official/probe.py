"""Report whether the AIC skill mount is visible. This is not a score."""
import json
from pathlib import Path

print(json.dumps({"workflow_loaded": Path("/opt/aic/SKILL.md").is_file()}))
