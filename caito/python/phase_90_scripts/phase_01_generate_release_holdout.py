#!/usr/bin/env python3
"""Create or verify the synthetic release-holdout-001 cohort."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from phase_01_evaluation.release_holdout import (  # noqa: E402
    ASSIGNMENTS_PER_DOCUMENT,
    DOCUMENTS_PER_FAMILY,
    FAMILIES_PER_LABEL,
    PRIMARY_LABELS,
    RELEASE_HOLDOUT_CONTRACT_VERSION,
    expected_documents,
    run,
)


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:], sys.stdout, sys.stderr))
