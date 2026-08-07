from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_90_orchestration.crawl_runner import USAGE, run


class CrawlCliTests(unittest.TestCase):
    def test_explicit_root_emits_only_redacted_aggregate_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sensitive_like").mkdir()
            (root / "sensitive_like" / "fixture.key").write_text(
                "private_key = SYNTHETIC_KEY_FIXTURE", encoding="utf-8"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = run(
                ["--root", str(root), "--as-corpus", "--manifest"], stdout, stderr
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["files_collected"], 1)
        self.assertEqual(result["corpus"]["class_counts"], {
            "sensitive_like": 1,
            "placeholder_or_test": 0,
            "benign_other": 0,
        })
        self.assertEqual(result["extraction"], {
            "contract_version": "extract-002",
            "documents": 1,
            "candidates": 1,
            "kind_counts": {"assignment": 1},
        })
        self.assertEqual(result["classifier_input"], {
            "contract_version": "classifier-input-002",
            "preprocessing_version": "preprocess-001",
            "extracted": 1,
            "prepared": 1,
            "rejected": 0,
            "rejection_codes": {},
        })
        self.assertEqual(result["corpus_manifest"], {
            "contract_version": "corpus-manifest-002",
            "preprocessing_version": "preprocess-001",
            "grouping_rule": "all candidates extracted from one crawl document share one group",
            "records": 1,
            "groups": 1,
            "class_counts": {
                "sensitive_like": 1,
                "placeholder_or_test": 0,
                "benign_other": 0,
            },
            "artifact_family_count": 0,
            "classifier_input_rejections": 0,
            "rejection_codes": {},
        })
        self.assertNotIn("fixture.key", stdout.getvalue())
        self.assertNotIn("SYNTHETIC_KEY_FIXTURE", stdout.getvalue())

    def test_requires_an_explicit_root_and_sanitizes_root_errors(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run([], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), f"{USAGE}\n")

        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(run(["--root", str(missing)], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "unable to crawl the explicitly selected root\n")
        self.assertNotIn("missing", stderr.getvalue())

    def test_corpus_mode_rejects_unlabeled_files_without_echoing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "not-labeled.txt").write_text("synthetic", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(run(["--root", str(root), "--as-corpus"], stdout, stderr), 1)

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "selected root does not match the required corpus layout\n")
        self.assertNotIn("not-labeled.txt", stderr.getvalue())

    def test_manifest_requires_the_explicit_corpus_mode(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run(["--root", "/not-used", "--manifest"], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "corpus manifest requires --as-corpus\n")

    def test_duplicate_analysis_is_aggregate_only_and_requires_a_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sensitive_like").mkdir()
            (root / "placeholder_or_test").mkdir()
            (root / "sensitive_like" / "first.txt").write_text(
                "private_key = SYNTHETIC_SHARED_VALUE", encoding="utf-8"
            )
            (root / "placeholder_or_test" / "example.txt").write_text(
                "example_value = SYNTHETIC_SHARED_VALUE", encoding="utf-8"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = run(["--root", str(root), "--as-corpus", "--duplicates"], stdout, stderr)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["duplicate_analysis"], {
            "contract_version": "duplicate-001",
            "metric": "sequence-matcher-nfc-001",
            "near_duplicate_threshold": 0.92,
            "near_duplicate_minimum_characters": 12,
            "records": 2,
            "exact": {
                "clusters": 1,
                "records": 2,
                "cross_group_clusters": 1,
                "cross_group_records": 2,
                "cross_label_clusters": 1,
                "cross_label_records": 2,
            },
            "near": {
                "clusters": 0,
                "records": 0,
                "cross_group_clusters": 0,
                "cross_group_records": 0,
                "cross_label_clusters": 0,
                "cross_label_records": 0,
            },
        })
        self.assertNotIn("first.txt", stdout.getvalue())
        self.assertNotIn("SYNTHETIC_SHARED_VALUE", stdout.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run(["--root", "/not-used", "--duplicates"], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "duplicate analysis requires --as-corpus\n")

    def test_split_planning_emits_aggregate_assignments_and_fails_closed_on_conflicts(self) -> None:
        values = {
            "sensitive_like": ("AURORA_CEDAR_OPAL_49", "BASALT_TIGER_COPPER_75", "DRIFTWOOD_LANTERN_SAPPHIRE_18", "FALCON_MARBLE_VIOLET_63"),
            "placeholder_or_test": ("GARDEN_COMPASS_AMBER_24", "HARBOR_WILLOW_QUARTZ_86", "IVORY_PEBBLE_CORAL_37", "JUNIPER_ANCHOR_SILVER_52"),
            "benign_other": ("KETTLE_ORBIT_INDIGO_94", "LILAC_BROOK_BRONZE_16", "MEADOW_RAVEN_JADE_68", "NORTHSTAR_FERN_GOLD_29"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label, candidates in values.items():
                directory = root / label
                directory.mkdir()
                for index, candidate in enumerate(candidates, start=1):
                    (directory / f"document-{index}.txt").write_text(
                        f"fixture_value = {candidate}", encoding="utf-8"
                    )
            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = run(["--root", str(root), "--as-corpus", "--splits"], stdout, stderr)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        split_manifest = result["split_manifest"]
        self.assertEqual(split_manifest["contract_version"], "split-002")
        self.assertEqual(split_manifest["records"], 12)
        self.assertEqual(split_manifest["groups"], 12)
        self.assertEqual(split_manifest["components"], 12)
        self.assertEqual(set(split_manifest["splits"]), {"train", "validation", "calibration", "test"})
        self.assertNotIn("AURORA_CEDAR_OPAL_49", stdout.getvalue())
        self.assertNotIn("document-1.txt", stdout.getvalue())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sensitive_like").mkdir()
            (root / "placeholder_or_test").mkdir()
            (root / "sensitive_like" / "one.txt").write_text(
                "value = CROSS_LABEL_SYNTHETIC_VALUE", encoding="utf-8"
            )
            (root / "placeholder_or_test" / "two.txt").write_text(
                "value = CROSS_LABEL_SYNTHETIC_VALUE", encoding="utf-8"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(run(["--root", str(root), "--as-corpus", "--splits"], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "split planning requires cross-label duplicate review\n")

        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run(["--root", "/not-used", "--splits"], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "split planning requires --as-corpus\n")

    def test_feature_extraction_emits_only_aggregate_indicator_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sensitive_like").mkdir()
            (root / "sensitive_like" / "fixture.txt").write_text(
                "# example fixture\nfixture_value = AAAA-12\ncopy AAAA-12",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = run(["--root", str(root), "--as-corpus", "--features"], stdout, stderr)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["features"], {
            "feature_schema_version": "features-001",
            "preprocessing_version": "preprocess-001",
            "records": 1,
            "feature_count": 17,
            "indicator_counts": {
                "is_uuid_like": 0,
                "is_hex_digest_like": 0,
                "is_base64_like": 0,
                "is_assignment_extraction": 1,
                "context_has_placeholder_language": 1,
                "candidate_in_nearby_context": 1,
            },
        })
        self.assertNotIn("fixture.txt", stdout.getvalue())
        self.assertNotIn("AAAA-12", stdout.getvalue())

    def test_feature_audit_is_label_stratified_and_aggregate_only(self) -> None:
        values = {
            "sensitive_like": "SENSITIVE_VALUE_123",
            "placeholder_or_test": "123e4567-e89b-12d3-a456-426614174000",
            "benign_other": "a" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label, candidate in values.items():
                directory = root / label
                directory.mkdir()
                (directory / "fixture.txt").write_text(
                    f"fixture_value = {candidate}", encoding="utf-8"
                )
            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = run(
                ["--root", str(root), "--as-corpus", "--feature-audit"], stdout, stderr
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        result = json.loads(stdout.getvalue())
        audit = result["feature_audit"]
        self.assertEqual(audit["contract_version"], "feature-audit-001")
        self.assertEqual(audit["feature_schema_version"], "features-001")
        self.assertEqual(audit["records"], 3)
        self.assertEqual(audit["non_sensitive_records"], 2)
        self.assertEqual(
            audit["class_counts"],
            {"sensitive_like": 1, "placeholder_or_test": 1, "benign_other": 1},
        )
        uuid = audit["indicator_activations"]["is_uuid_like"]
        self.assertEqual(uuid["non_sensitive"], {
            "records": 2,
            "activations": 1,
            "activation_rate": 0.5,
        })
        self.assertIn("candidate_entropy_bits_per_byte", audit["feature_statistics"])
        self.assertNotIn("fixture.txt", stdout.getvalue())
        self.assertNotIn("SENSITIVE_VALUE_123", stdout.getvalue())
        self.assertNotIn("123e4567-e89b-12d3-a456-426614174000", stdout.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run(["--root", "/not-used", "--feature-audit"], stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "feature audit requires --as-corpus\n")
