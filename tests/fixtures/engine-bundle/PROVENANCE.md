# Fixture provenance: claims.json

`claims.json` in this directory was generated from the real engine, not
hand-written:

- Source: `applied-epistemic-engineering` (the AEE engine), version
  1.6.0, repository commit `0f2efcf`.
- Method: claims were constructed with `aee.model` (`Claim`,
  `Evidence`, `FailureMode`, `Disposition`, including `advance_stage`
  stage events) and serialized through `Claim.to_dict()`, then wrapped
  as `{"claims": [...]}`.
- Generated: 2026-11-12.
- SHA-256 of claims.json at generation: `f4d5c3679c24759125d3d94cc86c9f63c3e1aea96b95d295864de8a58b591de8`

The bundle deliberately exercises the engine's current surface: a
headline claim with decomposition-role sub-claims, stored lifecycle
`stage` values with recorded `stage_events`, every evidence kind
(including `exposition`), a declared content hash (which makes the
engine emit `content_hash_status`), the derived `confidence_band`,
stored dispositions, and regenerated failure modes.

Purpose: the drift-alarm test in
`tests/test_spec_structure_evaluator.py` runs the structural evaluator
over this directory and asserts no `schema_violation` findings. If the
engine's claim model changes and this evaluator's hand-mirrored field
sets are not updated to match, the fixture should be regenerated from
the new engine and the test will fail until the mirror catches up.
The evaluator deliberately does NOT depend on the engine package; this
fixture is the cross-check instead.
