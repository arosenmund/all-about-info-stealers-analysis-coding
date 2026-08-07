"""Folder-derived corpus annotations for the versioned ``corpus-001`` POC.

Folder labels are ground truth for training/evaluation corpus construction.
They are deliberately not prediction features for arbitrary scan targets.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Final

from ..stage_00_authorization.contracts import PRIMARY_CLASSES
from ..stage_01_filesystem_crawl.crawl import CRAWL_CONTRACT_VERSION, CrawlResult


CORPUS_CONTRACT_VERSION: Final = "corpus-001"


@dataclass(frozen=True)
class CorpusContractError(ValueError):
    """Sanitized corpus-layout failure that never echoes a relative path."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CorpusItem:
    """One in-memory collected document with folder-derived ground truth."""

    document_id: str
    primary_label: str
    artifact_family: str | None
    text: str
    byte_length: int


@dataclass(frozen=True)
class CorpusSummary:
    """Aggregate label counts safe to use in corpus-quality reports."""

    items: int
    class_counts: tuple[tuple[str, int], ...]

    def class_count(self, label: str) -> int:
        return dict(self.class_counts).get(label, 0)


@dataclass(frozen=True)
class LabeledCorpus:
    """In-memory corpus result; it has no serializer or classifier behavior."""

    contract_version: str
    items: tuple[CorpusItem, ...]
    summary: CorpusSummary


def _raise(code: str, message: str) -> None:
    raise CorpusContractError(code=code, message=message)


def build_labeled_corpus(crawl_result: CrawlResult) -> LabeledCorpus:
    """Derive corpus annotations from the first two root-relative directories.

    A file directly below the corpus root has no label directory and fails
    closed. This prevents accidentally training on unlabeled or mislabeled
    documents. The returned labels must never be used as scan-time predictions.
    """

    if crawl_result.contract_version != CRAWL_CONTRACT_VERSION:
        _raise("contract_mismatch", "crawl result does not use the required crawl contract")

    labeled: list[CorpusItem] = []
    counts: Counter[str] = Counter()
    for item in crawl_result.items:
        parts = item.relative_path.parts
        if len(parts) < 2 or parts[0] not in PRIMARY_CLASSES:
            _raise(
                "unlabeled_path",
                "each corpus file must be below a recognized primary-label directory",
            )
        primary_label = parts[0]
        artifact_family = parts[1] if len(parts) >= 3 else None
        labeled.append(
            CorpusItem(
                document_id=item.document_id,
                primary_label=primary_label,
                artifact_family=artifact_family,
                text=item.text,
                byte_length=item.byte_length,
            )
        )
        counts[primary_label] += 1

    return LabeledCorpus(
        contract_version=CORPUS_CONTRACT_VERSION,
        items=tuple(labeled),
        summary=CorpusSummary(
            items=len(labeled),
            class_counts=tuple((label, counts[label]) for label in PRIMARY_CLASSES),
        ),
    )
