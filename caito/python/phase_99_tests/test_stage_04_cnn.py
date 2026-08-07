from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from phase_01_evaluation import (
    EVALUATION_ALLOCATION_CONTRACT_VERSION,
    EvaluationAllocation,
    EvaluationAllocationItem,
    EvaluationAllocationSummary,
)
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    CLASSIFIER_INPUT_CONTRACT_VERSION,
    ClassifierInputContext,
    ClassifierInputRecord,
    ClassifierInputResult,
    ClassifierInputSummary,
)
from hybrid_edge_classifier.stage_04_cnn import (
    CNN_CONTRACT_VERSION,
    CnnConfig,
    CnnContractError,
    CnnDataset,
    CnnExample,
    export_fp32_onnx,
    fit_cnn_model,
    fit_and_evaluate_cnn,
    select_cnn_development_inputs,
)


ROOT = Path(__file__).resolve().parents[2]
_HAS_TORCH = importlib.util.find_spec("torch") is not None


class CnnContractTests(unittest.TestCase):
    def test_machine_readable_contract_freezes_development_and_parity_boundaries(self) -> None:
        contract = json.loads((ROOT / "contracts/cnn-001.json").read_text(encoding="utf-8"))

        self.assertEqual(contract["contract_version"], CNN_CONTRACT_VERSION)
        self.assertEqual(contract["input"]["shape"], ["batch", 512])
        self.assertEqual(contract["training"]["partition"], "train only")
        self.assertIn("release_holdout", contract["release_holdout"])
        self.assertEqual(contract["onnx_parity"]["pytorch_to_onnx_max_absolute_logit_drift"], 0.00001)

    def test_int8_contract_preserves_the_release_holdout_and_relaxed_engineering_gate(self) -> None:
        contract = json.loads((ROOT / "contracts/cnn-int8-001.json").read_text(encoding="utf-8"))

        self.assertEqual(contract["contract_version"], "cnn-int8-001")
        self.assertEqual(contract["calibration"]["partition"], "train only")
        self.assertEqual(contract["calibration"]["format"], "QDQ")
        self.assertEqual(contract["evaluation"]["excluded"], ["historical_test", "release_holdout"])
        self.assertEqual(contract["engineering_gate"]["validation_macro_f1_maximum_drop"], 0.10)
        self.assertEqual(contract["engineering_gate"]["validation_top_class_agreement_minimum"], 0.80)

    def test_release_and_historical_records_do_not_enter_cnn_preprocessing(self) -> None:
        def input_record(record_id: str) -> ClassifierInputRecord:
            return ClassifierInputRecord(
                contract_version=CLASSIFIER_INPUT_CONTRACT_VERSION,
                record_id=record_id,
                origin_record_id=record_id,
                document_id=f"document-{record_id}",
                extraction_kind="assignment",
                candidate=f"synthetic-{record_id}",
                context=ClassifierInputContext(key="key", line="key=value", before=(), after=()),
                primary_label="sensitive_like",
                artifact_family="synthetic-family",
            )

        inputs = ClassifierInputResult(
            contract_version=CLASSIFIER_INPUT_CONTRACT_VERSION,
            items=(input_record("train"), input_record("historical"), input_record("release")),
            rejections=(),
            summary=ClassifierInputSummary(3, 3, 0, ()),
        )
        allocation = EvaluationAllocation(
            contract_version=EVALUATION_ALLOCATION_CONTRACT_VERSION,
            corpus_manifest_contract_version="corpus-manifest-002",
            duplicate_analysis_contract_version="duplicate-001",
            base_split_contract_version="split-002",
            release_holdout_contract_version="release-holdout-001",
            items=(
                EvaluationAllocationItem("train", "group-train", "component-train", "sensitive_like", "train"),
                EvaluationAllocationItem("historical", "group-historical", "component-historical", "sensitive_like", "historical_test"),
                EvaluationAllocationItem("release", "group-release", "component-release", "sensitive_like", "release_holdout"),
            ),
            summary=EvaluationAllocationSummary(3, 3, 3, ()),
        )

        selected = select_cnn_development_inputs(inputs, allocation)

        self.assertEqual(tuple(item.record_id for item in selected.items), ("train",))
        self.assertEqual(selected.summary.prepared, 1)


@unittest.skipUnless(_HAS_TORCH, "requires the pinned Phase 2 PyTorch environment")
class CnnReferenceTests(unittest.TestCase):
    @staticmethod
    def _example(label: str, allocation_name: str, ordinal: int) -> CnnExample:
        byte = {"sensitive_like": 65, "placeholder_or_test": 66, "benign_other": 67}[label]
        return CnnExample(
            record_id=f"record-{allocation_name}-{label}-{ordinal}",
            group_id=f"group-{allocation_name}-{label}-{ordinal}",
            primary_label=label,
            allocation_name=allocation_name,
            byte_ids=(byte,) * 32 + (256,) * 480,
        )

    def _dataset(self) -> CnnDataset:
        examples = tuple(
            self._example(label, allocation_name, ordinal)
            for allocation_name in ("train", "validation", "calibration")
            for ordinal in range(1, 3)
            for label in ("sensitive_like", "placeholder_or_test", "benign_other")
        )
        return CnnDataset(
            contract_version="cnn-001",
            preprocessing_version="preprocess-001",
            class_order=("sensitive_like", "placeholder_or_test", "benign_other"),
            examples=examples,
        )

    def test_fixed_reference_trains_and_reports_development_aggregates_only(self) -> None:
        config = CnnConfig(epochs=1, batch_size=3, dropout=0.0)
        report = fit_and_evaluate_cnn(self._dataset(), config)

        self.assertEqual(report.contract_version, "cnn-001")
        self.assertEqual(report.train_records, 6)
        self.assertEqual(
            tuple(metrics.allocation_name for metrics in report.split_metrics),
            ("validation", "calibration"),
        )
        self.assertEqual(tuple(metrics.records for metrics in report.split_metrics), (6, 6))
        self.assertNotIn("byte_ids", repr(report))

    def test_non_development_examples_fail_closed(self) -> None:
        dataset = CnnDataset(
            contract_version="cnn-001",
            preprocessing_version="preprocess-001",
            class_order=("sensitive_like", "placeholder_or_test", "benign_other"),
            examples=(self._example("sensitive_like", "release_holdout", 1),),
        )
        with self.assertRaisesRegex(CnnContractError, "non-development allocation"):
            fit_and_evaluate_cnn(dataset, CnnConfig(epochs=1, batch_size=1, dropout=0.0))

    def test_fp32_export_publishes_only_after_onnx_runtime_parity(self) -> None:
        config = CnnConfig(epochs=1, batch_size=3, dropout=0.0)
        dataset = self._dataset()
        model = fit_cnn_model(dataset, config)
        fixtures = tuple(example.byte_ids for example in dataset.examples[:3])
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report = export_fp32_onnx(model, fixtures, directory)
            manifest = json.loads((directory / "cnn-fp32-003.manifest.json").read_text(encoding="utf-8"))
            golden = (directory / "cnn-fp32-003.golden.json").read_text(encoding="utf-8")

        self.assertEqual(report.contract_version, "cnn-export-003")
        self.assertTrue(report.class_decisions_identical)
        self.assertLessEqual(report.max_absolute_logit_drift, 1e-5)
        self.assertEqual(manifest["model_sha256"], report.model_sha256)
        self.assertEqual(manifest["class_order"], ["sensitive_like", "placeholder_or_test", "benign_other"])
        self.assertEqual(manifest["preprocessing_version"], "preprocess-001")
        self.assertEqual(manifest["input_shape"], ["batch", 512])
        self.assertEqual(manifest["input_dtype"], "int64")
        self.assertNotIn("byte_ids", golden)
