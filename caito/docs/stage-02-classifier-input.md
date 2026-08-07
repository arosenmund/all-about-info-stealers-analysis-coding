# Stage 02 Classifier Input Bridge (`classifier-input-002`)

## Purpose

`classifier-input-002` is the Python-first, in-memory boundary between
`extract-002` candidate/context records and the model-facing canonical
preprocessing code. It provides a single explicit path for extracted file
contents to reach later deterministic features and models without changing the
frozen explicit-JSONL `input-001` schema.

The machine-readable contract is
[`contracts/classifier-input-002.json`](../contracts/classifier-input-002.json).

## Mapping

For every `extract-002` record, the bridge:

1. Derives `classifier-input-002-<origin-record-id>` as a stable in-memory
   record ID and retains the extraction record ID for later decision linkage.
2. Validates the candidate and context against the existing `preprocess-001`
   transport limits: 4,096 candidate bytes; 128-byte key; 2,048-byte line;
   four 512-byte nearby lines on each side; and 8,192 total context bytes.
3. Preserves `primary_label` and `artifact_family` only when they came from a
   `corpus-001` input. Ordinary target scans remain unlabelled.
4. Runs the same `preprocess-001` byte-buffer and candidate-redacted semantic
   context-envelope logic used by the Phase 0 explicit-record path.

It does not fabricate the legacy `input-001` `source` object. Extraction kind
and optional corpus annotations stay in process memory for future data/evidence
work; their external reporting format remains a later decision.

## Rejections and reporting

An extracted candidate that exceeds a transport limit or whose normalized
context would exceed the `preprocess-001` limit is rejected individually. The
batch continues and keeps only the internal origin-record ID and a sanitized
rejection code. The CLI may report aggregate prepared/rejected counts and code
totals; it never reports paths, record IDs, candidates, context, annotations,
or preprocessing envelopes.

Run the full aggregate-only local handoff with:

```text
phase_01_crawl.py --root <directory> --prepare
```

Add `--as-corpus` only for a root using the `corpus-001` folder layout.

## Scope boundary

This POC prepares records; it does not classify, persist records, create a
decision report, or add a Rust collector/runtime path. The next Phase 1 work is
to populate the folder-labelled corpus, produce leakage-safe splits from the
initial `corpus-manifest-002` POC, and build the deterministic-feature baseline.
