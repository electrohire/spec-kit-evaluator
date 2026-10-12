---
description: "Compose multiple evaluator results at a lifecycle point with deterministic precedence"
scripts:
  sh: ../scripts/bash/compose-results.sh
  ps: ../scripts/powershell/compose-results.ps1
  py: ../scripts/python/compose_results.py
---

# Evaluator Compose

Compose multiple independent evaluator results at a single lifecycle point into one aggregate result with deterministic precedence.

When multiple evaluators run at the same phase (e.g., a schema validator, a security scanner, and an epistemic checker all after `plan`), their results must be composed into a single actionable verdict. This command applies deterministic composition rules so the outcome is reproducible.

## User Input

```text
$ARGUMENTS
```

The user input specifies **which results to compose**. Accept:

1. **Phase** — the lifecycle phase to compose results for (e.g., `phase=after_plan`). Required.
2. **Result files** — explicit list of result file paths. If not provided, discover all result files for the given phase from `.specify/extensions/evaluator/results/`.
3. **Composition strategy** — `strict` (default), `majority`, or `optimistic`. See Composition Strategies below.

## Prerequisites

- **Path safety (do this before any read or write)**: resolve the project root and the real, symlink-resolved path of `.specify/extensions/evaluator/results/` and every result file you touch. **Refuse and report — never follow —** if any path component is a symlink, or if the resolved path does not remain inside the project root.
- At least one *valid* result file MUST exist for the specified phase. **Composition fails closed** (Spec 003 FR-6.1): if none exist — missing directory, zero files for the phase, or zero valid files — the composed result has `outcome: "block"` with an explicit `composed:NO-RESULTS` finding, and compose exits non-zero. Absence of evidence is never a pass.
- Each result file MUST be valid JSON conforming to the evaluator result schema. Invalid files are **not skipped**: each is wrapped as a blocking `schema_violation` finding (per `speckit.evaluator.run.md` step 3.4) and counts as a `block` vote under every strategy. Report each invalid file by name.

## Execution

Run `{SCRIPT}` with the appropriate arguments to compose the results:

```bash
{SCRIPT} --results-dir .specify/extensions/evaluator/results/ --phase <phase> [--strategy strict|majority|optimistic] [--output <path>]
```

The script performs the steps below. Use these rules as reference for interpreting the output.

### 1. Collect Results

Read all result files for the specified phase from `.specify/extensions/evaluator/results/`. Filter to files matching the pattern `<evaluator-id>-<phase>-<timestamp>.json`.

### 2. Validate Each Result

For each result file:
1. Parse as JSON. Malformed JSON is a named error for that file, never a crash.
2. Validate against `.specify/extensions/evaluator/schemas/evaluator-result.schema.json`. The Python composer always applies the full schema (`jsonschema` is a declared dependency; its absence is a hard error, never a silent skip). The Bash and PowerShell composers enforce the same minimum contract: required keys, outcome/severity/kind enums, evaluator `id` + `version`, and findings shape.
3. The payload's `phase` MUST equal the requested phase; a mismatch invalidates the result.
4. Wrap each invalid result as a blocking finding and report it by name — never skip it toward pass.

Evaluator identity for deduplication and counting is the payload `evaluator.id` + `version`, never the filename. Duplicates of one evaluator count once under every strategy (the latest timestamped filename wins, deterministically).

### 3. Apply Composition Strategy

#### `strict` (default)

The most severe outcome wins. Precedence order (most severe first):

1. `block` — any evaluator blocks → composed outcome is `block`
2. `gather_evidence` — any evaluator needs evidence → `gather_evidence`
3. `iterate` — any evaluator requests iteration → `iterate`
4. `clarify` — any evaluator needs clarification → `clarify`
5. `warn` — any evaluator warns → `warn`
6. `pass` — all evaluators pass → `pass`

#### `majority`

The outcome with the most evaluators supporting it wins. Ties break toward the more severe outcome (using strict precedence).

#### `optimistic`

The least severe outcome wins. Use only when evaluators are advisory and blocking is explicitly not desired.

**Non-gating strategies.** Results composed under `majority` or `optimistic` are advisory: the composed result is marked `metadata.gating: false` with a `metadata.non_gating_reason`. When such a composition overturns a `block`, the metadata additionally records `metadata.block_overridden: true`, and every input's outcome remains visible in `metadata.evaluator_results` — an overturned block is evidence on record, never silently erased. Only `strict` compositions may be used as a release gate.

### 4. Merge Findings

All findings from all evaluators are preserved in the composed result. Each finding's `id` is namespaced by its evaluator — `<evaluator.id>:<finding.id>` — so finding ids cannot collide across evaluators, and the origin is visible in the id itself (no out-of-schema marker fields are added; the composed output must validate against the result schema). Findings are ordered by:

1. Severity (critical → high → medium → low → info)
2. Finding id (namespaced, so this is evaluator id, then the finding's own id)

> **Decision (Spec 003 T610):** an earlier draft of this section promised ordering by *evaluator priority*. No shipped composer implements a priority concept and evaluators do not declare a composition priority in their results, so the promise is removed rather than left as drift. Run order priority (in `speckit.evaluator.run`) is unaffected.

### 5. Determine Next Action

The composed `next_action` is derived from the composed outcome:

| Composed Outcome | Next Action Kind | Target Phase |
|-----------------|-----------------|--------------|
| `pass` | `pass` | null |
| `warn` | `warn` | null |
| `iterate` | `iterate` | Most common `target_phase` among iterate findings |
| `clarify` | `clarify` | null |
| `gather_evidence` | `gather_evidence` | null |
| `block` | `block` | null |

### 6. Write Composed Result

Write to `.specify/extensions/evaluator/results/composed-<phase>-<timestamp>.json`.

### 7. Report

Output a summary:
- The phase
- The composition strategy used
- The number of evaluator results composed
- The composed outcome
- Total findings by severity
- Any contradictory findings flagged
- The recommended next action
- The path to the composed result file

## Composition Rules

1. **Deterministic**: same inputs + same strategy = same composed result (modulo `metadata.timestamp`).
2. **Fail-closed**: absence or invalidity of evidence composes to `block`, never to `pass`.
3. **Contradiction-preserving**: conflicting findings are both recorded, not resolved.
4. **Evidence-respecting**: `observed` evidence from one evaluator is not downgraded by another evaluator's `asserted` claim.
5. **State-isolated**: each evaluator's `state` object is preserved under its evaluator ID in the composed result's `state` map.

## Exit Codes

Compose is a gate, and its exit code is part of the contract (all three implementations; mirroring the `gate` format in `speckit.evaluator.report.md`):

| Exit code | Composed outcome |
|-----------|------------------|
| 0 | `pass` or `warn` |
| 1 | `iterate`, `clarify`, or `gather_evidence` |
| 2 | `block` — including fail-closed no-results and invalid-input blocks — or a hard error (missing schema, missing `jsonschema`, bad arguments) |

Hard errors print a named error to stderr and produce no composed result. Invalid *input files* are not hard errors: they are wrapped as blocking findings (step 2) and compose normally to the exit code above.

## Composed Result Format

The composed result is a standard evaluator result (it validates against `evaluator-result.schema.json`), with composition detail carried in `metadata`:

```json
{
  "schema_version": "1.0",
  "evaluator": { "id": "composed", "version": "1.0", "name": "Composed (strict)" },
  "phase": "after_plan",
  "outcome": "iterate",
  "summary": "2 evaluator(s) ran. Outcomes: schema-validate=pass, epistemic=iterate. 3 finding(s) total.",
  "findings": [
    "... all findings, ids namespaced as <evaluator.id>:<finding.id>, ordered by severity then id ..."
  ],
  "next_action": {
    "kind": "iterate",
    "target_phase": "plan",
    "message": "Composed outcome: iterate."
  },
  "metadata": {
    "timestamp": "<ISO-8601>",
    "evaluator_count": 2,
    "composition_strategy": "strict",
    "gating": true,
    "evaluator_results": [
      { "evaluator_id": "schema-validate", "outcome": "pass", "findings_count": 0 },
      { "evaluator_id": "epistemic", "outcome": "iterate", "findings_count": 3 }
    ],
    "invalid_results": [],
    "duplicate_results_ignored": [],
    "contradictory_findings": [
      { "subject": "REQ-014", "finding_ids": ["epistemic:EPI-001", "schema-validate:SCH-003"], "description": "Conflicting findings on subject 'REQ-014'" }
    ]
  },
  "state": {
    "schema-validate": {},
    "epistemic": { "... opaque evaluator state ..." }
  }
}
```

Composition metadata fields: `gating` (false under `majority`/`optimistic`), `non_gating_reason` (when non-gating), `block_overridden` (when a non-gating strategy overturned a block), `invalid_results` (each invalid file with its named reason), `duplicate_results_ignored` (filenames dropped by identity dedup), and `no_results` (on the fail-closed empty composition).

## Guardrails

- Never modify individual evaluator result files — compose reads them, writes a new composed file.
- Never resolve contradictions by dropping findings — preserve both.
- Never change another evaluator's evidence classification.
- Never merge `state` objects across evaluators — keep them isolated under evaluator IDs.
- The composed result is a new artifact; it does not replace individual evaluator results.
