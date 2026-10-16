---
name: speckit-aee-gate
description: Apply a CI-friendly decision gate to an AEE assessment
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: ElectroHire
  source: extension:aee
---

# Aee Gate Skill

# AEE Gate

Apply the AEE exit-code contract to an existing rich assessment.

## User input

```text
$ARGUMENTS
```

Resolve `assessment=<path>` inside `.specify/extensions/aee/assessments/` unless an explicit in-project path is supplied. Refuse symlinks and run:

```bash
python .specify/extensions/aee/scripts/python/run_aee.py gate --input "<assessment>"
```

To gate the most recent assessment for a lifecycle phase instead of naming a file, use the pointer that `assess` maintains:

```bash
python .specify/extensions/aee/scripts/python/run_aee.py gate --latest "<phase>"
```

`--latest` refuses (exit 2) when no assessment has been recorded for the phase, and prints the resolved assessment's age to stderr — check it before trusting the verdict, because it gates whatever the pointer names, however old. `--input` and `--latest` are mutually exclusive.

Exit semantics are: 0 for `pass` or `warn`, 1 for `iterate`, `clarify`, or `gather_evidence`, and 2 for `block` or malformed input. For multi-evaluator release policy, use `/speckit-evaluator-report format=gate` on a composed result.

A gate verdict is a lane-1 (machine verification) decision: it says the recorded evidence passed the recorded checks. It does not say any human has explained, accepted, or digested the claims — read the assessment's lane-2 state (`lanes.lane_2`) and its `not_understood` entries alongside the gate result before treating gated work as settled. A gated assessment that lacks a `not_understood` statement is itself incomplete and the gate refuses it (exit 2).
