# Proposed user workflow (not yet shipped)

Ask the agent: “Implement requirements R01 and R02. Identify linked tests and unresolved assumptions before changing files; capture actual verification and hand off unresolved gaps afterward.”

The operation skill follows preflight → implementation → explicit evidence capture → freshness/link gate → compact context handoff. CLI/Python exposes the same deterministic behavior. Install released engine with `python -m pip install applied-epistemic-engineering` or SpecKit integration with `specify extension add aee`; development features require this branch until a validated future release.

Current local prototype only:scope snapshots/freshness. Do not claim capture/preflight/context/evaluator1.1 is already shipped. Missing human authorization or trusted CI remains explicit; the tool does not certify correctness.
