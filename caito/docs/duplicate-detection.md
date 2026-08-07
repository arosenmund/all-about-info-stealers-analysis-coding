# Duplicate Detection Contract (`duplicate-001`)

## Purpose

`duplicate-001` is the first in-memory Phase 1 corpus-quality check. It
compares the candidates associated with a labeled `corpus-manifest-002` and
its matching `classifier-input-002` records, then identifies exact and
potential near-duplicate components for later split planning.

The machine-readable contract is
[`contracts/duplicate-001.json`](../contracts/duplicate-001.json).

## Comparison rules

- Exact duplicates have equal Unicode NFC-normalized candidate values.
- Near-duplicate comparisons are case-sensitive and use the deterministic
  `sequence-matcher-nfc-001` ratio on NFC-normalized values.
- A candidate must contain at least 12 Unicode characters and score at least
  `0.92` to form a non-exact near-duplicate edge.
- A near-duplicate cluster is a connected component of those pairwise edges.
- The analysis accepts at most 4,096 records and fails without a partial report
  above that bound. This keeps the initial pairwise POC bounded while covering
  the current development corpus plus `release-holdout-001`; a future,
  separately specified algorithm is required before raising the limit again.

The rule is intentionally a conservative lexical POC. It detects potential
leakage and label conflicts; it does not make a classification, relabel a
candidate, remove data, or assign a split.

## Privacy and output

Candidate text is used only while comparing records in process. The returned
in-memory clusters retain only kind plus record, document-group, and
primary-label IDs. The command boundary exposes only aggregate counts:

- exact and near cluster/record counts;
- components crossing more than one `group-001` document group; and
- components containing more than one primary label.

It never emits candidates, context, paths, fingerprints, or serialized
cluster records.

Cross-group components are split-isolation evidence. Cross-label components
are annotation conflicts or deliberate taxonomy overlaps that require review;
`duplicate-001` never resolves either automatically.

## Run it

```text
phase_01_crawl.py --root <corpus-root> --as-corpus --duplicates
```

or:

```text
make run-duplicates CRAWL_ROOT=<corpus-root>
```

`--duplicates` implies preparation and `corpus-manifest-002`, and requires the
`corpus-001` folder layout.

## Next work

[`split-002`](split-planning.md) now joins document groups, duplicate
components, and same-label artifact-family cohorts during deterministic
allocation. It fails closed while cross-label components remain; project,
language, chronology, and explicitly annotated template grouping remain later
owner-approved rules.
