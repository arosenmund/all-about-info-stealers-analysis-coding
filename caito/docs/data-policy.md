# Lab Data and Fixture Policy

## Scope

The lab uses generated data by default. The legacy source categories below are
optional descriptive metadata for fixtures and experiments; they are not a
general intake gate for future Stage 01 collection.

| Legacy source tag | Meaning |
| --- | --- |
| `synthetic` | Artificial test data produced for this project. |
| `generated` | Deliberately generated non-live data with recorded generation method. |
| `revoked` | Material verified as revoked and approved for research use. |
| `authorized` | Material explicitly authorized by the owner for a stated research purpose, when that distinction is useful. |

`input-001` keeps these fields mandatory because it is a frozen Phase 0
compatibility contract. A later crawl contract may make source metadata
optional while still recording it when available.

## Initial fixture rules

- All committed fixtures are synthetic, test-only, and non-live.
- Each committed fixture carries a dataset ID/version, legacy source tag, group ID, template ID, and primary label annotation for repeatability.
- Runtime input records never require labels; labels belong only in fixture/evaluation wrappers.
- Do not add paths, URLs, discovery hints, browser state, environment-variable names, or collection configuration to `input-001` source metadata. The `crawl-001` Stage 01 POC has its own versioned local-collection boundary; a later ingestion contract will define optional source metadata for classifier records.
- Keep raw test-only strings inside `tests/fixtures/` and never copy them to normal reports, logs, or session handoffs.

## Handling and retention

- Do not commit externally sourced datasets, model weights, or generated artifacts without appropriate license, checksum, and distribution notes. Lab-generated data may be used locally without an external authorization record.
- Generated datasets, split manifests, benchmark results, model artifacts, and release bundles are ignored by default until an approved retention policy is recorded.
- The first runtime will not persist candidate records. Any future retention need requires an ADR and explicit project-owner review.

## Reporting

- Successful output is redacted by schema: it includes a record ID, byte length, optional keyed fingerprint, decision, evidence summaries, and artifact versions.
- Rejection output contains a stable error code and sanitized message only; it must not echo candidate or context contents.
- Do not fall back to an ordinary content hash for operational correlation. Until a keyed fingerprint design is approved, omit the fingerprint.
