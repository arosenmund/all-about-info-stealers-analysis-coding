"""Redacted command boundary for explicitly requested ``crawl-001`` runs."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from ..stage_01_filesystem_crawl import CrawlConfig, CrawlContractError, crawl_selected_root
from ..stage_03_features import (
    FeatureAuditContractError,
    FeatureContractError,
    audit_deterministic_features,
    extract_deterministic_features,
)
from ..stage_02_ingestion_preprocess import (
    CorpusContractError,
    DuplicateAnalysisContractError,
    SplitContractError,
    analyze_corpus_duplicates,
    build_classifier_inputs,
    build_corpus_manifest,
    build_labeled_corpus,
    build_split_manifest,
    extract_crawl_result,
    extract_labeled_corpus,
    preprocess_classifier_inputs,
)


USAGE = "Usage: phase01-crawl --root <explicit-directory> [--as-corpus] [--extract] [--prepare] [--features] [--feature-audit] [--manifest] [--duplicates] [--splits]"


def _write_json(output: TextIO, value: dict[str, object]) -> None:
    output.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    output.write("\n")


def run(arguments: Sequence[str], stdout: TextIO, stderr: TextIO) -> int:
    """Run one explicitly selected crawl and emit a redacted aggregate summary."""

    if list(arguments) == ["--help"]:
        stdout.write(f"{USAGE}\n")
        return 0

    values = list(arguments)
    as_corpus = "--as-corpus" in values
    splits = "--splits" in values
    duplicates = "--duplicates" in values or splits
    manifest = "--manifest" in values or duplicates
    feature_audit = "--feature-audit" in values
    features = "--features" in values or feature_audit
    prepare = "--prepare" in values or manifest or features
    extract = "--extract" in values or prepare
    values = [
        value
        for value in values
        if value
        not in {
            "--as-corpus",
            "--extract",
            "--prepare",
            "--features",
            "--feature-audit",
            "--manifest",
            "--duplicates",
            "--splits",
        }
    ]
    if len(values) != 2 or values[0] != "--root":
        stderr.write(f"{USAGE}\n")
        return 1
    if (manifest or feature_audit) and not as_corpus:
        requirement = (
            "split planning"
            if splits
            else "duplicate analysis"
            if duplicates
            else "corpus manifest"
            if manifest
            else "feature audit"
        )
        stderr.write(f"{requirement} requires --as-corpus\n")
        return 1

    try:
        crawl_result = crawl_selected_root(CrawlConfig(root=Path(values[1])))
    except CrawlContractError:
        stderr.write("unable to crawl the explicitly selected root\n")
        return 1

    result: dict[str, object] = {
        "crawl_contract_version": crawl_result.contract_version,
        "files_collected": crawl_result.summary.files_collected,
        "bytes_collected": crawl_result.summary.bytes_collected,
        "skipped": dict(crawl_result.summary.skipped),
        "stopped_by_file_limit": crawl_result.summary.stopped_by_file_limit,
    }
    extraction = None
    if as_corpus:
        try:
            corpus = build_labeled_corpus(crawl_result)
        except CorpusContractError:
            stderr.write("selected root does not match the required corpus layout\n")
            return 1
        result["corpus"] = {
            "contract_version": corpus.contract_version,
            "items": corpus.summary.items,
            "class_counts": dict(corpus.summary.class_counts),
        }
        if extract:
            extraction = extract_labeled_corpus(corpus)
    elif extract:
        extraction = extract_crawl_result(crawl_result)

    if extraction is not None:
        result["extraction"] = {
            "contract_version": extraction.contract_version,
            "documents": extraction.summary.documents,
            "candidates": extraction.summary.candidates,
            "kind_counts": dict(extraction.summary.kind_counts),
        }
    if prepare and extraction is not None:
        classifier_inputs = build_classifier_inputs(extraction)
        preprocessed = preprocess_classifier_inputs(classifier_inputs)
        result["classifier_input"] = {
            "contract_version": classifier_inputs.contract_version,
            "preprocessing_version": preprocessed.preprocessing_version,
            "extracted": classifier_inputs.summary.extracted,
            "prepared": classifier_inputs.summary.prepared,
            "rejected": classifier_inputs.summary.rejected,
            "rejection_codes": dict(classifier_inputs.summary.rejection_codes),
        }
        feature_result = None
        if features:
            try:
                feature_result = extract_deterministic_features(preprocessed)
            except FeatureContractError:
                stderr.write("deterministic feature extraction could not be completed\n")
                return 1
            result["features"] = {
                "feature_schema_version": feature_result.feature_schema_version,
                "preprocessing_version": feature_result.preprocessing_version,
                "records": feature_result.summary.records,
                "feature_count": feature_result.summary.feature_count,
                "indicator_counts": dict(feature_result.summary.indicator_counts),
            }
        if feature_audit and feature_result is not None:
            try:
                audit = audit_deterministic_features(feature_result)
            except FeatureAuditContractError:
                stderr.write("deterministic feature audit could not be completed\n")
                return 1
            result["feature_audit"] = {
                "contract_version": audit.contract_version,
                "feature_schema_version": audit.feature_schema_version,
                "records": audit.summary.records,
                "feature_count": audit.summary.feature_count,
                "non_sensitive_records": audit.summary.non_sensitive_records,
                "class_counts": dict(audit.summary.class_counts),
                "feature_statistics": {
                    distribution.feature_name: {
                        statistics.primary_label: {
                            "records": statistics.records,
                            "mean": statistics.mean,
                            "minimum": statistics.minimum,
                            "maximum": statistics.maximum,
                        }
                        for statistics in distribution.label_statistics
                    }
                    for distribution in audit.distributions
                },
                "indicator_activations": {
                    indicator.feature_name: {
                        "by_label": {
                            activation.primary_label: {
                                "records": activation.records,
                                "activations": activation.activations,
                                "activation_rate": activation.activation_rate,
                            }
                            for activation in indicator.label_activations
                        },
                        "non_sensitive": {
                            "records": indicator.non_sensitive.records,
                            "activations": indicator.non_sensitive.activations,
                            "activation_rate": indicator.non_sensitive.activation_rate,
                        },
                    }
                    for indicator in audit.indicators
                },
            }
        if manifest:
            corpus_manifest = build_corpus_manifest(classifier_inputs)
            result["corpus_manifest"] = {
                "contract_version": corpus_manifest.contract_version,
                "preprocessing_version": corpus_manifest.preprocessing_version,
                "grouping_rule": corpus_manifest.grouping_rule,
                "records": corpus_manifest.summary.records,
                "groups": corpus_manifest.summary.groups,
                "class_counts": dict(corpus_manifest.summary.class_counts),
                "artifact_family_count": corpus_manifest.summary.artifact_family_count,
                "classifier_input_rejections": corpus_manifest.summary.classifier_input_rejections,
                "rejection_codes": dict(corpus_manifest.summary.rejection_codes),
            }
            duplicate_analysis = None
            if duplicates:
                try:
                    duplicate_analysis = analyze_corpus_duplicates(classifier_inputs, corpus_manifest)
                except DuplicateAnalysisContractError:
                    stderr.write("duplicate analysis could not be completed\n")
                    return 1
                result["duplicate_analysis"] = {
                    "contract_version": duplicate_analysis.contract_version,
                    "metric": duplicate_analysis.metric,
                    "near_duplicate_threshold": duplicate_analysis.near_duplicate_threshold,
                    "near_duplicate_minimum_characters": (
                        duplicate_analysis.near_duplicate_minimum_characters
                    ),
                    "records": duplicate_analysis.summary.records,
                    "exact": {
                        "clusters": duplicate_analysis.summary.exact.clusters,
                        "records": duplicate_analysis.summary.exact.records,
                        "cross_group_clusters": (
                            duplicate_analysis.summary.exact.cross_group_clusters
                        ),
                        "cross_group_records": (
                            duplicate_analysis.summary.exact.cross_group_records
                        ),
                        "cross_label_clusters": (
                            duplicate_analysis.summary.exact.cross_label_clusters
                        ),
                        "cross_label_records": (
                            duplicate_analysis.summary.exact.cross_label_records
                        ),
                    },
                    "near": {
                        "clusters": duplicate_analysis.summary.near.clusters,
                        "records": duplicate_analysis.summary.near.records,
                        "cross_group_clusters": (
                            duplicate_analysis.summary.near.cross_group_clusters
                        ),
                        "cross_group_records": (
                            duplicate_analysis.summary.near.cross_group_records
                        ),
                        "cross_label_clusters": (
                            duplicate_analysis.summary.near.cross_label_clusters
                        ),
                        "cross_label_records": (
                            duplicate_analysis.summary.near.cross_label_records
                        ),
                    },
                }
            if splits and duplicate_analysis is not None:
                try:
                    split_manifest = build_split_manifest(corpus_manifest, duplicate_analysis)
                except SplitContractError as error:
                    if error.code == "cross_label_conflict":
                        stderr.write("split planning requires cross-label duplicate review\n")
                    else:
                        stderr.write("split planning could not be completed\n")
                    return 1
                result["split_manifest"] = {
                    "contract_version": split_manifest.contract_version,
                    "allocation_rule": split_manifest.allocation_rule,
                    "ratios": dict(split_manifest.ratios),
                    "records": split_manifest.summary.records,
                    "groups": split_manifest.summary.groups,
                    "components": split_manifest.summary.components,
                    "splits": {
                        distribution.split_name: {
                            "records": distribution.records,
                            "groups": distribution.groups,
                            "components": distribution.components,
                            "class_counts": dict(distribution.class_counts),
                        }
                        for distribution in split_manifest.summary.distributions
                    },
                }

    _write_json(stdout, result)
    return 0
