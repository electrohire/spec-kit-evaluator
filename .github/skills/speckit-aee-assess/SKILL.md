---
name: speckit-aee-assess
description: Assess explicit claims and emit AEE and Evaluator Contract results
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: ElectroHire
  source: extension:aee
---

# Aee Assess Skill

# AEE Assess

Run the complete Applied Epistemic Engineering pipeline against explicitly identified claims in a JSON or Markdown artifact.

## User input

```text
$ARGUMENTS
```

Accept `artifact=<path>`, `phase=<after_specify|after_plan|after_tasks|after_implement>`, and optional `threshold=<0..1>`. Infer the current phase and its primary artifact when omitted; if ambiguity remains, ask before running.

Optional: `policy=<true|false>` attaches the engine's policy gates (per-claim ACCEPT / CHALLENGE / ABSTAIN verdicts; tune with `min_independent_sources=<n>` and `contested_threshold=<0..0.75>`), and `reliability=<path>` points at a ReliabilityTable JSON whose measured per-source reliability blends into scoring.

## Prerequisites

1. Do not install the engine yourself. The runner uses an `aee` engine in the range >=1.5.0,<2 from the active Python; otherwise its first run installs `applied-epistemic-engineering>=1.5.0,<2` into `.specify/extensions/aee/.runtime` (this needs network access once). If the runner refuses (exit 2) because that install is disabled (`SPECKIT_AEE_AUTO_INSTALL=0`) or failed, stop and relay its message, which names the manual `python -m pip install "applied-epistemic-engineering>=1.5.0,<2"` command. The runner checks the engine version itself at startup, so a below-floor engine cannot silently produce incomparable scores.
2. The spec-kit-evaluator extension (https://github.com/electrohire/spec-kit-evaluator) is a **required companion** to this adapter — the pair is one system. AEE is one evaluator among many by design: the Evaluator Contract result assess produces (written by the AEE engine itself, via its `--evaluator-output`) is meant to be composed with other evaluators' results through that common evaluator, so every evaluator's output is handled the same way. The runner enforces the requirement itself: with the evaluator extension missing from the project, `assess` first installs the pinned, SHA-256-verified spec-kit-evaluator release through `specify extension add evaluator` (this needs `specify` on PATH and network access once). It refuses with exit 2, naming the missing extension and the manual install command, before the engine runs or anything is written, only when that install is disabled (`SPECKIT_AEE_AUTO_INSTALL=0`) or fails. If evaluator commands were just installed, the coding agent may need a restart to see them. The runner reports `evaluator_extension_present` in its JSON so the installed pair is visible in every run record.
3. Resolve the project root and source artifact. Never follow symlinks or read outside the project root.

Use threshold `0.70` when omitted. The adapter does not load YAML configuration; pass explicit flags for overrides. The engine repository is https://github.com/electrohire/applied-epistemic-engineering.

## Execution

Run:

```bash
python .specify/extensions/aee/scripts/python/run_aee.py assess --input "<artifact>" --phase "<phase>" --threshold "<threshold>"
```

Quote every path and value verbatim exactly as shown; never eval, word-split, or otherwise re-interpret user-supplied arguments — an artifact path may contain spaces or shell metacharacters and must reach the runner as one argument.

With `policy=true`, append `--policy` (plus any threshold overrides); with `reliability=<path>`, append `--reliability "<path>"`.

The adapter writes a rich assessment under `.specify/extensions/aee/assessments/`, an Evaluator Contract result under `.specify/extensions/evaluator/results/`, and a chained ledger record under `.specify/extensions/aee/ledger/`.

Claim bundles written before the Spec 004 stage vocabulary have no `stage` field and strict loading refuses them. The runner therefore drives the engine's recorded `--lenient` compatibility mode (when the installed engine advertises it): missing stages default to `created`, and the default is on the record — the assessment metadata carries `loading_mode: "lenient"` and names the defaulted claims in `stage_defaulted_claims`. Treat a lenient-loaded assessment as transitional: add explicit `stage` values (or run `aee migrate`) so the project's bundles load strictly.

The documented loop is assess → verify-ledger (FR-8.2): after appending, the runner itself verifies the ledger chain and reports the verdict in its JSON summary as `ledger_verification` (`valid`, `entries`, `head_hash`, `errors`), alongside the assessment, evaluator-result, and ledger paths. Read that verdict before trusting the record; a `valid: false` verdict means the chain — including records from before this run — does not verify. With `--no-ledger`, no append and no verification happen and `ledger_verification` is `null` — never a fabricated verdict. The bare engine CLI ledgers by default with identical semantics (same default path, `--no-ledger` opt-out, `--ledger` to choose another path). The assessment JSON file is a working copy; the ledger entry, which records the assessment's SHA-256, is the record of what was assessed (FR-8.3).

The runner also stamps its own version into the assessment as `metadata.extension_version` (FR-4.2). The stamp is applied before the ledger append hashes the assessment, so the ledger record covers the stamped file exactly. The engine stamps `metadata.engine_version` itself; assessments produced by the bare CLI have no `extension_version` key — its absence means no extension produced the run, and no tool fills it in after the fact.

Report the outcome, confidence threshold, claim/finding counts, unresolved contradictions, recommended recovery, and exact output paths. When the policy is attached, also report the verdict counts (accept / challenge / abstain / unjudged) and name the abstained claims — an abstention is a deliberate non-verdict, not a low score — and the unjudged claims separately: an unjudged claim sits at stage `created` and has not been through checking at all, which is a different statement from abstention.

Report statuses as the assessment's `reported_statuses` — the stage-capped vocabulary — never the author-declared `status` fields: a claim at stage `checked` reports at most `partially_supported`, however its author labelled it, and the runner's JSON carries the same values in `verdict_display`. Report the two lanes as a pair, always: lane 1 (machine verification — the score, threshold, and outcome) and lane 2 (human acceptance — the stage counts, exposition coverage, verified-but-unexplained count, and cap reasons, in `verdict_display.lanes`). A green lane 1 with a lagging lane 2 is checked-not-settled work; never present a lane-1 outcome as acceptance, digestion, or settled truth. Render the assessment's `not_understood` entries with every verdict: they state what this assessment does not establish, and a verdict presented without them is incomplete. Do not describe an assessment as proof, certification, or truth.

Composition through the evaluator extension is the standard path, not an extra: when other evaluators ran at the same phase, compose this result with theirs by running `python .specify/extensions/aee/scripts/python/run_aee.py compose --phase "<phase>" --strategy strict`. That runs the evaluator extension's own Python composer on the runner's interpreter, where its `jsonschema>=4.0` dependency is installed along with the engine. `/speckit-evaluator-compose` performs the same composition, but it runs the composer variant chosen by the project's script type with that variant's own prerequisites (`jq` for Bash, `jsonschema` in the project's Python for Python), which AEE does not install. Composer exit codes pass through: 0 pass/warn, 1 recovery needed, 2 block or error.

## Claim field vocabulary

The AEE engine validates every claim with `Claim.from_dict` and rejects the
whole bundle on the first invalid value. Use exactly these lowercase values;
`id` must be non-empty, and `confidence`, when present, must be between 0 and 1.

- `kind`: observation, requirement, assumption, inference, hypothesis, decision, prediction, compliance
- `status`: draft, supported, partially_supported, unsupported, contradicted, unverifiable, superseded
- `stage`: created, checked, explained, accepted, digested — the claim's lifecycle stage (Spec 004). It advances only through recorded stage events, never by score, and it caps the status an assessment may report and the verdict a claim may receive. A bundle that omits `stage` loads leniently with the default `created` recorded as defaulted; strict loading names the missing field.
- `headline`: optional boolean marking a headline result; a headline claim should decompose via `depends_on` into sub-claims carrying `role`: statement-fidelity, evidence-verification, novelty, attribution, significance. An incomplete decomposition caps the headline at stage `created`.
- `uncertainty`: none, low, medium, high, insufficient_evidence
- `severity`: critical, high, medium, low, info
- evidence `kind`: observed, inferred, asserted, contradicted, unsupported, exposition — `exposition` is a named human's explanation of the claim (its `source_id` must resolve in the project's identity registry, `identities.json` beside the bundle or `--identity-registry`); it is lane-2 evidence: it explains, it does not verify.
- evidence `direction`: supports, contradicts, context
- evidence `source_quality`: primary, secondary, tertiary, artifact, test, human, model, unknown

## Guardrails

- Assess only claims with stable IDs; do not silently convert free prose into claims.
- Preserve counterevidence and contradictions.
- Model output is `asserted`, never `observed`.
- Do not modify the source artifact during assessment.
