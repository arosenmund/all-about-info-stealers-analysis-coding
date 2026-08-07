# Phase 01 Support — Data and Evaluation Inputs

This directory will contain lab-generated fixture generation, optional
source-metadata capture, corpus manifests, group-aware split tooling, and
data-quality reports.

For the first corpus layout, populate a selected root as described in
[`docs/corpus-layout.md`](../../docs/corpus-layout.md): the first directory is
the primary label and the optional second directory is the artifact family.
`stage_02_ingestion_preprocess.build_labeled_corpus()` derives those training
annotations in memory. Folder names label corpus examples only; they do not
become automatic classifications for arbitrary scan targets.

`extract_labeled_corpus()` applies the current `extract-002` candidate/context
rules while retaining those corpus annotations.
`build_classifier_inputs()` then applies the in-memory `classifier-input-002`
bridge and shared canonical preprocessing. The resulting records are ready for
the future feature/model branches, not yet classification results.

`build_corpus_manifest()` builds the labelled-only, in-memory
`corpus-manifest-002` POC. Its initial group boundary keeps all candidates from
one crawled document together. `analyze_corpus_duplicates()` now applies the
in-memory `duplicate-001` exact/near detector to that manifest and its matching
classifier inputs. Its redaction-safe groups are split-planning evidence only;
`build_split_manifest()` now combines those groups with `group-001` and the
same-label corpus artifact-family cohort into the in-memory `split-002` plan.
It fails closed until cross-label duplicate components are reviewed; persisted
split artifacts remain future work.
`features-001` consumes the prepared inputs in memory after that same intake
path; it is documented in [`docs/deterministic-features.md`](../../docs/deterministic-features.md).

Do not place unreviewed real-world values, credentials, or downloaded datasets here. Generated data and split artifacts are ignored by default.
