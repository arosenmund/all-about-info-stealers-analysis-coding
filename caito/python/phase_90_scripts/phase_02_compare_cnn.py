#!/usr/bin/env python3
"""Compare frozen Phase 2 CNN and n-gram baseline configurations."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from hybrid_edge_classifier.stage_90_orchestration.cnn_baseline_comparison_runner import run  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:], sys.stdout, sys.stderr))
