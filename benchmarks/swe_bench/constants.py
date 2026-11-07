"""Pinned SWE-bench Lite dataset and harness evidence.

Checked November 7, 2026. These pins are identifiers and terms, not a measured
score. The dataset is downloaded at runtime and is not stored in this package.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Hugging Face dataset card API, checked November 7, 2026:
# https://huggingface.co/api/datasets/SWE-bench/SWE-bench_Lite
# Card and README: https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite
DATASET_ID = "SWE-bench/SWE-bench_Lite"
DATASET_REVISION = "b0dde1093fe417d83b7184254edf8199c1f0dff5"
DATASET_SPLIT = "test"
EXPECTED_TEST_INSTANCES = 300
SMOKE_INSTANCES = 10

# The pinned harness loads this dataset id. The older princeton-nlp mirror
# does not publish the container fields that harness revision expects, and its
# card also has no license field (card sha 6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2,
# checked the same day).
DATASET_CARD_LICENSE_FIELD = None

# Official harness, MIT, checked November 7, 2026.
# https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/LICENSE
# Copyright (c) 2023 Carlos E Jimenez, John Yang, Alexander Wettig, Shunyu Yao,
# Kexin Pei, Ofir Press, Karthik R Narasimhan.
HARNESS_COMMIT = "02e7a74ffd0b707aab73d203fe87bdc7c76afc8e"
HARNESS_REPOSITORY = "https://github.com/SWE-bench/SWE-bench"
HARNESS_LICENSE = "MIT"
HARNESS_REQUIREMENT = f"swebench @ git+{HARNESS_REPOSITORY}.git@{HARNESS_COMMIT}"

MISSING_KEY_EXIT = 3
MISSING_KEY_MESSAGE = (
    "ANTHROPIC_API_KEY is required. No SWE-bench predictions or scores were recorded."
)

BASELINE_CONDITION = "baseline"
AIC_CONDITION = "aic"
MODEL_NAMES = {
    BASELINE_CONDITION: "claude-code-baseline",
    AIC_CONDITION: "claude-code-aic",
}
# Explicit plugin invocation. Bare print mode does not advertise discovered skills.
AIC_SKILL_COMMAND = "/aic:aic"

CHECKED_ON = "2026-11-07"
