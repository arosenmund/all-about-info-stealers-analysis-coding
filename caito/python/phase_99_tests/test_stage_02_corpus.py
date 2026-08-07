from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_00_authorization.contracts import PRIMARY_CLASSES
from hybrid_edge_classifier.stage_01_filesystem_crawl import (
    CrawlConfig,
    default_lab_corpus_root,
    crawl_selected_root,
)
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    CORPUS_CONTRACT_VERSION,
    CorpusContractError,
    build_labeled_corpus,
)


ROOT = Path(__file__).resolve().parents[2]


class FolderLabeledCorpusTests(unittest.TestCase):
    def test_default_corpus_root_is_project_local_and_not_cwd_dependent(self) -> None:
        self.assertEqual(default_lab_corpus_root(), ROOT / "corpus")
        self.assertTrue(default_lab_corpus_root().is_absolute())

    def test_contract_matches_primary_labels_and_declares_inference_boundary(self) -> None:
        contract = json.loads((ROOT / "contracts/corpus-001.json").read_text(encoding="utf-8"))

        self.assertEqual(contract["corpus_contract_version"], CORPUS_CONTRACT_VERSION)
        self.assertEqual(tuple(contract["primary_labels"]), PRIMARY_CLASSES)
        self.assertIn("must not", contract["inference_rule"])

    def test_derives_primary_label_and_optional_artifact_family_from_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sensitive_like" / "configuration_like").mkdir(parents=True)
            (root / "placeholder_or_test").mkdir()
            (root / "benign_other" / "ordinary_metadata" / "nested").mkdir(parents=True)
            (root / "sensitive_like" / "configuration_like" / "one.txt").write_text(
                "SENSITIVE", encoding="utf-8"
            )
            (root / "placeholder_or_test" / ".example").write_text("PLACEHOLDER", encoding="utf-8")
            (root / "benign_other" / "ordinary_metadata" / "nested" / "three.key").write_text(
                "BENIGN", encoding="utf-8"
            )

            corpus = build_labeled_corpus(crawl_selected_root(CrawlConfig(root=root)))

        self.assertEqual(corpus.contract_version, "corpus-001")
        self.assertEqual(
            [(item.primary_label, item.artifact_family) for item in corpus.items],
            [
                ("benign_other", "ordinary_metadata"),
                ("placeholder_or_test", None),
                ("sensitive_like", "configuration_like"),
            ],
        )
        self.assertEqual(corpus.summary.items, 3)
        self.assertEqual(
            [corpus.summary.class_count(label) for label in PRIMARY_CLASSES], [1, 1, 1]
        )

    def test_rejects_unlabeled_or_unknown_label_paths_without_echoing_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "direct.txt").write_text("UNLABELED", encoding="utf-8")
            (root / "unknown_label").mkdir()
            (root / "unknown_label" / "sample.txt").write_text("UNKNOWN", encoding="utf-8")

            crawl_result = crawl_selected_root(CrawlConfig(root=root))
            with self.assertRaises(CorpusContractError) as caught:
                build_labeled_corpus(crawl_result)

        self.assertEqual(caught.exception.code, "unlabeled_path")
        self.assertNotIn("direct.txt", caught.exception.message)
        self.assertNotIn("unknown_label", caught.exception.message)
