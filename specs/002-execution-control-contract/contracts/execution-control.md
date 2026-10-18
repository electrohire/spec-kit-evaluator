# Contract invariants (design, implementation pending)

Inputs are untrusted bounded data. Reject unknown versions, fields where strict schema applies, duplicate identities/JSONkeys, malformed hashes/timestamps/statuses, path escapes and arbitrary command execution during ingest. Never equate absent evidence with successful verification.

Round trip must preserve explicit epistemic status, scoped applicability, record identity and provenance. In-memory calls receive the same validation as JSON calls. Every gate failure has a stable reason and evidence pointer. Any unsupported future engine/evaluator contract produces an actionable error.

Version negotiation must preserve1.0 callers and validate new preflight routing before use. Python/Bash/PowerShell must agree on schema errors, missing/stale evidence and strict/majority/optimistic compositions; hard malformed contract always blocks.
