from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from phase_01_baseline import (
    BaselineConfig,
    BaselineContractError,
    build_baseline_dataset,
    fit_and_evaluate_baseline,
)
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
from hybrid_edge_classifier.stage_90_orchestration.baseline_runner import USAGE, run


_VALUES = {
    "sensitive_like": (
        "AURORA_TOKEN_ALPHA_11",
        "BASALT_TOKEN_BRAVO_22",
        "CEDAR_TOKEN_CHARLIE_33",
        "DRIFTWOOD_TOKEN_DELTA_44",
    ),
    "placeholder_or_test": (
        "EXAMPLE_TOKEN_ECHO_55",
        "FIXTURE_TOKEN_FOXTROT_66",
        "SAMPLE_TOKEN_GOLF_77",
        "TEST_TOKEN_HOTEL_88",
    ),
    "benign_other": (
        "build-2026.08.01-local",
        "release-2026.08.02-local",
        "version-2026.08.03-local",
        "package-2026.08.04-local",
    ),
}


class BaselineTests(unittest.TestCase):
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
        config = BaselineConfig(feature_dimension=64, epochs=12, learning_rate=0.25)
        return temporary, preprocess_classifier_inputs(inputs), split, config

    def test_grouped_baseline_is_deterministic_and_redacted(self) -> None:
        temporary, prepared, split, config = self._dataset()
        with temporary:
            dataset = build_baseline_dataset(prepared, split, config)
            first = fit_and_evaluate_baseline(dataset, config)
            second = fit_and_evaluate_baseline(dataset, config)

        self.assertEqual(first.contract_version, "baseline-003")
        self.assertEqual(first.feature_schema_version, "char-ngram-hash-001")
        self.assertEqual(first.class_order, (
            "sensitive_like",
            "placeholder_or_test",
            "benign_other",
        ))
        self.assertEqual(first.train_records, 3)
        self.assertEqual(
            tuple(metrics.split_name for metrics in first.split_metrics),
            ("validation", "calibration", "test"),
        )
        self.assertEqual(
            [metrics.confusion for metrics in first.split_metrics],
            [metrics.confusion for metrics in second.split_metrics],
        )
        self.assertNotIn(_VALUES["sensitive_like"][0], repr(dataset))
        self.assertNotIn(_VALUES["sensitive_like"][0], repr(first))

    def test_machine_readable_contract_matches_the_default_configuration(self) -> None:
        root = Path(__file__).resolve().parents[2]
        contract = json.loads((root / "contracts/baseline-003.json").read_text(encoding="utf-8"))
        config = BaselineConfig()

        self.assertEqual(contract["baseline_contract_version"], "baseline-003")
        self.assertEqual(contract["quality_gate_contract"], "phase-01-quality-gate-002")
        self.assertEqual(contract["split_contract"], "split-002")
        self.assertEqual(contract["class_order"], [
            "sensitive_like",
            "placeholder_or_test",
            "benign_other",
        ])
        self.assertEqual(contract["features"]["ngram_sizes"], [
            config.ngram_minimum,
            config.ngram_minimum + 1,
            config.ngram_maximum,
        ])
        self.assertEqual(contract["training"]["epochs"], config.epochs)
        self.assertEqual(contract["training"]["learning_rate"], config.learning_rate)

    def test_baseline_rejects_split_coverage_or_config_drift_without_echoing_values(self) -> None:
        temporary, prepared, split, config = self._dataset()
        with temporary:
            incomplete = replace(split, items=split.items[:-1])
            with self.assertRaisesRegex(BaselineContractError, "do not match split coverage") as raised:
                build_baseline_dataset(prepared, incomplete, config)
            self.assertNotIn(_VALUES["placeholder_or_test"][0], str(raised.exception))

            dataset = build_baseline_dataset(prepared, split, config)
            with self.assertRaisesRegex(BaselineContractError, "configuration differ"):
                fit_and_evaluate_baseline(
                    dataset, replace(config, feature_dimension=config.feature_dimension + 1)
                )

    def test_explicit_corpus_runner_emits_aggregate_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_corpus(root)
            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = run(["--root", str(root)], stdout, stderr)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["baseline"]["contract_version"], "baseline-003")
        self.assertEqual(result["baseline"]["feature_schema_version"], "char-ngram-hash-001")
        self.assertEqual(result["split_manifest"]["records"], 12)
        self.assertIn("test", result["baseline"]["splits"])
        self.assertNotIn(_VALUES["sensitive_like"][0], stdout.getvalue())
        self.assertNotIn("document-1.txt", stdout.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run([], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), f"{USAGE}\n")
