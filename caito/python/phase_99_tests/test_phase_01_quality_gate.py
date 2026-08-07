from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Phase01QualityGateTests(unittest.TestCase):
    def test_quality_gate_is_versioned_and_keeps_test_out_of_selection(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/phase-01-quality-gate-002.json").read_text(encoding="utf-8")
        )

        self.assertEqual(contract["contract_version"], "phase-01-quality-gate-002")
        self.assertEqual(contract["supersedes"], "phase-01-quality-gate-001")
        self.assertEqual(contract["evaluation_split_contract"], "split-002")
        self.assertIn("validation only", contract["selection_protocol"]["model_selection"])
        self.assertIn("never tune", contract["selection_protocol"]["test"])
        self.assertGreaterEqual(
            contract["data_readiness"]["fixed_fpr_one_percent_minimum_one_vs_rest_negatives"],
            100,
        )
        self.assertGreaterEqual(
            contract["data_readiness"]["minimum_records_per_primary_label_per_heldout_split"],
            30,
        )
        self.assertEqual(
            set(contract["baseline_selection_targets"]["validation_per_class_f1_minimum"]),
            {"sensitive_like", "placeholder_or_test", "benign_other"},
        )
        self.assertEqual(
            set(contract["baseline_selection_targets"]["sensitive_like_recall_at_empirical_fpr_minimum"]),
            {"0.10"},
        )
        self.assertEqual(
            contract["future_low_false_positive_objective"]
            ["sensitive_like_recall_at_empirical_fpr_minimum"]["0.01"],
            0.2,
        )
        self.assertGreaterEqual(
            contract["later_calibration_and_policy_targets"]["non_abstained_coverage_minimum"],
            0.7,
        )
