"""Redacted command boundary for the fresh final-evaluation allocation."""

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
)


USAGE = "Usage: phase01-evaluation-allocation --root <explicit-corpus-directory>"


def _write_json(output: TextIO, value: dict[str, object]) -> None:
    output.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    output.write("\n")


def run(arguments: Sequence[str], stdout: TextIO, stderr: TextIO) -> int:
    """Plan a redacted fresh release boundary for one explicit corpus root."""

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
        stderr.write("evaluation allocation base split planning could not be completed\n")
        return 1
    except EvaluationAllocationContractError as error:
        if error.code == "release_holdout_contamination":
            stderr.write("release holdout is not isolated from development data\n")
        else:
            stderr.write("fresh evaluation allocation could not be completed\n")
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
            "evaluation_allocation": {
                "contract_version": allocation.contract_version,
                "base_split_contract_version": allocation.base_split_contract_version,
                "release_holdout_contract_version": allocation.release_holdout_contract_version,
                "records": allocation.summary.records,
                "groups": allocation.summary.groups,
                "components": allocation.summary.components,
                "allocations": {
                    distribution.allocation_name: {
                        "records": distribution.records,
                        "groups": distribution.groups,
                        "components": distribution.components,
                        "class_counts": dict(distribution.class_counts),
                    }
                    for distribution in allocation.summary.distributions
                },
            },
        },
    )
    return 0
