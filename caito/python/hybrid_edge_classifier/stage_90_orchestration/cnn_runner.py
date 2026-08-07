"""Redacted command boundary for the Phase 2 FP32 byte-CNN POC."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

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
from ..stage_04_cnn import (
    CnnContractError,
    build_cnn_dataset,
    fit_and_evaluate_cnn,
    select_cnn_development_inputs,
)

from phase_01_evaluation import EvaluationAllocationContractError, build_evaluation_allocation


USAGE = "Usage: phase02-cnn --root <explicit-corpus-directory>"


def _write_json(output: TextIO, value: dict[str, object]) -> None:
    output.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    output.write("\n")


def run(arguments: Sequence[str], stdout: TextIO, stderr: TextIO) -> int:
    """Run the fixed FP32 CNN POC on one explicit lab corpus root."""

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
        dataset = build_cnn_dataset(prepared, allocation)
        report = fit_and_evaluate_cnn(dataset)
    except CrawlContractError:
        stderr.write("unable to crawl the explicitly selected root\n")
        return 1
    except CorpusContractError:
        stderr.write("selected root does not match the required corpus layout\n")
        return 1
    except DuplicateAnalysisContractError:
        stderr.write("duplicate analysis could not be completed\n")
        return 1
    except SplitContractError:
        stderr.write("CNN base split planning could not be completed\n")
        return 1
    except EvaluationAllocationContractError:
        stderr.write("CNN evaluation allocation could not be completed\n")
        return 1
    except CnnContractError:
        stderr.write("FP32 CNN POC could not be completed\n")
        return 1

    _write_json(
        stdout,
        {
            "crawl_contract_version": crawl.contract_version,
            "files_collected": crawl.summary.files_collected,
            "skipped": dict(crawl.summary.skipped),
            "evaluation_allocation_contract_version": allocation.contract_version,
            "cnn": report.as_mapping(),
        },
    )
    return 0
