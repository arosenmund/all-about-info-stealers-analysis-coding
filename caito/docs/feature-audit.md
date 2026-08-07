# Deterministic Feature Audit (`feature-audit-001`)

## Purpose

`feature-audit-001` reviews the current corpus-labelled `features-001` vectors
without exposing candidate text, context, file paths, record IDs, or document
IDs. It reports every feature's mean/minimum/maximum by primary label and each
boolean feature's activation rate by label.

The combined `non_sensitive` rate covers `placeholder_or_test` and
`benign_other`. It is a false-positive review proxy, not a classifier
false-positive rate: deterministic features do not make class decisions.

The machine-readable contract is
[`contracts/feature-audit-001.json`](../contracts/feature-audit-001.json).

## Run it

```sh
make run-feature-audit
```

`--feature-audit` implies feature extraction and requires `--as-corpus`, so
the review cannot run on an unlabelled scan target. It keeps all vectors and
statistics in memory and emits aggregate JSON only.

## Current corpus review

Run on 2026-08-07 against the current folder-labelled corpus:

| Candidate label | Records |
| --- | ---: |
| `sensitive_like` | 910 |
| `placeholder_or_test` | 480 |
| `benign_other` | 462 |

The corpus is materially class-imbalanced, so these observations guide review
and baseline design; they are not quality claims about a future scanner.

| Boolean feature | Sensitive-like | Placeholder/test | Benign/other | Non-sensitive combined | Review finding |
| --- | ---: | ---: | ---: | ---: | --- |
| UUID-like | 1.21% | 0.83% | 2.16% | 14 / 942 (1.49%) | Not a positive `sensitive_like` rule; more common in benign/other records. |
| Hex-digest-like | 1.98% | 1.46% | 1.52% | 14 / 942 (1.49%) | Not a positive `sensitive_like` rule; common enough in both non-sensitive classes to require learned weighting. |
| Base64-like | 11.10% | 80.42% | 17.97% | 469 / 942 (49.79%) | Not a positive `sensitive_like` rule; especially prevalent in placeholder/test records. |
| Assignment extraction | 76.81% | 78.54% | 79.00% | 742 / 942 (78.77%) | Extraction structure is broad corpus evidence, not a decision rule. |
| Placeholder language | 12.75% | 73.33% | 16.02% | 426 / 942 (45.22%) | Useful candidate evidence for the placeholder/test class, but not conclusive. |
| Candidate nearby | 10.33% | 0.21% | 1.08% | 6 / 942 (0.64%) | Potentially discriminative in this corpus; verify on held-out template groups to rule out template effects. |

Selected continuous-feature means were also reviewed: candidate byte length is
38.21 (`sensitive_like`), 43.73 (`placeholder_or_test`), and 50.17
(`benign_other`); entropy is 3.68, 4.04, and 4.03 bits per byte respectively.
These overlapping distributions reinforce that no individual morphological
feature should be turned into a label decision.

## Decision and completed handoff

No feature rule or label was changed by this audit. Keep all 17 values as
interpretable inputs for the grouped Python baseline, with regularization and
held-out evaluation deciding their weight and direction. In particular, do
not treat UUID-, digest-, or base64-like activation as a `sensitive_like`
shortcut.

The owner approved the current feature meanings and context vocabulary on
2026-08-07. Python then froze six synthetic `features-golden-001` vectors with
an absolute tolerance of `1e-12`, and the matching Rust feature extractor now
passes all parity vectors and rejects schema/order mismatches. The next work is
corpus and baseline review, not a new feature rule.
