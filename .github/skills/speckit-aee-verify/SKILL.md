---
name: speckit-aee-verify
description: Verify the tamper-evident AEE ledger
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: ElectroHire
  source: extension:aee
---

# Aee Verify Skill

# AEE Verify

Verify every link in the AEE SHA-256 JSONL ledger.

## User input

```text
$ARGUMENTS
```

Use `.specify/extensions/aee/ledger/epistemic-ledger.jsonl` unless `ledger=<path>` is given. Resolve it inside the project root, refuse symlinked components, and run:

```bash
python .specify/extensions/aee/scripts/python/run_aee.py verify --ledger "<path>"
```

Report validity, entry count, head hash, and every error. State explicitly that a valid chain proves continuity of the retained records only—not truth, identity, trusted time, completeness before the first record, or compliance.
