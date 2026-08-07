from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from phase_01_baseline import SELECTION_CANDIDATES, select_and_confirm_baseline
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
from hybrid_edge_classifier.stage_90_orchestration.baseline_selection_runner import USAGE, run


_VALUES = {
    "sensitive_like": ("AURORA_TOKEN_ALPHA_11", "BASALT_TOKEN_BRAVO_22", "CEDAR_TOKEN_CHARLIE_33", "DRIFTWOOD_TOKEN_DELTA_44"),
    "placeholder_or_test": ("EXAMPLE_TOKEN_ECHO_55", "FIXTURE_TOKEN_FOXTROT_66", "SAMPLE_TOKEN_GOLF_77", "TEST_TOKEN_HOTEL_88"),
    "benign_other": ("build-2026.08.01-local", "release-2026.08.02-local", "version-2026.08.03-local", "package-2026.08.04-local"),
}


class BaselineSelectionTests(unittest.TestCase):
    @staticmethod
    def _write_corpus(root: Path) -> None:
        for label, candidates in _VALUES.items():
            directory = root / label
            directory.mkdir()
            for index, candidate in enumerate(candidates, start=1):
                (directory / f"document-{index}.txt").write_text(
                    f"fixture_value = {candidate}\n", encoding="utf-8"
                )

    def _prepared_and_split(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        self._write_corpus(root)
        crawl = crawl_selected_root(CrawlConfig(root=root))
        inputs = build_classifier_inputs(extract_labeled_corpus(build_labeled_corpus(crawl)))
        manifest = build_corpus_manifest(inputs)
        split = build_split_manifest(manifest, analyze_corpus_duplicates(inputs, manifest))
        return temporary, preprocess_classifier_inputs(inputs), split

    def test_selection_uses_validation_only_before_confirmation_and_is_deterministic(self) -> None:
        temporary, prepared, split = self._prepared_and_split()
        with temporary:
            first = select_and_confirm_baseline(prepared, split)
            second = select_and_confirm_baseline(prepared, split)

        self.assertEqual(first.contract_version, "baseline-selection-001")
        self.assertEqual(first.baseline_contract_version, "baseline-003")
        self.assertEqual(first.quality_gate_contract_version, "phase-01-quality-gate-002")
        self.assertEqual(len(first.candidates), len(SELECTION_CANDIDATES))
        self.assertEqual(
            tuple(result.candidate_id for result in first.candidates),
            tuple(candidate.candidate_id for candidate in SELECTION_CANDIDATES),
        )
        self.assertEqual(first.selected_candidate_id, second.selected_candidate_id)
        self.assertEqual(
            tuple(result.validation for result in first.candidates),
            tuple(result.validation for result in second.candidates),
        )
        self.assertTrue(
            all(result.validation.split_name == "validation" for result in first.candidates)
        )
        self.assertEqual(
            tuple(metric.split_name for metric in first.selected_report.split_metrics),
            ("validation", "calibration", "test"),
        )
        self.assertNotIn(_VALUES["sensitive_like"][0], repr(first))

    def test_machine_readable_contract_matches_predeclared_candidates(self) -> None:
        root = Path(__file__).resolve().parents[2]
        contract = json.loads(
            (root / "contracts/baseline-selection-001.json").read_text(encoding="utf-8")
        )

        self.assertEqual(contract["contract_version"], "baseline-selection-001")
        self.assertEqual(contract["baseline_engine_contract"], "baseline-003")
        self.assertEqual(contract["quality_gate_contract"], "phase-01-quality-gate-002")
        self.assertEqual(
            [item["candidate_id"] for item in contract["candidate_configurations"]],
            [candidate.candidate_id for candidate in SELECTION_CANDIDATES],
        )
        self.assertEqual(
            [item["epochs"] for item in contract["candidate_configurations"]],
            [candidate.config.epochs for candidate in SELECTION_CANDIDATES],
        )

    def test_explicit_runner_is_redacted_and_requires_a_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_corpus(root)
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(run(["--root", str(root)], stdout, stderr), 0)

        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["baseline_selection"]["contract_version"], "baseline-selection-001")
        self.assertEqual(len(result["baseline_selection"]["candidates"]), 3)
        self.assertNotIn(_VALUES["sensitive_like"][0], stdout.getvalue())
        self.assertNotIn("document-1.txt", stdout.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run([], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), f"{USAGE}\n")
