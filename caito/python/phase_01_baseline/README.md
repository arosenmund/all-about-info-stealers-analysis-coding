# Phase 01 Support — Baseline Experiments

`baseline-002` is the Python-only Phase 1 comparator: deterministic signed
character n-gram hashing plus multinomial logistic regression. It trains only
on the `split-002` train partition and reports aggregate validation,
calibration, and test metrics without persisting a model or revealing
candidates.

Run it with `make run-baseline`. Its versioned behavior is in
[`contracts/baseline-002.json`](../../contracts/baseline-002.json), and the
current grouped result is recorded in
[`docs/baseline-002-report.md`](../../docs/baseline-002-report.md).

The first measured result is intentionally a baseline, not an accepted scanner
classifier: the stronger split exposes insufficient independent component and
held-out support for the quality gate. Do not move to policy, scanner
decisions, or neural dependencies until coverage and gate review pass.
