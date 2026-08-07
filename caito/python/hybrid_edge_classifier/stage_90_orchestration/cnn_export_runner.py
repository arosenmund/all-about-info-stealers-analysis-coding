"""Redacted artifact-factory command for `cnn-export-003`."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from phase_01_evaluation import EvaluationAllocationContractError, build_evaluation_allocation

from ..stage_01_filesystem_crawl import CrawlConfig, CrawlContractError, crawl_selected_root
from ..stage_02_ingestion_preprocess import (
    CorpusContractError,
    DuplicateAnalysisContractError,
    SplitContractError,
    analyze_corpus_duplicates,
    build_classifier_inputs,
    build_corpus_manifest,
    build_labeled_corpus,
    build_split_manifest,
    extract_labeled_corpus,
    preprocess_classifier_inputs,
)
from ..stage_02_ingestion_preprocess.canonical import candidate_byte_ids
from ..stage_04_cnn import (
    CnnContractError,
    OnnxExportContractError,
    build_cnn_dataset,
    export_fp32_onnx,
    fit_cnn_model,
    select_cnn_development_inputs,
)


USAGE = "Usage: phase02-export-cnn --root <explicit-corpus-directory>"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _write_json(output: TextIO, value: dict[str, object]) -> None:
    output.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    output.write("\n")


def _synthetic_fixture_buffers() -> tuple[tuple[int, ...], ...]:
    fixture_path = PROJECT_ROOT / "tests/fixtures/synthetic/records-001.jsonl"
    try:
        records = tuple(json.loads(line)["record"] for line in fixture_path.read_text(encoding="utf-8").splitlines() if line)
    except (OSError, UnicodeDecodeError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise OnnxExportContractError("fixture_read", "synthetic ONNX fixture inputs are unavailable") from error
    buffers = tuple(candidate_byte_ids(record["candidate"]) for record in records)
    if not buffers:
        raise OnnxExportContractError("fixture_read", "synthetic ONNX fixture inputs are unavailable")
    return buffers


def run(arguments: Sequence[str], stdout: TextIO, stderr: TextIO) -> int:
    """Create the FP32 ONNX artifact only after local parity passes."""

    if list(arguments) == ["--help"]:
        stdout.write(f"{USAGE}\n")
        return 0
    if len(arguments) != 2 or arguments[0] != "--root":
        stderr.write(f"{USAGE}\n")
        return 1
    try:
        crawl = crawl_selected_root(CrawlConfig(root=Path(arguments[1])))
        corpus = build_labeled_corpus(crawl)
        inputs = build_classifier_inputs(extract_labeled_corpus(corpus))
        manifest = build_corpus_manifest(inputs)
        duplicates = analyze_corpus_duplicates(inputs, manifest)
        base = build_split_manifest(manifest, duplicates)
        allocation = build_evaluation_allocation(manifest, duplicates, base)
        prepared = preprocess_classifier_inputs(select_cnn_development_inputs(inputs, allocation))
        model = fit_cnn_model(build_cnn_dataset(prepared, allocation))
        report = export_fp32_onnx(
            model,
            _synthetic_fixture_buffers(),
            PROJECT_ROOT / "artifacts/cnn",
        )
    except CrawlContractError:
        stderr.write("unable to crawl the explicitly selected root\n")
        return 1
    except CorpusContractError:
        stderr.write("selected root does not match the required corpus layout\n")
        return 1
    except (DuplicateAnalysisContractError, SplitContractError, EvaluationAllocationContractError):
        stderr.write("CNN export evaluation preparation could not be completed\n")
        return 1
    except CnnContractError:
        stderr.write("CNN export training could not be completed\n")
        return 1
    except OnnxExportContractError:
        stderr.write("FP32 ONNX export could not be completed\n")
        return 1

    _write_json(
        stdout,
        {
            "contract_version": report.contract_version,
            "fixture_count": report.fixture_count,
            "max_absolute_logit_drift": report.max_absolute_logit_drift,
            "class_decisions_identical": report.class_decisions_identical,
            "operator_types": list(report.operator_types),
        },
    )
    return 0
