from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_01_filesystem_crawl import CrawlConfig, crawl_selected_root
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    CORPUS_MANIFEST_CONTRACT_VERSION,
    GROUPING_RULE,
    ClassifierInputContractError,
    build_classifier_inputs,
    build_corpus_manifest,
    build_labeled_corpus,
    extract_crawl_result,
    extract_labeled_corpus,
)


ROOT = Path(__file__).resolve().parents[2]


class CorpusManifestTests(unittest.TestCase):
    def test_contract_declares_document_grouping_and_no_raw_fields(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/corpus-manifest-002.json").read_text(encoding="utf-8")
        )

        self.assertEqual(contract["corpus_manifest_contract_version"], CORPUS_MANIFEST_CONTRACT_VERSION)
        self.assertEqual(contract["input_contract"], "classifier-input-002")
        self.assertIn("same source document", contract["grouping"]["purpose"])
        self.assertIn("candidate text", contract["exclusions"])

    def test_manifest_groups_candidates_by_document_and_retains_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sensitive_like" / "configuration_like").mkdir(parents=True)
            (root / "benign_other").mkdir()
            (root / "sensitive_like" / "configuration_like" / "settings.txt").write_text(
                "api_key = SYNTHETIC_VALUE\nservice_token = OTHER_VALUE",
                encoding="utf-8",
            )
            (root / "benign_other" / "metadata.txt").write_text(
                "build_id = BUILD_VALUE", encoding="utf-8"
            )
            crawl = crawl_selected_root(CrawlConfig(root=root))
            inputs = build_classifier_inputs(extract_labeled_corpus(build_labeled_corpus(crawl)))
            manifest = build_corpus_manifest(inputs)

        self.assertEqual(manifest.contract_version, CORPUS_MANIFEST_CONTRACT_VERSION)
        self.assertEqual(manifest.grouping_rule, GROUPING_RULE)
        self.assertEqual(manifest.summary.records, 3)
        self.assertEqual(manifest.summary.groups, 2)
        self.assertEqual(
            dict(manifest.summary.class_counts),
            {"sensitive_like": 2, "placeholder_or_test": 0, "benign_other": 1},
        )
        sensitive_groups = {
            item.group_id for item in manifest.items if item.primary_label == "sensitive_like"
        }
        self.assertEqual(len(sensitive_groups), 1)
        self.assertEqual(manifest.summary.artifact_family_count, 1)
        self.assertNotIn("SYNTHETIC_VALUE", repr(manifest))

    def test_unlabeled_scan_cannot_become_a_corpus_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scan.txt").write_text("token = SYNTHETIC_VALUE", encoding="utf-8")
            inputs = build_classifier_inputs(extract_crawl_result(crawl_selected_root(CrawlConfig(root=root))))
            with self.assertRaisesRegex(ClassifierInputContractError, "requires corpus-labeled") as raised:
                build_corpus_manifest(inputs)

        self.assertNotIn("SYNTHETIC_VALUE", str(raised.exception))
