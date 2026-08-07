# Stage 01 — Local Filesystem Crawl

This stage is the local, opt-in boundary for traversing an explicitly
user-selected local filesystem root. Its Python-first `crawl-001` POC now
collects bounded UTF-8 text in memory; its explicit `--root` command emits only
redacted aggregate counts. It has no persistence, network access, or classifier
integration yet.

The contract defines the selected root, deterministic traversal, symlink
behavior, UTF-8 and size limits, optional exclusions, retention, redaction,
and reporting rules in [docs/stage-01-crawl.md](../../../docs/stage-01-crawl.md).
Within that selected lab root, hidden/configuration/key/certificate files are
eligible. The collector must not become background or system-wide discovery,
use network access, persist raw contents, or inspect browser, wallet, registry,
or process sources.

The current `input-001` and `manifest-001` contracts remain unchanged for the
Phase 0 JSONL runtime. `crawl-001` is the new versioned local-collection
contract and does not change their meaning. A later Stage 02 ingestion contract
will convert `CrawlItem` values into classifier inputs.
