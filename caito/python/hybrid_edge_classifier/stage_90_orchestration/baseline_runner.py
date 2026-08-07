"""Redacted command boundary for the Python-only grouped `baseline-003` POC."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from phase_01_baseline import (
    BaselineContractError,
    build_baseline_dataset,
    fit_and_evaluate_baseline,
)

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


USAGE = "Usage: phase01-baseline --root <explicit-corpus-directory>"


def _write_json(output: TextIO, value: dict[str, object]) -> None:
    output.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    output.write("\n")


def run(arguments: Sequence[str], stdout: TextIO, stderr: TextIO) -> int:
    """Train and evaluate only against an explicit folder-labelled lab corpus."""

    if list(arguments) == ["--help"]:
        stdout.write(f"{USAGE}\n")
        return 0
    if len(arguments) != 2 or arguments[0] != "--root":
        stderr.write(f"{USAGE}\n")
        return 1
    try:
        crawl = crawl_selected_root(CrawlConfig(root=Path(arguments[1])))
        corpus = build_labeled_corpus(crawl)
        extraction = extract_labeled_corpus(corpus)
        inputs = build_classifier_inputs(extraction)
        preprocessed = preprocess_classifier_inputs(inputs)
        manifest = build_corpus_manifest(inputs)
        duplicates = analyze_corpus_duplicates(inputs, manifest)
        split_manifest = build_split_manifest(manifest, duplicates)
        dataset = build_baseline_dataset(preprocessed, split_manifest)
        report = fit_and_evaluate_baseline(dataset)
    except CrawlContractError:
        stderr.write("unable to crawl the explicitly selected root\n")
        return 1
    except CorpusContractError:
        stderr.write("selected root does not match the required corpus layout\n")
        return 1
    except DuplicateAnalysisContractError:
        stderr.write("duplicate analysis could not be completed\n")
        return 1
    except SplitContractError as error:
        if error.code == "cross_label_conflict":
            stderr.write("baseline requires cross-label duplicate review\n")
        else:
            stderr.write("baseline split planning could not be completed\n")
        return 1
    except BaselineContractError:
        stderr.write("baseline training could not be completed\n")
        return 1

    _write_json(
        stdout,
        {
            "crawl_contract_version": crawl.contract_version,
            "files_collected": crawl.summary.files_collected,
            "skipped": dict(crawl.summary.skipped),
            "corpus": {
                "contract_version": corpus.contract_version,
                "items": corpus.summary.items,
                "class_counts": dict(corpus.summary.class_counts),
            },
            "extraction": {
                "contract_version": extraction.contract_version,
                "documents": extraction.summary.documents,
                "candidates": extraction.summary.candidates,
                "kind_counts": dict(extraction.summary.kind_counts),
            },
            "split_manifest": {
                "contract_version": split_manifest.contract_version,
                "records": split_manifest.summary.records,
                "groups": split_manifest.summary.groups,
                "components": split_manifest.summary.components,
            },
            "baseline": report.as_mapping(),
        },
    )
    return 0
