from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from phase_01_baseline import BaselineConfig, build_baseline_dataset
from phase_01_evaluation import CalibrationConfig, fit_calibration_and_evaluate
from hybrid_edge_classifier.stage_01_filesystem_crawl import CrawlConfig, crawl_selected_root
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    analyze_corpus_duplicates,
    build_classifier_inputs,
    build_corpus_manifest,
    build_labeled_corpus,
    build_split_manifest,
    extract_labeled_corpus,
    preprocess_classifier_inputs,
)
from hybrid_edge_classifier.stage_90_orchestration.calibration_runner import USAGE, run


_VALUES = {
    "sensitive_like": ("AURORA_TOKEN_ALPHA_11", "BASALT_TOKEN_BRAVO_22", "CEDAR_TOKEN_CHARLIE_33", "DRIFTWOOD_TOKEN_DELTA_44"),
    "placeholder_or_test": ("EXAMPLE_TOKEN_ECHO_55", "FIXTURE_TOKEN_FOXTROT_66", "SAMPLE_TOKEN_GOLF_77", "TEST_TOKEN_HOTEL_88"),
    "benign_other": ("build-2026.08.01-local", "release-2026.08.02-local", "version-2026.08.03-local", "package-2026.08.04-local"),
}


class CalibrationTests(unittest.TestCase):
    @staticmethod
    def _write_corpus(root: Path) -> None:
        for label, candidates in _VALUES.items():
            directory = root / label
            directory.mkdir()
            for index, candidate in enumerate(candidates, start=1):
                (directory / f"document-{index}.txt").write_text(
                    f"fixture_value = {candidate}\n", encoding="utf-8"
                )

    def _dataset(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        self._write_corpus(root)
        crawl = crawl_selected_root(CrawlConfig(root=root))
        inputs = build_classifier_inputs(extract_labeled_corpus(build_labeled_corpus(crawl)))
        manifest = build_corpus_manifest(inputs)
        split = build_split_manifest(manifest, analyze_corpus_duplicates(inputs, manifest))
        return temporary, build_baseline_dataset(preprocess_classifier_inputs(inputs), split, BaselineConfig(feature_dimension=64, epochs=12, learning_rate=0.25))

    def test_calibration_and_abstention_are_deterministic_and_aggregate_only(self) -> None:
        temporary, dataset = self._dataset()
        config = CalibrationConfig()
        with temporary:
            first = fit_calibration_and_evaluate(dataset, dataset.config, config)
            second = fit_calibration_and_evaluate(dataset, dataset.config, config)

        self.assertEqual(first.contract_version, "calibration-001")
        self.assertEqual(first.baseline_contract_version, "baseline-003")
        self.assertEqual(first.quality_gate_contract_version, "phase-01-quality-gate-002")
        self.assertEqual(first.temperature, second.temperature)
        self.assertEqual(first.confidence_threshold, second.confidence_threshold)
        self.assertEqual(first.split_metrics, second.split_metrics)
        self.assertEqual(tuple(item.split_name for item in first.split_metrics), ("calibration", "test"))
        self.assertNotIn(_VALUES["sensitive_like"][0], repr(first))

    def test_machine_readable_contract_matches_the_default_configuration(self) -> None:
        root = Path(__file__).resolve().parents[2]
        contract = json.loads((root / "contracts/calibration-001.json").read_text(encoding="utf-8"))
        config = CalibrationConfig()

        self.assertEqual(contract["contract_version"], "calibration-001")
        self.assertEqual(contract["baseline_contract"], "baseline-003")
        self.assertEqual(contract["quality_gate_contract"], "phase-01-quality-gate-002")
        self.assertEqual(contract["temperature"]["candidates"], list(config.temperatures))
        self.assertEqual(contract["abstention"]["threshold_candidates"], list(config.confidence_thresholds))
        self.assertEqual(contract["evaluation"]["ece_bins"], config.ece_bins)

    def test_explicit_runner_is_redacted_and_requires_a_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_corpus(root)
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(run(["--root", str(root)], stdout, stderr), 0)

        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["calibration"]["contract_version"], "calibration-001")
        self.assertEqual(result["calibration"]["baseline_contract_version"], "baseline-003")
        self.assertEqual(set(result["calibration"]["splits"]), {"calibration", "test"})
        self.assertNotIn(_VALUES["sensitive_like"][0], stdout.getvalue())
        self.assertNotIn("document-1.txt", stdout.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run([], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), f"{USAGE}\n")
