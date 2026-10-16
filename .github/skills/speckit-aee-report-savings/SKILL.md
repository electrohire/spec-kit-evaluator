---
name: speckit-aee-report-savings
description: Report measured RTK and Headroom token savings, never estimated
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: ElectroHire
  source: extension:aee
---

# Aee Report Savings Skill

# AEE Report Savings

Report token savings measured by the optional token-economy tools after a
large Spec Kit workflow, after implementation, or when asked how many tokens
were saved.

## User input

```text
$ARGUMENTS
```

Accept an optional reporting window in hours (default 168).

## Measurement rules

- Count only RTK and Headroom as token-saving tools.
- RTK saves shell-output tokens. Measure with `rtk gain`.
- Headroom saves context and tool-output tokens. Measure with
  `headroom perf --hours <N>`.
- Do not count token-router, Ollama, subagents, or state externalization as
  token savings. They are workflow tools, not savings channels.
- Never estimate. If a measurement source is missing or unparseable, report
  `n/a` with the reason.
- Keep RTK and Headroom separate. Add a combined total only when both values
  are measured in the same report. Never double-count.

## Execution

Run the policy helper:

```bash
python .specify/extensions/aee/scripts/python/aee_token_economy.py report --hours "<N>"
```

The helper degrades gracefully: a missing tool yields `n/a` with a reason,
never a zero and never an estimate.

## Report format

The helper prints JSON; report its values verbatim, per channel:

```json
{
  "rtk": {"used": true, "saved_tokens": 1234, "source": "rtk gain --format json"},
  "headroom": {"used": false, "saved_tokens": "n/a", "reason": "headroom not installed"},
  "combined_saved_tokens": "n/a",
  "policy": "…"
}
```

`used` is a JSON boolean (`true`/`false`, never `yes|no|n/a`); `saved_tokens`
is a measured number or the string `"n/a"` with a `reason`. `combined_saved_tokens`
is the sum only when both channels measured, otherwise `"n/a"`.

Save the report under `.specify/extensions/aee/reports/` when it belongs to a
feature workflow. Include the commands used as evidence. Do not print raw
tool logs that contain sensitive file paths or secrets.

## Guardrails

- A savings figure is a measurement claim: ground it in the tool output, or
  mark it `n/a`.
- Do not quote vendor marketing figures for any tool. Only measured values
  from this environment count.
