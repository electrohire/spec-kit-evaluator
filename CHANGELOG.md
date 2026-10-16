# Changelog

All notable changes to the Evaluator Contract extension will be documented in this file.

## Unreleased

## [1.1.2] - 2026-10-16

### Changed
- Publish the private vulnerability reporting policy, add a Python lint gate,
  and fuzz malformed result bytes across all three composition strategies.

- Add an evaluator agent skill for standalone and Spec Kit composition and
  document natural-language use of the installed operation skills.
- Clarify distribution and extension names, the limits of composition and
  independent evaluation, and this repository's own Spec Kit/AEE setup.

### Fixed
- Treat non-UTF-8 result files as blocking invalid input instead of allowing
  a Unicode decoding traceback to escape composition.

## [1.1.1] - 2026-10-15

### Fixed
- The Python composer and `examples/demo.py` failed to parse on Python
  3.11: they nested same-type quotes inside f-strings, which only Python
  3.12+ (PEP 701) accepts. The quotes are now distinct (the composer
  builds its outcome list outside the f-string); output is unchanged.
- README installation used `specify extension add evaluator`, which the
  discovery-only community catalog refuses, and a stale in-tree `--dev`
  path; it now gives the release-archive `--from` command and the composer
  dependencies.

### Changed
- CI runs the Python test suite on Ubuntu, Windows, and macOS with
  Python 3.11, 3.12, and 3.13, matching applied-epistemic-engineering and
  spec-kit-aee. It installs `jq` where missing and fails when a composer
  toolchain is absent, so no target silently skips a parity leg.

## [1.1.0] - 2026-10-12

### Added
- Lane-paired composition (Spec 004 P5, `specs/001-lane-paired-composition`): when an input result carries the AEE lane pair in `metadata.lanes` (lane 1 machine verification / lane 2 human acceptance, emitted by the realigned engine's Evaluator Contract result), the Python composer carries it through verbatim per evaluator as `metadata.lane_states` — never merged, averaged, or scored — and the composed summary states lane-2 lag (claims below the explained stage, verified-but-unexplained claims, residual `not_understood` entries) whenever present, including on a `pass`, so a lane-1-green headline never reads as acceptance or digestion. Lane-less inputs compose exactly as before.
- Lane-paired composition parity (Spec 004 P5 addendum, `specs/001-lane-paired-composition`): the bash and PowerShell composers now carry `metadata.lanes` through as `metadata.lane_states` with the same lane-2 lag summary semantics as the Python composer, and the cross-implementation parity harness asserts the lane pairs field-by-field (not just outcome/exit) for all three composers.
- Deterministic spec-structure reference evaluator (`scripts/python/spec_structure_evaluator.py`, Spec 002 FR-7): checks spec/plan/tasks presence, required spec sections, claims bundle presence + strict-load validity, falsifiers, assessment presence, and task↔requirement traceability; emits schema-valid evaluator results
- `evaluators.yml` registering the reference evaluator for discovery
- Passing and failing fixture specs under `examples/fixtures/spec-structure/` and a README walkthrough (discovery → run → validate → compose), exercised by `tests/test_spec_structure_evaluator.py`

### Changed
- Composition fails closed in all three composers (Spec 003 FR-6): empty or all-invalid composition yields `block` + exit 2 with an explicit no-results error, never `pass`; command documents amended from pass-on-empty
- Python composer always schema-validates inputs (`jsonschema` is now a declared dependency in `requirements.txt`; its absence is a hard error) and self-validates composed output; invalid, malformed, or phase-mismatched inputs are wrapped as blocking findings instead of skipped or crashing
- Composed output is schema-valid: finding ids namespaced per evaluator (no `_evaluator_id` injection), `model_routing` omitted rather than `null`, summary capped at 500 chars, merged routing taken consistently from the winning routing
- Dedup/counting use payload `evaluator.id` + `version` (duplicates count once); `majority`/`optimistic` results are marked non-gating in metadata with `block_overridden` recorded; compose exit codes follow the gate contract (0 pass/warn, 1 iterate/clarify/gather_evidence, 2 block/error)
- `examples/demo.py` fixed to the current compose output shape and covered by tests

## [1.0.0] - 2026-09-01

### Added
- Initial release of the Evaluator Contract extension
- JSON Schema for evaluator results (6 outcomes, 14 finding kinds, 5 evidence kinds, 5 uncertainty levels)
- 4 commands: `speckit.evaluator.run`, `.compose`, `.report`, `.route`
- 3 parity scripts: Python, Bash, PowerShell
- 4 lifecycle hooks: `after_specify`, `after_plan`, `after_tasks`, `after_implement`
- Model routing: recommends budget/standard/premium tier per phase
- Composition: strict/majority/optimistic strategies with contradiction detection
- Quick-start demo: `python examples/demo.py`
- Token-economic benchmark suite with Monte Carlo simulation
- 70 tests with 0 regressions against spec-kit test suite
