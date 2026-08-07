# Stage 01 Local Crawl Contract (`crawl-001`)

## Purpose and status

`crawl-001` is the Python-first, in-memory local-collection POC. It reads a
bounded set of UTF-8 text files from exactly one user-selected directory and
returns in-memory `CrawlItem` values to the next pipeline stage. It does not
classify values, create `input-001` records, or write artifacts. Its explicit
`phase_01_crawl.py --root <directory>` command reports aggregate counts only;
it never reports paths or file contents.

The machine-readable defaults are in
[`contracts/crawl-001.json`](../contracts/crawl-001.json). This is a new
contract; it does not weaken or reinterpret the frozen Phase 0 `input-001` or
`manifest-001` contracts.

## Boundary

- The caller supplies one local directory as `CrawlConfig.root` or through the
  required `phase_01_crawl.py --root <directory>` argument. The root is
  resolved once and collection remains beneath that resolved directory.
- A filesystem root, a missing path, or a non-directory is rejected with a
  sanitized `CrawlContractError`; errors do not include the supplied path.
- Traversal is deterministic: directory entries are processed in name order.
- Symlinks are never followed. Apart from an optional caller-provided exclusion
  list, all regular files beneath the selected root are eligible—including
  hidden, source-control, key/certificate, configuration, and extensionless
  files.
- `crawl-001` decodes UTF-8 strictly and skips invalid bytes. A caller may
  optionally narrow collection to a suffix allowlist, but the default does not
  exclude files by name or extension.
- The POC is bounded to 512 files, 1 MiB per file, and 8 MiB in total. It
  performs bounded reads so a file changed during traversal cannot bypass the
  per-file memory limit.
- The configuration can add exclusions or narrow the suffix allowlist. It
  cannot enable symlink traversal or remove the count/byte/UTF-8 limits.

## Results and privacy

`CrawlResult.items` retains text and a relative path only in process memory for
the next pipeline stage. It has no serializer, persistence function, or CLI.
`CrawlSummary` exposes aggregate file/byte counts and skip reasons only; it
contains no paths or file contents. Normal reporting continues to be redacted.

`CrawlItem.document_id` is a deterministic internal identifier derived from
the relative path. It is not an operational fingerprint and must not be emitted
in ordinary reports until a keyed correlation design is approved.

## Handoff and acceptance gate

`extract-002` is the tested Stage 02 in-memory handoff from `CrawlItem` to
candidate/context records. `classifier-input-002` then validates their limits
and invokes shared canonical preprocessing; see
[`docs/stage-02-extraction.md`](stage-02-extraction.md) and
[`docs/stage-02-classifier-input.md`](stage-02-classifier-input.md). A later
decision-reporting contract must still define final source-metadata conventions
and redacted decision output before any Rust migration.

The `crawl-001` POC is accepted only when unit tests prove deterministic
selection, symlink exclusion, UTF-8 and byte-limit handling,
aggregate-only reporting, and no persistence or network behavior.
