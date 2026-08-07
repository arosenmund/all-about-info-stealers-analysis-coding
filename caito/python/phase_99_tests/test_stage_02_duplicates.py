from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from hybrid_edge_classifier.stage_01_filesystem_crawl import CrawlConfig, crawl_selected_root
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    DUPLICATE_ANALYSIS_CONTRACT_VERSION,
    DUPLICATE_ANALYSIS_MAX_RECORDS,
    NEAR_DUPLICATE_METRIC,
    NEAR_DUPLICATE_MINIMUM_CHARACTERS,
    NEAR_DUPLICATE_THRESHOLD,
    DuplicateAnalysisContractError,
    analyze_corpus_duplicates,
    build_classifier_inputs,
    build_corpus_manifest,
    build_labeled_corpus,
    extract_labeled_corpus,
)


ROOT = Path(__file__).resolve().parents[2]


class DuplicateAnalysisTests(unittest.TestCase):
    def _inputs_and_manifest(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "sensitive_like").mkdir()
        (root / "placeholder_or_test").mkdir()
        (root / "sensitive_like" / "first.txt").write_text(
            "first_key = EXACT_DUPLICATE_VALUE\n"
            "second_key = EXACT_DUPLICATE_VALUE\n"
            "near_key = NEAR_DUPLICATE_TOKEN_ALPHA\n"
            "short_key = ABC12345\n",
            encoding="utf-8",
        )
        (root / "sensitive_like" / "second.txt").write_text(
            "third_key = EXACT_DUPLICATE_VALUE\n"
            "near_key = NEAR_DUPLICATE_TOKEN_ALPHB\n"
            "short_key = ABC12346\n",
            encoding="utf-8",
        )
        (root / "placeholder_or_test" / "example.txt").write_text(
            "example_key = EXACT_DUPLICATE_VALUE\n", encoding="utf-8"
        )
        crawl = crawl_selected_root(CrawlConfig(root=root))
        inputs = build_classifier_inputs(extract_labeled_corpus(build_labeled_corpus(crawl)))
        return temporary, inputs, build_corpus_manifest(inputs)

    def test_contract_declares_redacted_deterministic_comparisons(self) -> None:
        contract = json.loads((ROOT / "contracts/duplicate-001.json").read_text(encoding="utf-8"))

        self.assertEqual(
            contract["duplicate_analysis_contract_version"], DUPLICATE_ANALYSIS_CONTRACT_VERSION
        )
        self.assertEqual(contract["near_comparison"]["metric"], NEAR_DUPLICATE_METRIC)
        self.assertEqual(
            contract["near_comparison"]["threshold"], NEAR_DUPLICATE_THRESHOLD
        )
        self.assertEqual(contract["resource_limits"]["max_records"], DUPLICATE_ANALYSIS_MAX_RECORDS)
        self.assertIn("candidate text", contract["exclusions"])
        self.assertIn("automatic split assignment", contract["exclusions"])

    def test_exact_near_and_cross_label_summary_is_deterministic_and_redacted(self) -> None:
        temporary, inputs, manifest = self._inputs_and_manifest()
        with temporary:
            first = analyze_corpus_duplicates(inputs, manifest)
            second = analyze_corpus_duplicates(inputs, manifest)

        self.assertEqual(first, second)
        self.assertEqual(first.contract_version, DUPLICATE_ANALYSIS_CONTRACT_VERSION)
        self.assertEqual(first.metric, NEAR_DUPLICATE_METRIC)
        self.assertEqual(first.near_duplicate_threshold, NEAR_DUPLICATE_THRESHOLD)
        self.assertEqual(
            first.near_duplicate_minimum_characters, NEAR_DUPLICATE_MINIMUM_CHARACTERS
        )
        self.assertEqual(first.summary.records, 8)
        self.assertEqual(first.summary.exact.clusters, 1)
        self.assertEqual(first.summary.exact.records, 4)
        self.assertEqual(first.summary.exact.cross_group_clusters, 1)
        self.assertEqual(first.summary.exact.cross_group_records, 4)
        self.assertEqual(first.summary.exact.cross_label_clusters, 1)
        self.assertEqual(first.summary.exact.cross_label_records, 4)
        self.assertEqual(first.summary.near.clusters, 1)
        self.assertEqual(first.summary.near.records, 2)
        self.assertEqual(first.summary.near.cross_group_clusters, 1)
        self.assertEqual(first.summary.near.cross_group_records, 2)
        self.assertEqual(first.summary.near.cross_label_clusters, 0)
        self.assertEqual(first.summary.near.cross_label_records, 0)
        self.assertEqual(tuple(cluster.kind for cluster in first.clusters), ("exact", "near"))
        self.assertNotIn("EXACT_DUPLICATE_VALUE", repr(first))
        self.assertNotIn("NEAR_DUPLICATE_TOKEN_ALPHA", repr(first))
        self.assertNotIn("ABC12345", repr(first))

    def test_manifest_alignment_fails_without_echoing_candidates(self) -> None:
        temporary, inputs, manifest = self._inputs_and_manifest()
        with temporary:
            incomplete = replace(manifest, items=manifest.items[:-1])
            with self.assertRaisesRegex(DuplicateAnalysisContractError, "does not match") as raised:
                analyze_corpus_duplicates(inputs, incomplete)

        self.assertNotIn("EXACT_DUPLICATE_VALUE", str(raised.exception))

    def test_record_limit_fails_before_pairwise_comparison(self) -> None:
        temporary, inputs, manifest = self._inputs_and_manifest()
        with temporary:
            source_input = inputs.items[0]
            source_manifest = manifest.items[0]
            over_limit_inputs = tuple(
                replace(source_input, record_id=f"record-{index:05d}")
                for index in range(DUPLICATE_ANALYSIS_MAX_RECORDS + 1)
            )
            over_limit_manifest = tuple(
                replace(source_manifest, record_id=f"record-{index:05d}")
                for index in range(DUPLICATE_ANALYSIS_MAX_RECORDS + 1)
            )
            with self.assertRaisesRegex(DuplicateAnalysisContractError, "bounded record limit") as raised:
                analyze_corpus_duplicates(
                    replace(inputs, items=over_limit_inputs),
                    replace(manifest, items=over_limit_manifest),
                )

        self.assertNotIn("EXACT_DUPLICATE_VALUE", str(raised.exception))
