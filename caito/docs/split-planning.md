# Split Planning Contract (`split-002`)

## Purpose

`split-002` creates a deterministic, in-memory plan for the four Phase 1
partitions: train, validation, calibration, and test. It consumes a labeled
`corpus-manifest-002` plus its matching `duplicate-001` analysis; it does not
write a dataset artifact.

The machine-readable contract is
[`contracts/split-002.json`](../contracts/split-002.json). `split-001` remains
the historical document/duplicate-only POC.

## Isolation rules

Every `group-001` document group is atomic. In addition, all groups connected
by an exact or near-duplicate component are joined into one isolation
component and assigned to one split. This prevents the baseline from training
on a duplicate or near duplicate of a candidate held out for evaluation.

`split-002` also joins all documents with the same primary label and
corpus-derived artifact family. This is an explicit template proxy based on
the folder-labelled corpus layout. It is evaluation metadata only: it never
becomes a scanner feature or a scan-time prediction rule. A document without
an artifact-family directory retains its document/duplicate-only boundary.

The planner fails closed if any duplicate component crosses primary labels. It
does not select a label, omit a record, or assign conflicting records to a
split. The corpus owner must review and correct or deliberately retain those
taxonomy overlaps first.

## Deterministic allocation

The initial POC uses these target ratios:

| Split | Target |
| --- | ---: |
| Train | 70% |
| Validation | 10% |
| Calibration | 10% |
| Test | 10% |

Each class must have at least four isolated components. Components are sorted
deterministically by candidate count and group ID, one is seeded into each
split, and the remaining components are placed in the split with the lowest
ratio-adjusted candidate count. The result balances at the component boundary;
it does not split a group merely to match a row-count ratio.

## Privacy and output

In-memory assignments retain only record ID, group ID, primary label, split
name, and an opaque isolation-component ID. The command reports only aggregate
record/group/component/class counts. It never emits candidates, context, paths,
fingerprints, or the assignment membership of an individual record.

## Run it

```text
phase_01_crawl.py --root <corpus-root> --as-corpus --splits
```

or:

```text
make run-splits CRAWL_ROOT=<corpus-root>
```

`--splits` implies duplicate analysis, manifest construction, preparation, and
extraction. It requires the `corpus-001` folder layout.

## Current gate and next work

The current owner-populated corpus has no cross-label duplicate components and
`split-002` emits a 1,852-record plan over 53 isolation components: 13
sensitive-like, 14 placeholder/test, and 26 benign/other. The plan allocates
1,227 training, 226 validation, 208 calibration, and 191 test records. Every
held-out primary-label count is at least 50, so the structural data-readiness
requirements in [`phase-01-quality-gate-002`](phase-01-quality-gate.md) pass.

Later owner-approved project, language, chronology, or explicit-template
metadata rules remain future work. A persisted dataset-artifact format remains
separate future work.
