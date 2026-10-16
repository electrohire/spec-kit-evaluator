---
name: speckit-aee-draft-claims
description: Draft atomic claims from a specification's requirements for human ratification
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: ElectroHire
  source: extension:aee
---

# Aee Draft Claims Skill

# AEE Draft Claims

Propose draft claims from a specification's stated requirements (functional requirements, user stories, acceptance criteria) and emit them as a claims bundle in engine format. Drafting is a proposal step: it lowers the authoring tax of writing claims by hand, and it ratifies nothing.

## User input

```text
$ARGUMENTS
```

Accept `spec=<path>` (a spec markdown file, or a feature directory containing `spec.md`) and optional `output=<path>`. When `output` is omitted, the bundle is written as `aee-claims.json` beside the spec.

## Prerequisites

1. Do not install the engine yourself. The runner uses an `aee` engine in the range >=1.5.0,<2 from the active Python; otherwise its first run installs `applied-epistemic-engineering>=1.5.0,<2` into `.specify/extensions/aee/.runtime` (this needs network access once). If the runner refuses (exit 2) because that install is disabled (`SPECKIT_AEE_AUTO_INSTALL=0`) or failed, stop and relay its message, which names the manual `python -m pip install "applied-epistemic-engineering>=1.5.0,<2"` command.
2. Drafting uses the engine's Python helper `aee.extract.draft_claims_from_spec` (the engine CLI has no drafting subcommand); the runner calls it from the same Python that provides the engine (the runtime environment above when it installed one). An engine without the helper makes the runner refuse cleanly with exit 2 — it never falls back to inventing claims itself.
3. Resolve the project root and the spec artifact. Never follow symlinks or read outside the project root.

## Execution

Run:

```bash
python .specify/extensions/aee/scripts/python/run_aee.py draft-claims --spec "<spec.md-or-feature-dir>"
```

With an explicit destination, append `--output "<path>"`.

The runner prints a JSON summary naming the bundle actually written, the claim count, how many drafts still carry a TODO falsifier, and the `depends_on` proposals (below). The drafting is deterministic and makes no model calls.

## What a draft is

- Every drafted claim is born `status: draft`. Its single evidence item is the requirement text itself, as modelled by the helper: `kind: asserted`, `source_quality: model` — never anything stronger.
- Each draft carries its source requirement reference in `source_ref` and a proposed falsification test, marked as proposed in the test text. A requirement whose text gives the helper nothing testable to anchor to gets an explicit `TODO` falsifier instead of an invented test.
- A draft whose falsifier is still a `TODO` is rejected by strict loading (`aee validate`, and any strict assess) until a human writes a real one. TODO drafts cannot sneak past that gate.

## depends_on proposals

Where a requirement's text explicitly references another requirement in the same spec, the helper scaffolds a `depends_on` proposal on the draft and records the source references under `metadata.depends_on_proposed_from`. The runner surfaces these in its JSON summary under `depends_on_proposals`. They are proposals in exactly the same sense as the claims themselves: a human confirms or removes them during ratification. Absence of a proposal means the spec stated no cross-reference — it is not evidence that no dependency exists.

## Guardrails

- The tool contains no code path that ratifies, supports, or upgrades a claim, or that upgrades a draft's evidence. Ratification is a recorded human edit to the bundle, never a runner or command action.
- Do not edit a draft's `status`, evidence `kind`, or `source_quality` on the tool's behalf; do not complete a TODO falsifier with an invented test — a falsifier is written by the human who owns the requirement, or the draft stays unfinished.
- Drafts are proposals from the spec's own text, not evidence about the world: model output is `asserted`, never `observed`.
- Do not modify the source spec during drafting.
