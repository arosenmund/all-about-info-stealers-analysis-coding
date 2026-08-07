from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_01_filesystem_crawl import CrawlConfig, crawl_selected_root
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    CONTEXT_AFTER_LINES,
    CONTEXT_BEFORE_LINES,
    EXTRACTION_CONTRACT_VERSION,
    extract_crawl_result,
    extract_document,
    extract_labeled_corpus,
    build_labeled_corpus,
)


ROOT = Path(__file__).resolve().parents[2]


class ExtractionTests(unittest.TestCase):
    def test_contract_matches_primary_labels_and_context_window(self) -> None:
        contract = json.loads((ROOT / "contracts/extract-002.json").read_text(encoding="utf-8"))

        self.assertEqual(contract["extraction_contract_version"], EXTRACTION_CONTRACT_VERSION)
        self.assertEqual(contract["context"]["before_lines"], CONTEXT_BEFORE_LINES)
        self.assertEqual(contract["context"]["after_lines"], CONTEXT_AFTER_LINES)
        self.assertIn("corpus annotations", contract["folder_label_rule"].lower())
        self.assertEqual(tuple(contract["input_contracts"]), ("crawl-001", "corpus-001"))

    def test_extracts_assignments_with_context_quotes_and_comments(self) -> None:
        text = "\n".join(
            (
                "before = value",
                'service_token = "SYNTHETIC#VALUE" # comment',
                "endpoint: EXAMPLE_VALUE // comment",
                "not an assignment",
                "after = final",
            )
        )

        items = extract_document("document-001", text)

        self.assertEqual([item.key for item in items], ["before", "service_token", "endpoint", "after"])
        self.assertEqual(
            [item.candidate for item in items],
            ["value", "SYNTHETIC#VALUE", "EXAMPLE_VALUE", "final"],
        )
        token = items[1]
        self.assertEqual(token.line_number, 2)
        self.assertEqual(token.before, ("before = value",))
        self.assertEqual(token.after, ("endpoint: EXAMPLE_VALUE // comment", "not an assignment"))
        self.assertEqual(token.record_id, "extract-002-document-001-000002-01")

    def test_extracts_top_level_json_strings_in_source_order_and_ignores_other_values(self) -> None:
        items = extract_document(
            "document-json-001",
            '{"api_key":"JSON_VALUE","retries":3,"note":"example","nested":{"key":"skip"}}',
        )

        self.assertEqual(
            [(item.extraction_kind, item.key, item.candidate, item.ordinal) for item in items],
            [("json_string", "api_key", "JSON_VALUE", 1), ("json_string", "note", "example", 2)],
        )

    def test_extracts_multiline_json_string_properties(self) -> None:
        items = extract_document(
            "document-json-properties-001",
            "{\n  \"api_key\": \"JSON_VALUE\",\n  \"note\": \"example\"\n}",
        )

        self.assertEqual(
            [(item.extraction_kind, item.key, item.candidate, item.line_number) for item in items],
            [
                ("json_string_property", "api_key", "JSON_VALUE", 2),
                ("json_string_property", "note", "example", 3),
            ],
        )

    def test_extracts_conservative_relaxed_colon_mappings(self) -> None:
        items = extract_document(
            "document-relaxed-001",
            "`Display Key`: EXAMPLE_VALUE\n@example: SECOND_VALUE # note\nplain prose: ignored?",
        )

        self.assertEqual(
            [(item.extraction_kind, item.key, item.candidate) for item in items],
            [
                ("relaxed_mapping", "Display Key", "EXAMPLE_VALUE"),
                ("relaxed_mapping", "@example", "SECOND_VALUE"),
                ("relaxed_mapping", "plain prose", "ignored?"),
            ],
        )

    def test_unmatched_lines_produce_no_candidates(self) -> None:
        items = extract_document("document-empty-001", "plain prose\nkey = \n[1, 2, 3]")
        self.assertEqual(items, ())

    def test_crawl_and_corpus_extraction_keep_their_label_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sensitive_like" / "config").mkdir(parents=True)
            (root / "placeholder_or_test").mkdir()
            (root / "sensitive_like" / "config" / "sample.txt").write_text(
                "token = SYNTHETIC_VALUE", encoding="utf-8"
            )
            (root / "placeholder_or_test" / "example.txt").write_text(
                "example: REPLACE_ME", encoding="utf-8"
            )
            crawl = crawl_selected_root(CrawlConfig(root=root))
            unlabeled = extract_crawl_result(crawl)
            labeled = extract_labeled_corpus(build_labeled_corpus(crawl))

        self.assertEqual([item.primary_label for item in unlabeled.items], [None, None])
        self.assertEqual(
            [(item.primary_label, item.artifact_family) for item in labeled.items],
            [("placeholder_or_test", None), ("sensitive_like", "config")],
        )
        self.assertEqual(labeled.summary.documents, 2)
        self.assertEqual(labeled.summary.kind_count("assignment"), 2)
