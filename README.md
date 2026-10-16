# Evaluator Contract Extension

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15600/badge)](https://www.bestpractices.dev/en/projects/15600)

OpenSSF assessment: 97%; reporting-history criteria remain unclaimed.

Standard evaluator result contract for evidence, provenance, uncertainty, and recovery — a provider-neutral protocol for extensions that evaluate artifact quality between Spec-Driven Development phases.

## Overview

In agent loops, this contract lets tools retain conflicting findings, distinguish
observations from assertions, and compose explicit recovery/block outcomes before
the next step. AEE supplies evidence-centered claim assessment; this extension
supplies the neutral envelope and composition. Together they can help expose
unsupported completion claims and preserve uncertainty during handoffs. A composed
pass does not validate sources or guarantee a hallucination-free answer. See
[use cases and how to evaluate the benefit](https://applied-epistemic-engineering.readthedocs.io/en/latest/use-cases/).

Spec Kit has a strong lifecycle and extensible hook system, but there is no common contract for extensions that evaluate the quality or trustworthiness of artifacts between phases. This extension defines that contract.

The evaluator contract lets any extension:

1. **Register** for one or more lifecycle events via hooks
2. **Receive** the relevant resolved artifacts plus stable source/provenance references
3. **Return** a versioned machine-readable result conforming to a shared schema
4. **Distinguish** observed evidence from generated assertions
5. **Preserve** contradictory findings instead of forcing false consensus
6. **Represent** insufficient evidence or unresolved uncertainty explicitly
7. **Request** a bounded next action: `pass`, `warn`, `iterate`, `clarify`, `gather_evidence`, or `block`
8. **Persist** enough compact state to survive pause/resume
9. **Compose** deterministically with other evaluators
10. **Remain** implementation-neutral: deterministic, model-backed, local, remote, private, paid, or hybrid

## Installation

This repository is `electrohire/spec-kit-evaluator`; its Spec Kit extension ID is
`evaluator`. It is distributed as a GitHub archive, not a PyPI package. Its AEE
companion is repository `electrohire/spec-kit-aee`, extension ID `aee`. The AEE
engine is the PyPI distribution `applied-epistemic-engineering`, which installs
the Python import and CLI `aee`. Do not use `pip install aee` for that engine.

A valid result envelope and composed `pass` describe schema conformance and the
configured composition policy. They do not certify the truth of findings,
universal correctness, safety, or compliance. Independence of a reviewer helps
challenge evidence; it does not turn a model's response into a certificate. See
the engine's [names and assurance boundaries](https://applied-epistemic-engineering.readthedocs.io/en/latest/names-and-assurance/)
and this repository's [development setup](DEVELOPMENT.md).

For the complete AEE workflow in an initialized Spec Kit project:

```bash
specify extension add aee
```

AEE provisions the engine, this companion, and the Python composer dependency;
no separate evaluator installation is needed.

For standalone AEE without Spec Kit, install only the engine:

```bash
python -m pip install applied-epistemic-engineering
```

The standalone engine does not require this evaluator extension. Developers
running the composer separately can find its Python/Bash/PowerShell prerequisites
and component-specific installation in [development setup](DEVELOPMENT.md).

## Commands

### Use an agent instead of learning command syntax

Ask your agent: “Compose the evaluator results for this plan, explain conflicts,
and identify the next evidence needed.” Spec Kit renders four operation
`SKILL.md` files for run, compose, report, and route into the active integration's
skill directory. The agent reads those instructions and handles execution for you.
Reload the agent session after installation if the skills are not visible.

The source [evaluator-contract skill](skills/evaluator-contract/SKILL.md) also
guides direct composition from a checkout without Spec Kit; this onboarding skill
is included from extension v1.1.2. A composer does not produce the evidence it combines.
For standalone AEE assessment, use the engine's
[direct agent skill](https://applied-epistemic-engineering.readthedocs.io/en/latest/agent/).
The command examples below remain useful to agents and CLI users alike.

### `/speckit.evaluator.run`

Run an evaluator against one or more artifacts and produce a versioned machine-readable result.

```bash
/speckit.evaluator.run phase=after_plan artifacts=spec.md,plan.md
```

Results are written to `.specify/extensions/evaluator/results/<evaluator-id>-<phase>-<timestamp>.json`.

### `/speckit.evaluator.compose`

Compose multiple evaluator results at a lifecycle point with deterministic precedence.

```bash
/speckit.evaluator.compose phase=after_plan strategy=strict
```

Composed results are written to `.specify/extensions/evaluator/results/composed-<phase>-<timestamp>.json`.

### `/speckit.evaluator.report`

Render evaluator results as a human-readable report, CI annotation, or release gate.

```bash
/speckit.evaluator.report phase=after_plan format=terminal
/speckit.evaluator.report phase=after_plan format=ci-annotation
/speckit.evaluator.report phase=after_plan format=gate
```

## Evaluator Result Schema

The full JSON Schema is at `schemas/evaluator-result.schema.json`. Every evaluator result MUST conform to this schema.

### Minimal Valid Result

```json
{
  "schema_version": "1.0",
  "evaluator": {
    "id": "my-evaluator",
    "version": "0.1.0"
  },
  "phase": "after_plan",
  "outcome": "pass",
  "findings": []
}
```

### Outcome Semantics

| Outcome | Meaning | Workflow Effect |
|---------|---------|----------------|
| `pass` | All checks passed | Continue to next phase |
| `warn` | Issues found but not blocking | Continue with warnings |
| `iterate` | Issues require revisiting a prior phase | Return to target phase |
| `clarify` | Ambiguities need human resolution | Pause for human input |
| `gather_evidence` | Insufficient evidence | Pause for evidence collection |
| `block` | Hard blocker | Stop the workflow |

### Evidence Kinds

| Kind | Meaning |
|------|---------|
| `observed` | Directly observed from an artifact or command output |
| `inferred` | Logically derived from observed evidence |
| `asserted` | Claimed by a model or agent without direct observation |
| `contradicted` | Conflicts with other observed evidence |
| `unsupported` | No evidence found to support or refute |

## Reference Evaluator: `spec-structure`

The extension ships one deterministic reference evaluator (Spec 002 FR-7), registered in [`evaluators.yml`](evaluators.yml) — a stock install is no longer a contract without a tenant. It checks a feature directory for the contract's basics:

- `spec.md` / `plan.md` / `tasks.md` presence, and required spec sections (title, requirements, acceptance/success criteria)
- `claims.json` presence and strict-load validity (structural mirror of the AEE engine's strict loader: known fields only, non-empty `id`/`text`, valid enums, list-typed fields, no duplicate ids or JSON keys)
- every claim carries at least one falsification test
- `assessment.json` presence
- task ↔ requirement traceability (every task line references a requirement; every requirement in `spec.md` is referenced from `tasks.md`)

It is deliberately small and deterministic — no model calls; the same feature directory produces a byte-identical result modulo `metadata.timestamp`. Judging epistemics remains AEE's role; this evaluator proves the contract composes.

### Walkthrough (discovery → run → compose)

From a clean checkout, with nothing registered by hand:

```bash
# 1. Discover: evaluators.yml registers the evaluator and its script
grep -A3 'id: spec-structure' evaluators.yml

# 2. Run it against the passing fixture
mkdir -p /tmp/evaluator-results
python3 scripts/python/spec_structure_evaluator.py \
  --feature-dir examples/fixtures/spec-structure/passing \
  --phase after_specify \
  --output /tmp/evaluator-results/spec-structure-after_specify-20260101T000000Z.json

# 3. Validate the emitted result against the contract schema
python3 -c "
import json, jsonschema
schema = json.load(open('schemas/evaluator-result.schema.json'))
result = json.load(open('/tmp/evaluator-results/spec-structure-after_specify-20260101T000000Z.json'))
jsonschema.validate(result, schema)
print('emitted result is schema-valid; outcome:', result['outcome'])
"

# 4. Compose (the run command's results-directory flow)
python3 scripts/python/compose_results.py \
  --results-dir /tmp/evaluator-results --phase after_specify --strategy strict --json
```

Expected: the emitted result has `outcome: "pass"` and the composed result has `outcome: "pass"` with `evaluator_count: 1`. Repeat with `examples/fixtures/spec-structure/failing` (missing `plan.md` and `assessment.json`, a claim with no falsification test, a strict-load-invalid claim, uncovered requirements) — the emitted and composed outcomes are `block`, and every defect is named in the findings.

The walkthrough is exercised by `tests/test_spec_structure_evaluator.py` (`python3 -m unittest discover -s tests`).

## Composition Strategies

When multiple evaluators run at the same phase, their results are composed:

| Strategy | Behavior |
|----------|----------|
| `strict` (default) | Most severe outcome wins |
| `majority` | Most common outcome wins; ties break toward severity |
| `optimistic` | Least severe outcome wins |

## Composition Contract (fail-closed)

All three composers (Python, Bash, PowerShell) implement the same contract (Spec 003 FR-6), verified by a shared fixture corpus in `tests/`:

- **Empty fails closed.** Zero usable results — missing directory, no files for the phase, or no *valid* files — composes to `outcome: "block"` with an explicit no-results finding and exit code 2. Absence of evidence is never a pass.
- **Inputs are validated.** The Python composer always applies the shipped JSON Schema (`jsonschema>=4.0`, see `requirements.txt`, is a hard dependency — its absence is a hard error, never a silent skip). Bash/PowerShell enforce the same minimum contract (required keys, enums, evaluator `id` + `version`, payload `phase` equal to the requested phase). A malformed or invalid file is **wrapped as a blocking `schema_violation` finding** and votes `block` under every strategy — never skipped toward pass, never a traceback.
- **Identity is the payload.** Dedup and counting use `evaluator.id` + `version`, never the filename; duplicates of one evaluator count once. Finding ids are namespaced `<evaluator.id>:<finding.id>`.
- **Composed output is schema-valid.** No `_evaluator_id` injection, `model_routing` omitted rather than `null`, summaries within the 500-char cap; the Python composer self-validates its output before emitting it.
- **Advisory strategies are marked.** `majority`/`optimistic` results carry `metadata.gating: false`; when they overturn a `block`, `metadata.block_overridden: true` is recorded and the inputs' outcomes stay visible in `metadata.evaluator_results`. Only `strict` compositions gate.
- **Exit codes are the gate contract:** 0 = `pass`/`warn`, 1 = `iterate`/`clarify`/`gather_evidence`, 2 = `block` or hard error.

> **Decision (Spec 003 T610, recorded with Spec 002 FR-7.4):** `speckit.evaluator.report` and `speckit.evaluator.route` remain prompt-only commands — this extension ships executables for composition only, and no test pins report/route output. The earlier promise of priority-ordered findings in composition is removed from the compose command (no shipped composer implements evaluator priority); see `commands/speckit.evaluator.compose.md`.

## Hooks

The extension registers hooks at key lifecycle points:

- `after_specify` — Evaluate spec quality, evidence, and provenance
- `after_plan` — Evaluate plan assumptions, risks, and coverage
- `after_tasks` — Evaluate task completeness and traceability
- `after_implement` — Evaluate implementation against spec, plan, and tasks

All hooks are optional (prompt before executing) with priority 20.

## Writing an Evaluator

To write an evaluator that conforms to this contract:

1. Create an extension that depends on `evaluator`
2. Register hooks at the lifecycle points you want to evaluate
3. In your command, read the relevant artifacts
4. Produce a result JSON file conforming to `evaluator-result.schema.json`
5. Write it to `.specify/extensions/evaluator/results/`

See `templates/evaluator-result-template.json` for a starting point.

## Design Rules

1. **Generated assertions MUST remain distinguishable from observed evidence.**
2. **Model self-attestation MUST NOT satisfy an evidence gate by itself.**
3. **Contradictions MUST be preserved**, not collapsed into a single synthesized answer.
4. **Insufficient evidence MUST be represented explicitly** rather than inventing certainty.
5. **Deterministic checks SHOULD run before probabilistic review** where appropriate.
6. **Higher-risk work MAY require evaluator independence** — the same model/family SHOULD NOT both generate and independently evaluate the result. An independent evaluation is not itself a certification.

## File Structure

```
spec-kit-evaluator/
├── evaluators.yml                      # Registered evaluators (spec-structure)
├── schemas/
│   └── evaluator-result.schema.json   # JSON Schema for evaluator results
├── templates/
│   └── evaluator-result-template.json # Template for new evaluator results
├── scripts/
│   ├── python/spec_structure_evaluator.py  # Reference evaluator (FR-7)
│   ├── python/compose_results.py      # Composition (Python)
│   ├── bash/compose-results.sh        # Composition (Bash)
│   └── powershell/compose-results.ps1 # Composition (PowerShell)
├── examples/
│   ├── demo.py                        # Quick-start demo
│   └── fixtures/spec-structure/       # Passing + failing fixture specs
└── tests/                             # unittest suite (python3 -m unittest discover -s tests)

Installed into a project (.specify/extensions/evaluator/):
├── results/                            # Individual evaluator result files
│   ├── <evaluator-id>-<phase>-<ts>.json
│   └── composed-<phase>-<ts>.json
└── reports/                            # Human-readable reports (markdown format)
    └── report-<phase>-<ts>.md
```

## Security reporting

Report suspected vulnerabilities privately using the process in
[SECURITY.md](SECURITY.md). Ordinary bugs and enhancement requests belong in
[GitHub Issues](https://github.com/electrohire/spec-kit-evaluator/issues).

## License

MIT — see the [LICENSE](./LICENSE).
