# Tasks: Execution-evidence control loop

**Input**:spec.md, plan.md, research.md, data-model.md and contracts/. Tests explicitly requested.

## Foundation

- [x] T001 Refresh own Specify1.2.1 while preserving installed released AEE/evaluator pins in .specify/project-tooling.json.
- [x] T002 Fill design artifacts and run actual specification/planning AEE with composed results; draft/human acceptance stays unknown.
- [ ] T003 Measure maintained-code line/branch coverage including subprocesses; record cross-platform/shell gaps without exclusions.

- [ ] T004 [US1] Create backward-compatible schema fixtures and malformed/version/preflight/freshness tests in tests/ before schemas/ implementation.
- [ ] T005 [US1] Implement explicit new phase and shared evidence sub-contract in schemas/ without accepting unknown versions/fields or selfdeclared trust.
- [ ] T006 [US2] Implement deterministic composition in scripts/python/compose_results.py, Bash and PowerShell with hard malformed-contract blocking.
- [ ] T007 [US2] Add parity/fuzz fixtures and actual AEE-produced result integration; preserve released1.0 paths and policy semantics.

## Cross-cutting verification

- [ ] T090 Update README/docs/skills/examples and CHANGELOG Unreleased with actual capabilities and assurance limits.
- [ ] T091 Complete actual after_tasks/after_implement AEE and deterministic Evaluator composition with inspectable command artifacts.
- [ ] T092 Pass lint/type/build/fuzz/security, meaningful100%line+branch coverage and all required cross-platform CI; disclose remaining gaps.
- [ ] T093 Open linked reviewable PR, merge only exact-green head with exact policy restoration; hold product releases during baseline.

## Dependencies and execution strategy

Foundation → scoped evidence → links → preflight → context → adapter integration. Evaluator schema fixtures can be prepared before final engine CLI, but cross-component acceptance blocks completion. Execute incrementally with one owner; no parallel agents authorized. Each story has targeted malformed/error tests and an independently runnable integration scenario. CLI, direct-agent and SpecKit routes share semantics.

## Benchmark gate

Valid baseline completion + all product validation → immutable versioned candidate/release under current rules → prospective matched after freeze. Never change baseline dependencies or tune features to hidden scored outcomes.
