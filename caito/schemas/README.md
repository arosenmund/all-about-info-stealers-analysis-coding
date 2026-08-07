# Schemas

Schemas use JSON Schema Draft 2020-12. They are versioned public contracts; a breaking change requires a new schema version and migration/golden-fixture updates.

- `input.schema.json`: explicit runtime records only.
- `fixture.schema.json`: labeled synthetic/evaluation wrappers around input records.
- `output.schema.json`: redacted successful and rejection outputs.
- `manifest.schema.json`: versioned offline artifact bundles.

The standard-library Phase 0 validator mirrors the safety-critical rules while the project has no JSON-Schema dependency. Add a full schema-validator dependency only when pinned and verified in the project environment.

