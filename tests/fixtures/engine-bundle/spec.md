# Engine Bundle Drift Fixture

A minimal feature directory whose claims.json is a bundle serialized by
the real AEE engine, used by the drift-alarm test: the structural mirror
must accept, with no schema_violation findings, the exact bundle shape
the current engine writes.

## Requirements

- FR-001: The structural evaluator accepts engine-written claim bundles.

## Acceptance Criteria

- Evaluating this directory yields no schema_violation findings.
