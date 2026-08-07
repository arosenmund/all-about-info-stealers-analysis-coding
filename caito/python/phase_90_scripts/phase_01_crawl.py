#!/usr/bin/env python3
"""Run one explicit-root Stage 01 crawl and print a redacted aggregate summary."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from hybrid_edge_classifier.stage_90_orchestration.crawl_runner import run  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:], sys.stdout, sys.stderr))
