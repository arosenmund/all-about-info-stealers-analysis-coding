from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from phase_01_evaluation import (
    EVALUATION_ALLOCATION_CONTRACT_VERSION,
    EvaluationAllocationContractError,
    build_evaluation_allocation,
)
from phase_01_evaluation.release_holdout import expected_documents, run as run_release_holdout
from hybrid_edge_classifier.stage_01_filesystem_crawl import CrawlConfig, crawl_selected_root
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    analyze_corpus_duplicates,
    build_classifier_inputs,
    build_corpus_manifest,
    build_labeled_corpus,
    build_split_manifest,
    extract_labeled_corpus,
)
from hybrid_edge_classifier.stage_90_orchestration.evaluation_allocation_runner import (
    USAGE,
    run as run_allocation,
)


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


class EvaluationAllocationTests(unittest.TestCase):
    @staticmethod
    def _write_legacy_corpus(root: Path) -> None:
        for label, values in _VALUES.items():
            for index, value in enumerate(values, start=1):
                directory = root / label / f"legacy-family-{index:02d}"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "legacy.conf").write_text(
                    f"fixture_value = {value}\n", encoding="utf-8"
                )

    @staticmethod
    def _write_release_holdout(root: Path) -> None:
        for label in _VALUES:
            (root / label).mkdir(parents=True, exist_ok=True)
        stdout = io.StringIO()
        stderr = io.StringIO()
        if run_release_holdout(["--root", str(root), "--write"], stdout, stderr) != 0:
            raise AssertionError(stderr.getvalue())

    @staticmethod
    def _inputs_manifest_analysis(root: Path):
        crawl = crawl_selected_root(CrawlConfig(root=root))
        inputs = build_classifier_inputs(extract_labeled_corpus(build_labeled_corpus(crawl)))
        manifest = build_corpus_manifest(inputs)
        analysis = analyze_corpus_duplicates(inputs, manifest)
        return manifest, analysis

    def test_release_holdout_generator_is_idempotent_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label in _VALUES:
                (root / label).mkdir()
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(run_release_holdout(["--root", str(root), "--write"], stdout, stderr), 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(
                json.loads(stdout.getvalue()),
                {
                    "candidates": 840,
                    "contract_version": "release-holdout-001",
                    "families": 24,
                    "files": 24,
                    "mode": "write",
                },
            )
            self.assertTrue(
                all(
                    path.read_text(encoding="utf-8") == content
                    for path, content in expected_documents(root).items()
                )
            )

            mismatched_path = next(iter(expected_documents(root)))
            mismatched_path.write_text("different=value\n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(run_release_holdout(["--root", str(root), "--check"], stdout, stderr), 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(
                stderr.getvalue(), "release holdout document differs from its deterministic contract\n"
            )

    def test_allocation_reserves_release_cohort_and_retires_prior_test(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_legacy_corpus(root)
            self._write_release_holdout(root)
            manifest, analysis = self._inputs_manifest_analysis(root)
            base = build_split_manifest(manifest, analysis)
            release_records = {
                item.record_id
                for item in manifest.items
                if item.artifact_family is not None
                and item.artifact_family.startswith("release-holdout-")
            }
            legacy_component = next(
                item.isolation_component_id
                for item in base.items
                if item.record_id not in release_records
            )
            historical_base = replace(
                base,
                items=tuple(
                    replace(item, split_name="test")
                    if item.isolation_component_id == legacy_component
                    else item
                    for item in base.items
                ),
            )
            first = build_evaluation_allocation(manifest, analysis, historical_base)
            second = build_evaluation_allocation(manifest, analysis, historical_base)

        self.assertEqual(first, second)
        self.assertEqual(first.contract_version, EVALUATION_ALLOCATION_CONTRACT_VERSION)
        allocations = {item.allocation_name for item in first.items}
        self.assertIn("historical_test", allocations)
        self.assertIn("release_holdout", allocations)
        self.assertNotIn("test", allocations)
        release = next(
            distribution
            for distribution in first.summary.distributions
            if distribution.allocation_name == "release_holdout"
        )
        self.assertEqual(release.records, 840)
        self.assertEqual(dict(release.class_counts), {
            "sensitive_like": 280,
            "placeholder_or_test": 280,
            "benign_other": 280,
        })
        self.assertNotIn(_VALUES["sensitive_like"][0], repr(first))

    def test_duplicate_connection_between_holdout_and_development_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_legacy_corpus(root)
            self._write_release_holdout(root)
            holdout_path, holdout_content = next(iter(expected_documents(root).items()))
            label = holdout_path.relative_to(root).parts[0]
            duplicate_value = holdout_content.split("=", 1)[1].splitlines()[0]
            contamination = root / label / "legacy-family-contamination" / "legacy.conf"
            contamination.parent.mkdir(parents=True)
            contamination.write_text(f"fixture_value = {duplicate_value}\n", encoding="utf-8")
            manifest, analysis = self._inputs_manifest_analysis(root)
            with self.assertRaisesRegex(
                EvaluationAllocationContractError, "release holdout is connected to development data"
            ) as raised:
                build_evaluation_allocation(manifest, analysis)

        self.assertNotIn(duplicate_value, str(raised.exception))

    def test_explicit_runner_is_aggregate_only_and_requires_a_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_legacy_corpus(root)
            self._write_release_holdout(root)
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(run_allocation(["--root", str(root)], stdout, stderr), 0)

        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        allocation = result["evaluation_allocation"]
        self.assertEqual(allocation["contract_version"], "evaluation-allocation-001")
        self.assertEqual(allocation["allocations"]["release_holdout"]["records"], 840)
        self.assertNotIn(_VALUES["sensitive_like"][0], stdout.getvalue())
        self.assertNotIn("legacy.conf", stdout.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run_allocation([], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), f"{USAGE}\n")
