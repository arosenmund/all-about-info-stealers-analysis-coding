# Deterministic Feature Contract (`features-001`)

## Purpose

`features-001` is the Python reference for interpretable, model-free evidence
over prepared `classifier-input-002` records. It is a feature extractor, not a
classifier: it does not select a class, change an annotation, or apply policy.

The machine-readable schema is
[`contracts/features-001.json`](../contracts/features-001.json).

## Ordered feature groups

| Group | Features |
| --- | --- |
| Candidate size | UTF-8 byte length; length divided by the 4,096-byte transport maximum |
| Byte distribution | Shannon entropy; ASCII letter/digit/whitespace/punctuation ratios; non-ASCII ratio |
| Diversity and repetition | Unique-byte ratio; longest repeated-byte-run ratio |
| Structure | Delimiter ratio; UUID-like, hexadecimal-digest-like, and base64-like shape indicators; assignment-extraction indicator |
| Context | Placeholder/test-language indicator in the key or nearby lines; exact candidate occurrence in nearby context, excluding the candidate-bearing primary line |

The feature vector is exactly the schema order and uses finite `float64`
values. Its documented ranges are checked by the Python reference. Changing a
name, order, formula, range, or context rule requires a new feature schema
version and new golden fixtures.

## Privacy

Candidate bytes and context are inspected only in process. Feature records
retain record/document IDs, optional corpus annotations, and numeric values;
they have no candidate or context serializer. The CLI reports only aggregate
counts and numeric statistics.

## Run it

```sh
make run-features
make run-feature-audit
make feature-goldens
```

The current corpus produces 1,852 vectors with 17 features. Its aggregate
indicator counts are 25 UUID-like, 32 digest-like, 570 base64-like, 1,441
assignment-extracted, 542 placeholder-language, and 100 nearby-occurrence
records. These are coverage observations, not quality or classification
metrics.

`make run-feature-audit` stratifies all 17 features by folder label and
reports boolean activation rates for each class plus a combined non-sensitive
review rate. Its current findings are recorded in
[the feature-audit report](feature-audit.md): UUID-, digest-, and base64-like
features are not positive `sensitive_like` rules in this corpus.

## Frozen parity handoff

The owner approved the audited `features-001` semantics on 2026-08-07.
`features-golden-001` now generates six synthetic source cases into
non-reversible numeric feature vectors with a declared absolute tolerance of
`1e-12`. The goldens contain no candidate or context text.

The Rust `classifier-core::features` implementation now matches all frozen
vectors within that tolerance and fails closed on a feature-schema version or
order mismatch. Python remains the golden generator and feature-definition
source of truth; any semantic change requires a new feature schema and goldens.
