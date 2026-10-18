# Feature Specification: Execution-evidence control loop

**Status**: Draft implementation requirements
**Date**:2026-10-18
**Branch**: feat/execution-evidence-control-loop

## User scenarios

A user asks an agent to implement scoped requirements without learning CLI commands. Before work, the agent identifies requirement IDs, real tests and unresolved assumptions. After work, it captures actual verification, rejects stale/missing evidence, checks links and hands off compact status-preserving context.

## Functional requirements

- **EC-001**: Versioned execution evidence envelope and explicit preflight phase compatibility.
- **EC-002**: Fail-closed malformed/unknown contract handling.
- **EC-003**: Deterministic evidence-status composition without duplicate AEE scoring.
- **EC-004**: Python/Bash/PowerShell parity and preserved1.0 result compatibility.

## Acceptance and safety boundaries

No status promotion from prose, score or a self-declared CI name. No executing commands on ingest. Reject path escapes, symlinks, malformed/unknown versions and incomplete discovery. Human approvals require inspectable scoped provenance. Missing/stale evidence is unknown, not a pass. Preserve historical evidence, independent method/lexicon versions and all published tags.

## Validation

Meaningful line and branch coverage, adversarial/fuzz and real integration tests; maintain Linux/macOS/Windows × Python3.11/12/13. Do not exclude untested code to claim100%. Shell parity is additional to Python coverage. Complete actual AEE assessments at specification, planning, tasks and implementation with recorded command evidence and separate human-acceptance status.

## Benchmark isolation

Do not alter the running baseline benchmark source, environment, installed releases or model/service. No release until the before study completes successfully. The after study will change only documented feature versions/skills under the same prospective measurement settings. No automatic efficacy/savings claim.

## Linked requests

- https://github.com/electrohire/spec-kit-evaluator/issues/17

## Out of scope

Another claim-scoring layer; Specsmith dependency; unrelated features; fabricated trusted CI/human acceptance; product truth/safety/compliance certification; baseline rerun contamination.
