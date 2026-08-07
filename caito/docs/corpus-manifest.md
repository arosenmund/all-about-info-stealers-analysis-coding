# Corpus Manifest Contract (`corpus-manifest-002`)

## Purpose

`corpus-manifest-002` creates a deterministic, in-memory inventory of prepared
`corpus-001` candidates. It is the first Phase 1 data-quality POC: it confirms
that folder-derived labels have reached canonical preprocessing and establishes
a conservative group boundary before any train/evaluation split exists.

The machine-readable contract is
[`contracts/corpus-manifest-002.json`](../contracts/corpus-manifest-002.json).

## Contents and privacy

Each in-memory manifest item retains only a stable record ID, group ID, primary
label, optional artifact family, extraction kind, candidate byte length, and
whether byte preprocessing truncated it. It intentionally excludes candidate
text, context, semantic envelopes, filesystem paths, and candidate fingerprints.
The POC has no writer; it does not create a persisted dataset artifact.

The aggregate summary contains record/group counts, the three primary-label
counts, the number of artifact families, and aggregate classifier-input
rejection codes. This is the only form exposed through the CLI.

## Initial grouping rule

`group-001` puts every candidate extracted from one crawl document in the same
group. This ensures later split logic cannot train on one candidate from a file
and evaluate on another from that same file. It is a minimum isolation boundary,
not a substitute for later template, project, language, chronology, or
near-duplicate grouping.

The manifest accepts labelled corpus inputs only. An ordinary target scan has no
ground-truth labels and is rejected rather than being silently converted to
training data.

## Run it

```text
phase_01_crawl.py --root <corpus-root> --as-corpus --manifest
```

This implies extraction and preparation, and prints aggregate counts only.

## Next work

[`duplicate-001`](duplicate-detection.md) now compares labeled candidates
in-memory and reports aggregate exact/near, cross-group, and cross-label
counts. Its components are the next isolation boundary to combine with
`group-001` during deterministic train/validation/calibration/test assignment.
[`split-002`](split-planning.md) now implements that in-memory assignment POC,
adds same-label artifact-family isolation, and rejects unresolved cross-label
components.
