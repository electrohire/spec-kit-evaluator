---
name: speckit-aee-review
description: Diff two AEE assessments into a materiality-filtered review queue
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: ElectroHire
  source: extension:aee
---

# Aee Review Skill

# AEE Review

Diff two rich AEE assessments and emit the bounded queue a reviewer actually owes attention: claims whose propagated score moved by at least the materiality threshold, policy verdict flips, and added/removed claims.

## User input

```text
$ARGUMENTS
```

Accept `previous=<path>` and `current=<path>` (assessment JSON files, usually under `.specify/extensions/aee/assessments/`), optional `materiality=<0..1>` (default `0.05`, the engine's validated hysteresis point), and optional `limit=<n>` top-k budget applied after sorting by movement size.

## Prerequisites

1. Do not install the engine yourself. The runner uses an `aee` engine in the range >=1.5.0,<2 from the active Python; otherwise its first run installs `applied-epistemic-engineering>=1.5.0,<2` into `.specify/extensions/aee/.runtime` (this needs network access once). If the runner refuses (exit 2) because that install is disabled (`SPECKIT_AEE_AUTO_INSTALL=0`) or failed, stop and relay its message, which names the manual `python -m pip install "applied-epistemic-engineering>=1.5.0,<2"` command.
2. Resolve both assessment paths inside the project root. Never follow symlinks or read outside the project root.

## Execution

Run:

```bash
python .specify/extensions/aee/scripts/python/run_aee.py review --previous "<path>" --current "<path>"
```

The runner prints the review queue as JSON. Report the moved claims (largest first, with before/after scores and bands), any verdict changes, and added/removed claims. An empty queue is a real result: it means nothing moved materially between the two assessments — say so rather than re-reviewing everything.
