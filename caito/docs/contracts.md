# Contracts and Canonical Preprocessing

## Version 001 status

`input-001`, `output-001`, `fixture-001`, `manifest-001`, and `preprocess-001` are the first **provisional but explicit** project contracts. They are suitable for Phase 0 testing. Any behavior change requires a new version, new golden fixtures, and a documented migration note; never silently reinterpret an existing version.

## Input record

The runtime accepts only a valid UTF-8 JSONL object with this fixed shape:

```json
{
  "schema_version": "input-001",
  "record_id": "fixture-0001",
  "candidate": "synthetic test-only value",
  "context": {"key": "example_key", "line": "example", "before": [], "after": []},
  "source": {"dataset_id": "synthetic-fixtures", "dataset_version": "001", "authorization": "synthetic"}
}
```

`context.key`, `context.line`, `context.before`, and `context.after` are always present. Empty strings/arrays represent unavailable context. Extra top-level, context, or source fields are rejected so input cannot smuggle paths, URLs, discovery instructions, or collection configuration.

`input-001` remains the Phase 0 explicit-JSONL contract. The selected-root
collection path instead uses the separate in-memory `crawl-001` →
`extract-002` → `classifier-input-002` contracts. It does not reinterpret
`input-001`, add path metadata to its fixed shape, or invent its legacy source
object.

## Limits and malformed input

The frozen Phase 0 `input-001` parser must accept strict, valid UTF-8 JSON
only and reject malformed JSON, UTF-16/UTF-32 input, duplicate object members,
non-standard `NaN`/`Infinity` constants, invalid Unicode scalar values,
oversized values, unknown fields, absent legacy source fields, and unknown
legacy authorization values before inference. Duplicate members and
non-standard constants use `invalid_json`; a lone Unicode surrogate escape
uses `invalid_unicode`. Those legacy-source checks do not define the future
Stage 01 collection contract.

The provisional transport limits are:

| Field | Limit |
| --- | ---: |
| Physical JSONL line, including a line ending if present | 16,384 bytes |
| Candidate | 4,096 UTF-8 bytes |
| Context key | 128 UTF-8 bytes |
| Context line | 2,048 UTF-8 bytes |
| `before` / `after` items | 4 each |
| Each nearby line | 512 UTF-8 bytes |
| Supplied context fields, aggregate before normalization | 8,192 UTF-8 bytes |
| Normalized/redacted context fields, aggregate before envelope labels/separators | 8,192 UTF-8 bytes |

The model-facing candidate buffer is separately capped at 512 bytes by `preprocess-001`; accepting a record does not imply every byte reaches a later CNN.

## Canonical preprocessing (`preprocess-001`)

The machine-readable parameter source is [`contracts/preprocess-001.json`](../contracts/preprocess-001.json).

1. Decode one valid UTF-8 JSON record explicitly as UTF-8; reject invalid bytes and UTF-16/UTF-32 inputs rather than auto-detecting or replacing them.
2. Validate the `input-001` shape and limits.
3. Preserve candidate text exactly for the byte path, then UTF-8 encode it strictly. Byte ID `0–255` equals the corresponding byte value.
4. Right-truncate candidates over 512 bytes and right-pad shorter buffers with byte ID `256` to a fixed 512 IDs.
5. For semantic context, Unicode-normalize all text to NFC and normalize `CRLF`/`CR` line endings to `LF`.
6. Replace normalized occurrences of the normalized candidate in `key`, `line`, `before`, and `after` with the literal `<CANDIDATE>` before forming the context envelope.
7. Form the deterministic envelope in this exact order:

   ```text
   key=<key>\n
   line=<line>\n
   before=<line 1>\n<line 2>...\n
   after=<line 1>\n<line 2>...
   ```

8. Reject a record if either its supplied context fields or its normalized/redacted field contents exceed the separately stated aggregate limits. Envelope labels and separators are not included in the latter count. Do not silently truncate semantic context in version 001.

The Python reference generates golden records from this rule. Rust must produce the same byte-ID buffer and context envelope before its preprocessing implementation is accepted; the buffer is checked through the defined digest.

Golden records contain the candidate byte length, truncation state, and SHA-256 of the fixed-width byte-ID buffer—not a reversible encoding of the candidate. The digest inputs are the 512 IDs represented as unsigned two-byte big-endian integers, preserving the distinction between byte `0` and padding ID `256`.

## Selected-root classifier-input bridge

The Python-only Stage 01/02 path is versioned as `crawl-001` (bounded
UTF-8-file collection), `extract-002` (candidate/context extraction), and
`classifier-input-002` (bounded handoff to this same preprocessing behavior).
The final bridge adopts the candidate and context limits above, performs the
same candidate-redacted semantic-context construction, and rejects individual
over-limit extracted candidates using aggregate-only codes.

It retains optional `corpus-001` labels in memory for training/evaluation and
leaves ordinary scans unlabelled. It has no `input-001` source object, no raw
record serializer, and no path/content output. See
[`docs/stage-02-classifier-input.md`](stage-02-classifier-input.md).

For corpus-labelled inputs, `corpus-manifest-002` retains a redaction-safe
in-memory inventory and groups all candidates from the same crawl document. It
does not persist a manifest or assign train/evaluation splits; see
[`docs/corpus-manifest.md`](corpus-manifest.md).

`duplicate-001` then compares the in-memory candidate values only to create
redaction-safe exact and near-duplicate cluster metadata for later split
planning. It never serializes candidate values, context, paths, or
fingerprints, and it never changes labels or assigns splits. See
[`docs/duplicate-detection.md`](duplicate-detection.md).

`split-002` combines `group-001` documents, duplicate components, and the
same-label corpus artifact-family cohort to form in-memory
train/validation/calibration/test assignments. It rejects any cross-label
duplicate component and exposes only aggregate split coverage at the command
boundary. See [`docs/split-planning.md`](split-planning.md).

## Output and errors

`output-001` has three redacted forms:

- `validated`: an intentionally temporary Phase 0 CLI success response. It proves the explicit input record passed validation/preprocessing and reports only record ID, candidate byte length, context presence, and preprocessing version. It makes no model classification.
- `classified`: contains model top class, policy decision (which may be `abstain`), confidence, redacted evidence summaries, and artifact versions.
- `rejected`: contains a sanitized error code/message and optional safe record ID, never a candidate or context echo.

Initial Phase 0 rejection codes are `invalid_json`, `invalid_utf8`,
`invalid_schema`, `invalid_provenance`, `invalid_unicode`, and
`input_limit_exceeded`. `invalid_provenance` applies only to the frozen
`input-001` legacy source fields.

## Artifact manifest

`manifest-001` binds a bundle’s class order, preprocessing version, legacy
legacy allowed-source tags, offline/discovery flags, and checksummed files.
Future CNN, embedding, prototype, fusion, and policy metadata are versioned
component sections—not implicit runtime assumptions.

The `runtime_discovery: false` invariant in `manifest-001` applies to the
current Phase 0 bundle/runtime. If Stage 01 introduces an explicit-root local
crawl, it requires a new versioned manifest/crawl contract rather than changing
the meaning of this manifest version.
