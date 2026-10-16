---
name: speckit-aee-challenge
description: Adversarially challenge claims and identify bounded recovery work
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: ElectroHire
  source: extension:aee
---

# Aee Challenge Skill

# AEE Challenge

Challenge explicit claims for observability, atomicity, boundaries, falsifiability, evidence independence, provenance, missing dependencies, cycles, and contradictions.

## User input

```text
$ARGUMENTS
```

Resolve `artifact=<path>` and optional `phase=<phase>` using the same prerequisites and path rules as `/speckit-aee-assess`. Run the AEE adapter's `challenge` operation, which emits a deterministic failure-mode projection (failures plus bounded recovery proposals) rather than aggregate scoring.

```bash
python .specify/extensions/aee/scripts/python/run_aee.py challenge --input "<artifact>" --phase "<phase>"
```

For every failure in the emitted projection, report:

- stable failure and claim IDs;
- the deterministic challenge that triggered;
- the inspectable breakpoint;
- evidence references and their kinds;
- a bounded recovery action and how its completion can be verified.

Never delete a conflicting position, manufacture evidence, or accept model self-attestation as independent support. Recommend rerunning `/speckit-aee-assess` after recovery work changes the source artifact.
