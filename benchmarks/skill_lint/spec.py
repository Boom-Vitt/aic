"""Published limits the checker measures against.

Field limits and the progressive-disclosure sizes come from the Agent Skills
specification and Anthropic's skill authoring documents. The score weights,
the terse-description floor, and the trigger phrases are AIC's deterministic
hygiene metric; they are not an Anthropic ranking.
"""

from __future__ import annotations

SPEC_REVISION = "83021e2be457a9b6679148719c1f6074f0ad975e"
SPEC_URL = "https://agentskills.io/specification"
SPEC_REPOSITORY = "https://github.com/agentskills/agentskills"
ANTHROPIC_SKILL_DOCS = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview"
ANTHROPIC_BEST_PRACTICES = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices"
SPEC_CHECKED = "2026-11-07"

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500
MAX_SKILL_LINES = 500
MAX_INSTRUCTION_UNITS = 5000
TERSE_DESCRIPTION_LENGTH = 40

ERROR_WEIGHT = 20
WARNING_WEIGHT = 5
MAX_REPORTED_FINDINGS = 40

ALLOWED_FIELDS = frozenset(
    {"allowed-tools", "compatibility", "description", "license", "metadata", "name"}
)
