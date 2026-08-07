#!/usr/bin/env python3
"""Run the Python-only grouped `baseline-003` POC on one explicit corpus root."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from hybrid_edge_classifier.stage_90_orchestration.baseline_runner import run  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:], sys.stdout, sys.stderr))
