# Changelog

All notable changes to the Evaluator Contract extension will be documented in this file.

## [Unreleased]

### Added
- Deterministic spec-structure reference evaluator (`scripts/python/spec_structure_evaluator.py`, Spec 002 FR-7): checks spec/plan/tasks presence, required spec sections, claims bundle presence + strict-load validity, falsifiers, assessment presence, and task↔requirement traceability; emits schema-valid evaluator results
- `evaluators.yml` registering the reference evaluator for discovery
- Passing and failing fixture specs under `examples/fixtures/spec-structure/` and a README walkthrough (discovery → run → validate → compose), exercised by `tests/test_spec_structure_evaluator.py`

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