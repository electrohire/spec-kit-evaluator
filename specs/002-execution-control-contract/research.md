# Research decisions

- Keep engine semantics and existing anchored ledger as backbone; do not add another score or Specsmith dependency.
- Scope applicability is explicit code/test/config bytes. Snapshot before/after command; changed or unreadable input cannot pass. Unscoped changes make no general correctness claim.
- Strict JSON/version/ID/path/size validation precedes semantic ingestion. Ingest never executes recorded commands. Evidence producer trust is an external verification policy, not a JSON assertion.
- Real tests are discovered/inventoried; a string link alone is insufficient. Approved non-test verification requires actual scoped human provenance. Collection errors/incomplete inventory remain unknown.
- Context carries original statuses/stages, contradictions, unknowns and evidence pointers under a bound; no silent promotion or dropped blocker.
- Measure cross-platform/subprocess coverage; local platform skips and shell parity are transparent. Baseline in-process engine89% is not completion.
- Preserve before-study frozen releases and all failed setup calls. Compare only prospectively matched after treatment once features validate; no predetermined savings result.
