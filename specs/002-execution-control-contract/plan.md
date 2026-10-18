# Implementation Plan: Execution-evidence control loop

**Branch**:feat/execution-evidence-control-loop | **Date**:2026-10-18 | **Spec**:[spec.md](spec.md)

## Summary

Validate an optional versioned execution-evidence contract and explicit before_implement phase; preserve1.0 envelopes and deterministic composition.

## Technical Context

**Language/Version**:Python3.11+/Bash+jq/PowerShell and JSON Schema
**Storage**:bounded strict JSON artifacts plus existing append-only anchored ledger; no database/network in core.
**Testing**:pytest/unittest, meaningful line+branch coverage including subprocesses, malformed-input fuzz, real engine/extension/composer integration, all9 supported platform/Python combinations.
**Performance Goals**:bounded file count, byte sizes, output and execution duration; deterministic offline validation. No universal latency or efficacy promise.
**Constraints**:no shell execution on ingest, no implicit trust escalation, no fabricated human approval, no stale/missing evidence pass. Python3.11 syntax. Baseline installed versions remain immutable.
**Scale/Scope**:explicit scoped files/requirements/test inventory, not repository-wide implicit trust.

## Constitution Check

Pre-design: PASS design separation, epistemic labels, deterministic fail-closed semantics, actual verification and immutable releases. Adapter/evaluator unfilled constitutions replaced with principles grounded in CONTRIBUTING/SECURITY and user request; not claimed historical approval. Post-design: PASS subject to actual tests and review; implementation validation is pending. No human acceptance asserted.

## Project Structure

- Feature documents:spec.md, research.md, data-model.md, contracts/execution-control.md, quickstart.md and tasks.md.
- Source:schemas/, scripts/python/compose_results.py and Bash/PowerShell composers.
- Tests:existing tests plus focused security/behavior regressions, fuzz corpus, CLI/subprocess and cross-component integration.

## Dependencies and sequencing

Engine primitives define evidence scope, provenance and decisions. Evaluator owns only shared envelope validation/composition. Adapter exposes engine via CLI/direct-agent/SpecKit operation skills. Integrate candidate source locally without changing frozen benchmark environment. Versioned release/public archive acceptance happens only after valid baseline completion and all product checks, followed by prospectively matched after benchmark.

## Complexity Tracking

No new service/scoring layer. Strict external CI identity needs a verifier policy boundary; a name/URL is never sufficient. Do not invent hosted signing infrastructure; unsupported producer identity stays untrusted/unknown. Commands execute only via explicit capture with argv and bounded timeout; callers remain responsible for OS authorization/isolation.
