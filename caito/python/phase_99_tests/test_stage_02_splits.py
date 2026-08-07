from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from hybrid_edge_classifier.stage_01_filesystem_crawl import CrawlConfig, crawl_selected_root
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    ALLOCATION_RULE,
    MINIMUM_COMPONENTS_PER_CLASS,
    SPLIT_MANIFEST_CONTRACT_VERSION,
    SPLIT_NAMES,
    SplitContractError,
    analyze_corpus_duplicates,
    build_classifier_inputs,
    build_corpus_manifest,
    build_labeled_corpus,
    build_split_manifest,
    extract_labeled_corpus,
    validate_split_manifest,
)


ROOT = Path(__file__).resolve().parents[2]

_VALUES = {
    "sensitive_like": (
        "AURORA_CEDAR_OPAL_49",
        "BASALT_TIGER_COPPER_75",
        "DRIFTWOOD_LANTERN_SAPPHIRE_18",
        "FALCON_MARBLE_VIOLET_63",
    ),
    "placeholder_or_test": (
        "GARDEN_COMPASS_AMBER_24",
        "HARBOR_WILLOW_QUARTZ_86",
        "IVORY_PEBBLE_CORAL_37",
        "JUNIPER_ANCHOR_SILVER_52",
    ),
    "benign_other": (
        "KETTLE_ORBIT_INDIGO_94",
        "LILAC_BROOK_BRONZE_16",
        "MEADOW_RAVEN_JADE_68",
        "NORTHSTAR_FERN_GOLD_29",
    ),
}


class SplitManifestTests(unittest.TestCase):
    def _clean_inputs_manifest_analysis(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for label, values in _VALUES.items():
            directory = root / label
            directory.mkdir()
            for index, value in enumerate(values, start=1):
                (directory / f"document-{index}.txt").write_text(
                    f"fixture_value = {value}\n", encoding="utf-8"
                )
        # The extra document creates a five-document sensitive class whose
        # repeated value must be joined with document one during allocation.
        (root / "sensitive_like" / "document-5.txt").write_text(
            f"fixture_value = {_VALUES['sensitive_like'][0]}\n", encoding="utf-8"
        )
        crawl = crawl_selected_root(CrawlConfig(root=root))
        inputs = build_classifier_inputs(extract_labeled_corpus(build_labeled_corpus(crawl)))
        manifest = build_corpus_manifest(inputs)
        analysis = analyze_corpus_duplicates(inputs, manifest)
        return temporary, manifest, analysis

    def test_contract_declares_atomic_groups_components_and_cross_label_failure(self) -> None:
        contract = json.loads((ROOT / "contracts/split-002.json").read_text(encoding="utf-8"))

        self.assertEqual(contract["split_manifest_contract_version"], SPLIT_MANIFEST_CONTRACT_VERSION)
        self.assertEqual(
            contract["allocation"]["minimum_isolated_components_per_primary_label"],
            MINIMUM_COMPONENTS_PER_CLASS,
        )
        self.assertIn("Fail without an assignment", contract["isolation"]["cross_label_behavior"])
        self.assertIn("same primary label", contract["isolation"]["artifact_family_rule"])
        self.assertIn("candidate text", contract["exclusions"])

    def test_component_aware_assignment_is_deterministic_balanced_and_redacted(self) -> None:
        temporary, manifest, analysis = self._clean_inputs_manifest_analysis()
        with temporary:
            first = build_split_manifest(manifest, analysis)
            second = build_split_manifest(manifest, analysis)

        self.assertEqual(first, second)
        self.assertEqual(first.contract_version, SPLIT_MANIFEST_CONTRACT_VERSION)
        self.assertEqual(first.allocation_rule, ALLOCATION_RULE)
        self.assertEqual(first.summary.records, 13)
        self.assertEqual(first.summary.groups, 13)
        self.assertEqual(first.summary.components, 12)
        self.assertEqual(tuple(item.split_name for item in first.summary.distributions), SPLIT_NAMES)
        for distribution in first.summary.distributions:
            self.assertEqual(distribution.components, 3)
            self.assertEqual(
                set(label for label, count in distribution.class_counts if count),
                {"sensitive_like", "placeholder_or_test", "benign_other"},
            )

        exact_cluster = next(cluster for cluster in analysis.clusters if cluster.kind == "exact")
        assignments = {item.record_id: item for item in first.items}
        cluster_assignments = [assignments[record_id] for record_id in exact_cluster.record_ids]
        self.assertEqual({item.split_name for item in cluster_assignments}, {"train"})
        self.assertEqual(len({item.isolation_component_id for item in cluster_assignments}), 1)
        self.assertIsNone(validate_split_manifest(first, manifest, analysis))
        self.assertNotIn(_VALUES["sensitive_like"][0], repr(first))

    def test_cross_label_duplicates_fail_closed_without_candidate_echo(self) -> None:
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
            inputs = build_classifier_inputs(
                extract_labeled_corpus(build_labeled_corpus(crawl_selected_root(CrawlConfig(root=root))))
            )
            manifest = build_corpus_manifest(inputs)
            analysis = analyze_corpus_duplicates(inputs, manifest)
            with self.assertRaisesRegex(SplitContractError, "cross-label duplicate review") as raised:
                build_split_manifest(manifest, analysis)

        self.assertNotIn("CROSS_LABEL_SYNTHETIC_VALUE", str(raised.exception))

    def test_each_class_requires_four_isolated_components(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label, values in _VALUES.items():
                directory = root / label
                directory.mkdir()
                for index, value in enumerate(values[:3], start=1):
                    (directory / f"document-{index}.txt").write_text(
                        f"fixture_value = {value}\n", encoding="utf-8"
                    )
            inputs = build_classifier_inputs(
                extract_labeled_corpus(build_labeled_corpus(crawl_selected_root(CrawlConfig(root=root))))
            )
            manifest = build_corpus_manifest(inputs)
            analysis = analyze_corpus_duplicates(inputs, manifest)
            with self.assertRaisesRegex(SplitContractError, "at least four isolated components"):
                build_split_manifest(manifest, analysis)

    def test_validator_rejects_duplicate_component_leakage(self) -> None:
        temporary, manifest, analysis = self._clean_inputs_manifest_analysis()
        with temporary:
            split_manifest = build_split_manifest(manifest, analysis)
            exact_cluster = next(cluster for cluster in analysis.clusters if cluster.kind == "exact")
            items = list(split_manifest.items)
            leaking_record = exact_cluster.record_ids[1]
            index = next(index for index, item in enumerate(items) if item.record_id == leaking_record)
            items[index] = replace(items[index], split_name="validation")
            leaked = replace(split_manifest, items=tuple(items))
            with self.assertRaisesRegex(SplitContractError, "duplicate component crosses"):
                validate_split_manifest(leaked, manifest, analysis)

    def test_same_label_artifact_family_is_atomic_and_cannot_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label, values in _VALUES.items():
                for index, value in enumerate(values, start=1):
                    family = root / label / f"family-{index}"
                    family.mkdir(parents=True)
                    (family / "first.txt").write_text(
                        f"fixture_value = {value}\n", encoding="utf-8"
                    )
                first_family = root / label / "family-1"
                (first_family / "second.txt").write_text(
                    f"fixture_value = {values[0]}_SECOND\n", encoding="utf-8"
                )
            inputs = build_classifier_inputs(
                extract_labeled_corpus(build_labeled_corpus(crawl_selected_root(CrawlConfig(root=root))))
            )
            manifest = build_corpus_manifest(inputs)
            analysis = analyze_corpus_duplicates(inputs, manifest)
            split_manifest = build_split_manifest(manifest, analysis)

        first_family_records = tuple(
            item
            for item in manifest.items
            if item.primary_label == "sensitive_like" and item.artifact_family == "family-1"
        )
        assignments = {item.record_id: item for item in split_manifest.items}
        assigned = tuple(assignments[item.record_id] for item in first_family_records)
        self.assertEqual(len({item.group_id for item in assigned}), 2)
        self.assertEqual(len({item.split_name for item in assigned}), 1)
        self.assertEqual(len({item.isolation_component_id for item in assigned}), 1)

        changed_group = assigned[0].group_id
        original_split = assigned[0].split_name
        other_split = next(name for name in SPLIT_NAMES if name != original_split)
        leaked = replace(
            split_manifest,
            items=tuple(
                replace(item, split_name=other_split) if item.group_id == changed_group else item
                for item in split_manifest.items
            ),
        )
        with self.assertRaisesRegex(SplitContractError, "artifact-family cohort crosses"):
            validate_split_manifest(leaked, manifest, analysis)
