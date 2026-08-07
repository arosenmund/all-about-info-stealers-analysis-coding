# Stage 02 Candidate and Context Extraction (`extract-002`)

## Purpose

`extract-002` converts in-memory Stage 01 files into candidate/context records
for the Python POC. It is deliberately a small, deterministic starting point:
it does not classify, persist, emit raw records, or reinterpret the frozen
Phase 0 `input-001` schema.

The machine-readable contract is
[`contracts/extract-002.json`](../contracts/extract-002.json). It supersedes
the narrower historical `extract-001` POC.

## Rules

For each UTF-8 file, process lines in source order.

1. A valid one-line JSON object emits each non-empty top-level string value in
   object/source order. A multiline JSON property with a quoted string key and
   quoted string value also emits one candidate; an optional trailing comma is
   accepted.
2. Otherwise, an identifier-like `key=value` or `key: value` line emits one
   non-empty candidate.
3. Otherwise, a constrained `key: value` mapping may use a key containing
   ASCII letters/digits, underscore, `@`, spaces, periods, backslashes,
   backticks, or hyphens. One matching outer backtick pair is removed from the
   key. This covers structured documentation labels without a free-text-line
   fallback.
4. Non-JSON mapping values are trimmed, one matching outer quote pair is
   removed, and a whitespace-delimited trailing `#` or `//` comment is removed
   outside quotes.
5. Each record carries its key, original line, and up to two preceding and two
   following lines as in-memory context. Line numbers are one-based.
6. Unmatched lines are ignored. There is no arbitrary free-text, multiline
   YAML block, TOML-table, nested-JSON, or regular-expression extraction.

When the input is a `corpus-001` result, its primary-label and optional
artifact-family annotations are carried with each extracted record for training
and evaluation. When the input is an ordinary `crawl-001` result, the record
has no label. Folder names never become a target-scan prediction.

## Handoff

`extract-002` feeds the in-memory `classifier-input-002` bridge. That bridge
enforces candidate/context transport limits, preserves only optional corpus
annotations, and invokes the existing `preprocess-001` byte/context behavior.
It does not invent the legacy `input-001` source object or change that frozen
schema. See [`docs/stage-02-classifier-input.md`](stage-02-classifier-input.md).

For an aggregate-only exercise of the POC, run
`phase_01_crawl.py --root <directory> --extract`; add `--as-corpus` when the
root uses the `corpus-001` folder layout. The command reports extraction counts
and kinds, never paths, candidates, or context.
