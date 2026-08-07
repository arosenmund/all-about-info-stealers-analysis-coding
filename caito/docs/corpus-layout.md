# Folder-Labeled Corpus Contract (`corpus-001`)

## Purpose

`corpus-001` lets the folder structure assign ground-truth labels to the
lab-generated examples you add. It builds on the selected-root `crawl-001` POC
and remains entirely in memory.

Python and Rust share the default project-local root `<repository>/corpus`.
Both derive it from their package location, so the same checkout works on macOS
and Windows without hardcoding a machine-specific absolute path. The helper
does not create or crawl that directory automatically.

```text
corpus-root/
├── sensitive_like/
│   ├── configuration_like/
│   │   └── example.txt
│   └── direct-example.txt
├── placeholder_or_test/
│   └── documentation_example/
│       └── sample.yaml
└── benign_other/
    └── ordinary_metadata/
        └── values.json
```

For this project, use `corpus` as `corpus-root` and populate:

```text
corpus/sensitive_like/
corpus/placeholder_or_test/
corpus/benign_other/
```

- The first directory below `corpus-root` must be exactly one of
  `sensitive_like`, `placeholder_or_test`, or `benign_other`. It supplies the
  required primary label.
- The optional second directory supplies the artifact-family annotation.
  Deeper directories organize files only; they do not alter the label.
- A file directly under `corpus-root`, or below an unrecognized first
  directory, rejects the corpus build rather than being silently mislabeled.
- Hidden/configuration/key/certificate and extensionless files remain eligible
  input when they are regular UTF-8 files under the selected corpus root.

The machine-readable source is
[`contracts/corpus-001.json`](../contracts/corpus-001.json).

## Important inference boundary

Folder names are ground truth for corpus construction, split generation, and
evaluation only. An arbitrary filesystem scan must classify file contents and
context; it must not assign a prediction merely because a target folder shares
a corpus label name. That would leak the answer and invalidate evaluation.

## Current handoff

`stage_02_ingestion_preprocess.build_labeled_corpus()` turns `crawl-001`
`CrawlItem` values into labeled in-memory `CorpusItem` values.
`extract_labeled_corpus()` then applies the documented `extract-002` rules and
retains those labels on its in-memory candidate/context records. See
[`docs/stage-02-extraction.md`](stage-02-extraction.md).
`classifier-input-002` then applies canonical preprocessing while retaining
those annotations in memory. It must preserve this corpus-only labeling
boundary; a later decision-reporting contract must do the same.

`corpus-manifest-002` then creates a labeled-only, in-memory manifest from the
prepared records. Its initial `group-001` rule places all candidates extracted
from one crawled document in one group, so a later split cannot divide a file's
candidates across train and evaluation partitions. It has no writer or split
assignment yet. See [`docs/corpus-manifest.md`](corpus-manifest.md).
