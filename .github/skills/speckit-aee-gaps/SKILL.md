---
name: speckit-aee-gaps
description: Generate or update the gap register from a verification matrix and test
  evidence
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: ElectroHire
  source: extension:aee
---

# Aee Gaps Skill

# AEE Gaps

Generate or update the project gap register (GAPS.md) by cross-referencing the verification matrix against available test evidence.

## User input

```text
$ARGUMENTS
```

Accept `matrix=<path>`, `evidence=<dir>`, and optional `output=<path>`, `close=<GAP-ID>`, `existing=<path>`. Infer the verification matrix at `.specify/extensions/aee/docs/verification-matrix.md` and the evidence directory at `evidence/` when omitted.

## Prerequisites

1. Do not install the engine yourself. The runner uses an `aee` engine in the range >=1.5.0,<2 from the active Python; otherwise its first run installs `applied-epistemic-engineering>=1.5.0,<2` into `.specify/extensions/aee/.runtime` (this needs network access once). If the runner refuses (exit 2) because that install is disabled (`SPECKIT_AEE_AUTO_INSTALL=0`) or failed, stop and relay its message, which names the manual `python -m pip install "applied-epistemic-engineering>=1.5.0,<2"` command.
2. Confirm the verification matrix file exists. If absent, stop and recommend creating `.specify/extensions/aee/docs/verification-matrix.md` first.
3. Resolve the project root. Never follow symlinks or read outside the project root.

## Execution

Run:

```bash
python .specify/extensions/aee/scripts/python/run_aee.py gaps --matrix "<matrix>" --evidence "<evidence>" --output "<output>"
```

Manual closure does not validate evidence automatically. Inspect passing evidence first; then use the existing register as `--output` to close a specific gap:

```bash
python .specify/extensions/aee/scripts/python/run_aee.py gaps --matrix "<matrix>" --evidence "<evidence>" --output "<output>" --close GAP-XXX
```

The adapter writes the gap register only when `output=<path>` is supplied; otherwise the engine prints it to stdout. Choose an explicit in-project path such as `GAPS.md`. Pass `--existing "<prior-register>"` when regenerating if you intend to preserve prior closed gaps. The adapter does not read the YAML reference configuration.

Evidence confinement is a runner-side pre-flight: before the engine runs, the adapter walks the evidence tree and refuses (exit 2, naming the offenders) any symlink and any entry resolving outside the project root, so out-of-root data can never close a gap. Keep evidence as real files inside the project.

Report the open/closed counts and list any open gaps. Do not describe the register as proof of correctness — it tracks verification coverage only.

## Guardrails

- Only close gaps when evidence explicitly shows a passing test.
- Pass `--existing` to preserve previously closed gaps across regenerations; review whether the old evidence still applies.
- Do not modify the verification matrix during gap generation.
- The gap register is a tracking artifact, not a certification.
