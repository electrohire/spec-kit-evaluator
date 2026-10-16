#!/usr/bin/env python3
"""Compose multiple evaluator results with deterministic precedence.

Reads evaluator result JSON files from a results directory, validates
every input against the shipped evaluator-result schema, and produces a
composed result that itself validates against that schema.

Composition contract (Spec 003 FR-6):

* Fail closed on empty: zero usable results composes to outcome
  ``block`` with an explicit no-results finding — never ``pass``.
* Every input is schema-validated (``jsonschema`` is a hard dependency;
  its absence is a hard error, never a silent skip). A file that is
  malformed, schema-invalid, or whose payload ``phase`` differs from the
  requested phase is NOT skipped toward pass: it is wrapped as a
  blocking ``schema_violation`` finding and counts as a ``block`` vote
  under every strategy (per speckit.evaluator.run.md step 3.4).
* Evaluator identity for dedup/counting is the payload
  ``evaluator.id`` + ``version``, never the filename; duplicates of one
  evaluator count once (the lexicographically greatest filename — the
  latest timestamped run — wins, deterministically).
* Finding ids are namespaced ``<evaluator.id>:<finding.id>`` so ids
  cannot collide across evaluators; no ``_evaluator_id`` is injected
  into findings (the composed output must satisfy the schema's
  ``additionalProperties: false``).
* ``model_routing`` is omitted when no input routes (never ``null``),
  and the composed summary respects the schema's 500-char cap.
* ``majority`` / ``optimistic`` compositions are marked non-gating in
  ``metadata`` (``gating: false``); when they overturn a ``block`` the
  metadata records ``block_overridden: true`` and the per-evaluator
  outcomes remain visible in ``metadata.evaluator_results``.

Exit codes (gate contract, mirroring speckit.evaluator.report.md):
    0  composed outcome is ``pass`` or ``warn``
    1  composed outcome is ``iterate``, ``clarify``, or ``gather_evidence``
    2  composed outcome is ``block`` (including no-results and
       invalid-input blocks), or a hard error (missing schema,
       missing ``jsonschema``, unreadable schema)

Usage:
    compose_results.py --results-dir <path> --phase <phase>
                       [--strategy strict|majority|optimistic]
                       [--output <path>] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas" / "evaluator-result.schema.json"
)

# -- Outcome precedence for strict composition (most severe first) ----------
_STRICT_PRECEDENCE = [
    "block",
    "gather_evidence",
    "iterate",
    "clarify",
    "warn",
    "pass",
]

_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

# Gate exit contract (mirrors speckit.evaluator.report.md gate format).
_GATE_EXIT_CODES = {
    "pass": 0,
    "warn": 0,
    "iterate": 1,
    "clarify": 1,
    "gather_evidence": 1,
    "block": 2,
}


class ComposeError(Exception):
    """Hard composition error: named on stderr, exit 2, no output."""


# ---------------------------------------------------------------------------
# Schema handling
# ---------------------------------------------------------------------------

def _load_schema() -> dict[str, Any]:
    """Load the shipped schema; jsonschema is a hard dependency (FR-6.2)."""
    try:
        import jsonschema  # noqa: F401
    except ImportError as exc:
        raise ComposeError(
            "the 'jsonschema' package is required to compose evaluator "
            "results (Spec 003 FR-6.2); install it with "
            "'pip install -r requirements.txt'. Refusing to compose "
            "without schema validation."
        ) from exc
    if not _SCHEMA_PATH.is_file():
        raise ComposeError(
            f"evaluator result schema not found at {_SCHEMA_PATH}; "
            "the evaluator extension install is incomplete."
        )
    try:
        return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComposeError(
            f"could not load evaluator result schema at {_SCHEMA_PATH}: {exc}"
        ) from exc


def _schema_problem(data: Any, schema: dict[str, Any]) -> str | None:
    """First schema validation problem for *data*, or None if valid."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(data),
        key=lambda e: [str(p) for p in e.absolute_path],
    )
    if not errors:
        return None
    err = errors[0]
    path = ".".join(str(p) for p in err.absolute_path) or "<root>"
    return f"schema validation failed at {path}: {err.message}"


# ---------------------------------------------------------------------------
# Outcome resolution
# ---------------------------------------------------------------------------

def _resolve_outcome_strict(outcomes: list[str]) -> str:
    for candidate in _STRICT_PRECEDENCE:
        if candidate in outcomes:
            return candidate
    return "pass"


def _resolve_outcome_majority(outcomes: list[str]) -> str:
    counts = Counter(outcomes)
    max_count = max(counts.values())
    tied = [o for o, c in counts.items() if c == max_count]
    if len(tied) == 1:
        return tied[0]
    return _resolve_outcome_strict(tied)


def _resolve_outcome_optimistic(outcomes: list[str]) -> str:
    for candidate in reversed(_STRICT_PRECEDENCE):
        if candidate in outcomes:
            return candidate
    return "pass"


def _resolve_outcome(outcomes: list[str], strategy: str) -> str:
    if strategy == "majority":
        return _resolve_outcome_majority(outcomes)
    if strategy == "optimistic":
        return _resolve_outcome_optimistic(outcomes)
    return _resolve_outcome_strict(outcomes)


def _outcome_to_next_action(outcome: str, iterate_phase: str | None) -> dict[str, Any]:
    target_phase = iterate_phase if outcome == "iterate" else None
    return {
        "kind": outcome,
        "target_phase": target_phase,
        "message": f"Composed outcome: {outcome}.",
    }


# ---------------------------------------------------------------------------
# Findings helpers
# ---------------------------------------------------------------------------

def _severity_sort_key(finding: dict[str, Any]) -> tuple[int, str]:
    return (
        _SEVERITY_ORDER.get(finding.get("severity", "info"), 99),
        finding.get("id", ""),
    )


def _detect_contradictions(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect pairs of findings that contradict each other on one subject.

    Inputs are schema-validated before this runs, so every finding has
    id/severity/kind/subject and well-formed evidence_refs.
    """
    _negative_kinds = {
        "unsupported_claim",
        "contradiction",
        "missing_evidence",
        "unverified_assertion",
        "provenance_gap",
        "coverage_gap",
        "traceability_gap",
    }

    by_subject: dict[str, list[dict[str, Any]]] = {}
    for f in findings:
        by_subject.setdefault(f.get("subject", ""), []).append(f)

    contradictions: list[dict[str, Any]] = []
    for subject, group in by_subject.items():
        if len(group) < 2:
            continue
        kinds = {f.get("kind") for f in group}
        has_supporting = any(
            any(e.get("kind") in ("observed", "inferred")
                for e in f.get("evidence_refs", []))
            for f in group
        )
        has_contradicting = any(
            any(e.get("kind") in ("contradicted", "unsupported")
                for e in f.get("evidence_refs", []))
            for f in group
        )
        has_negative_kind = bool(kinds & _negative_kinds)
        has_positive_kind = bool(kinds - _negative_kinds)

        if (has_supporting and has_contradicting) or (
            has_positive_kind and has_negative_kind
        ):
            contradictions.append(
                {
                    "subject": subject,
                    "finding_ids": [f["id"] for f in group],
                    "description": f"Conflicting findings on subject '{subject}'",
                }
            )
    return contradictions


def _invalid_finding(filename: str, problem: str) -> dict[str, Any]:
    """Wrap an invalid input file as a blocking finding (FR-6.2/FR-6.4).

    Per speckit.evaluator.run.md step 3.4, an invalid result is wrapped
    in an error finding with outcome block — never skipped toward pass
    and never a composer crash.
    """
    description = (
        f"Invalid evaluator result '{filename}' was not composed: {problem}. "
        "The invalid result is wrapped as a blocking finding; composition "
        "fails closed rather than skipping it toward pass."
    )
    return {
        "id": f"invalid:{filename}",
        "severity": "critical",
        "kind": "schema_violation",
        "subject": filename,
        "description": description[:500],
        "evidence_refs": [
            {"ref": filename, "kind": "observed", "description": problem[:500]}
        ],
        "provenance_refs": [filename],
        "uncertainty": "none",
        "recommended_action": "block",
        "rationale": (
            "An evaluator result that cannot be validated cannot certify "
            "anything; it blocks composition (Spec 003 FR-6.2)."
        ),
    }


# ---------------------------------------------------------------------------
# Input loading / selection
# ---------------------------------------------------------------------------

def _classify_file(
    filepath: Path, phase: str, schema: dict[str, Any]
) -> tuple[str, Any]:
    """Classify one candidate file.

    Returns ("valid", result_dict) or ("invalid", problem_string).
    Malformed JSON is a named problem here, never an exception (FR-6.4).
    """
    try:
        raw = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return "invalid", f"unreadable result file: {exc}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return (
            "invalid",
            f"malformed JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})",
        )
    problem = _schema_problem(data, schema)
    if problem is not None:
        return "invalid", problem
    if data.get("phase") != phase:
        return (
            "invalid",
            f"phase mismatch: payload phase '{data.get('phase')}' "
            f"!= requested phase '{phase}'",
        )
    return "valid", data


def _select_latest(
    candidates: list[tuple[str, dict[str, Any]]]
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """Deduplicate by payload identity (evaluator.id + version) (FR-6.5).

    The lexicographically greatest filename wins — result filenames end
    in an ISO-8601 basic timestamp, so this is the latest run, chosen
    deterministically (never by mtime). Returns (selected, duplicates).
    """
    by_identity: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    duplicates: list[str] = []
    for name, data in sorted(candidates, key=lambda item: item[0]):
        identity = (data["evaluator"]["id"], data["evaluator"]["version"])
        if identity in by_identity:
            duplicates.append(by_identity[identity][0])
        by_identity[identity] = (name, data)
    selected = sorted(by_identity.values(), key=lambda item: item[0])
    return selected, duplicates


# ---------------------------------------------------------------------------
# Model routing merge
# ---------------------------------------------------------------------------

def _merge_model_routing(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Merge model routing from validated inputs (fixes RT4-L1).

    The winning routing contributes its tier, its reason, its headline
    estimates AND its tier breakdown, so the merged block never mixes
    one evaluator's totals with another's breakdown. Escalation
    triggers are merged, deduplicated, deterministically ordered, and
    capped at 5. Routings without a ``recommended_tier`` carry no
    recommendation and are ignored.
    """
    routings = [
        r["model_routing"]
        for r in results
        if isinstance(r.get("model_routing"), dict)
        and r["model_routing"].get("recommended_tier")
    ]
    if not routings:
        return None

    precedence = {"premium": 3, "portfolio": 2, "standard": 2, "budget": 1}
    winner: dict[str, Any] | None = None
    best_key: tuple[int, str] | None = None
    for routing in routings:
        tier = routing["recommended_tier"]
        key = (precedence.get(tier, 0), tier)
        if best_key is None or key > best_key:
            best_key = key
            winner = routing
    assert winner is not None

    triggers: dict[tuple[str, str], dict[str, Any]] = {}
    for routing in routings:
        for trigger in routing.get("escalation_triggers", []):
            triggers[(trigger["condition"], trigger["escalate_to"])] = trigger
    merged_triggers = [triggers[key] for key in sorted(triggers)][:5]

    merged: dict[str, Any] = {"recommended_tier": winner["recommended_tier"]}
    reason = f"[Composed from {len(routings)} evaluator(s)] {winner.get('reason', '')}".strip()
    if reason:
        merged["reason"] = reason[:300]
    if merged_triggers:
        merged["escalation_triggers"] = merged_triggers
    if "estimated_tokens" in winner:
        merged["estimated_tokens"] = winner["estimated_tokens"]
    if "estimated_cost_usd" in winner:
        merged["estimated_cost_usd"] = winner["estimated_cost_usd"]
    if winner.get("tier_breakdown"):
        merged["tier_breakdown"] = winner["tier_breakdown"]
    return merged


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def _composed_shell(
    phase: str, strategy: str, outcome: str, summary: str,
    findings: list[dict[str, Any]], next_action: dict[str, Any],
    metadata_extra: dict[str, Any], state: dict[str, Any],
    model_routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_ms": 0,
        "artifacts_evaluated": [],
        "deterministic": True,
        "composition_strategy": strategy,
    }
    metadata.update(metadata_extra)
    composed: dict[str, Any] = {
        "schema_version": "1.0",
        "evaluator": {
            "id": "composed",
            "version": "1.0",
            "name": f"Composed ({strategy})",
        },
        "phase": phase,
        "outcome": outcome,
        "summary": summary[:500],
        "findings": findings,
        "next_action": next_action,
        "metadata": metadata,
        "state": state,
    }
    if model_routing is not None:
        composed["model_routing"] = model_routing
    return composed


def _no_results_composed(
    phase: str, strategy: str, detail: str
) -> dict[str, Any]:
    """Fail-closed composition for an empty result set (FR-6.1)."""
    summary = (
        f"No evaluator results for phase '{phase}': composition requires "
        "at least one valid evaluator result and fails closed — absence "
        "of evidence is not a pass. "
        f"{detail}"
    )
    finding = {
        "id": "composed:NO-RESULTS",
        "severity": "critical",
        "kind": "missing_evidence",
        "subject": phase,
        "description": (
            "No valid evaluator results were available to compose for "
            f"phase '{phase}'. A missing/crashed evaluator or a typo'd "
            "phase must never read downstream as a green gate."
        ),
        "evidence_refs": [],
        "provenance_refs": [],
        "uncertainty": "insufficient_evidence",
        "recommended_action": "block",
        "rationale": "Fail-closed composition (Spec 003 FR-6.1).",
    }
    return _composed_shell(
        phase,
        strategy,
        "block",
        summary,
        [finding],
        {
            "kind": "block",
            "target_phase": None,
            "message": f"No evaluator results found for phase '{phase}'.",
        },
        {
            "evaluator_count": 0,
            "contradictory_findings": [],
            "evaluator_results": [],
            "invalid_results": [],
            "duplicate_results_ignored": [],
            "gating": strategy == "strict",
            "no_results": True,
        },
        {},
    )


def _lane_lag_summary(lane_states: list[dict[str, Any]]) -> str:
    """One headline sentence naming lane-2 lag, or "" when no
    carried lane state lags (Spec 004 P5-V2).

    Lag signals, all read from the carried records: claims below
    the explained stage, verified-but-unexplained claims, capped or
    attribution-contested counts where the record carries them,
    and residual `not_understood` entries. Counts are reported as
    the records state them; nothing is scored or combined.
    """
    parts: list[str] = []
    for state in lane_states:
        lane_2 = state.get("lane_2")
        bundle = lane_2.get("bundle") if isinstance(lane_2, dict) else None
        if not isinstance(bundle, dict):
            bundle = lane_2 if isinstance(lane_2, dict) else {}
        signals: list[str] = []
        below = bundle.get("below_explained")
        if isinstance(below, int) and below:
            signals.append(f"{below} claim(s) below the explained stage")
        unexplained = bundle.get("verified_unexplained")
        if isinstance(unexplained, int) and unexplained:
            signals.append(f"{unexplained} verified-but-unexplained claim(s)")
        unknowns = state.get("not_understood") or []
        if unknowns:
            signals.append(f"{len(unknowns)} residual unknown(s) not understood")
        if signals:
            parts.append(f"{state['evaluator_id']}: " + ", ".join(signals))
    if not parts:
        return ""
    return (
        "Lane 2 (human acceptance) lags lane 1 (machine verification) — "
        + "; ".join(parts)
        + ". A composed outcome is a checking-stage decision, not acceptance or digestion."
    )


def compose_results(
    results_dir: Path,
    phase: str,
    strategy: str = "strict",
    *,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose all evaluator results for a phase into one aggregate result.

    Raises ComposeError on hard errors (missing schema / jsonschema).
    The returned dict always validates against the shipped schema.
    """
    if schema is None:
        schema = _load_schema()

    if not results_dir.is_dir():
        composed = _no_results_composed(
            phase, strategy, f"Results directory not found: {results_dir}."
        )
        _assert_composed_valid(composed, schema)
        return composed

    result_files = sorted(results_dir.glob(f"*-{phase}-*.json"))
    result_files = [f for f in result_files if not f.name.startswith("composed-")]

    valid_candidates: list[tuple[str, dict[str, Any]]] = []
    invalid: list[tuple[str, str]] = []
    for fp in result_files:
        status, payload = _classify_file(fp, phase, schema)
        if status == "valid":
            valid_candidates.append((fp.name, payload))
        else:
            invalid.append((fp.name, payload))

    selected, duplicates = _select_latest(valid_candidates)
    results = [data for _, data in selected]

    if not results and not invalid:
        composed = _no_results_composed(
            phase,
            strategy,
            "The results directory contains no result files for this phase."
            if not result_files
            else "No result files remained after filtering.",
        )
        _assert_composed_valid(composed, schema)
        return composed

    # -- Findings: namespaced per evaluator (FR-6.5/T606), plus wrapped
    #    invalid-input findings.
    all_findings: list[dict[str, Any]] = []
    for r in results:
        eid = r["evaluator"]["id"]
        for f in r.get("findings", []):
            namespaced = dict(f)
            namespaced["id"] = f"{eid}:{f['id']}"
            all_findings.append(namespaced)
    for filename, problem in invalid:
        all_findings.append(_invalid_finding(filename, problem))
    all_findings.sort(key=_severity_sort_key)

    # -- Outcome: invalid inputs vote block under every strategy (the
    #    wrapped result's outcome is block, per run.md step 3.4).
    outcomes = [r["outcome"] for r in results] + ["block"] * len(invalid)
    composed_outcome = _resolve_outcome(outcomes, strategy)

    gating = strategy == "strict"
    block_overridden = "block" in outcomes and composed_outcome != "block"

    # -- Iterate target: most common target_phase among iterate results,
    #    deterministic tie-break (frequency, then alphabetical).
    iterate_phases = [
        r.get("next_action", {}).get("target_phase")
        for r in results
        if r["outcome"] == "iterate"
        and isinstance(r.get("next_action"), dict)
        and r["next_action"].get("target_phase")
    ]
    most_common_iterate = None
    if iterate_phases:
        phase_counts = Counter(iterate_phases)
        most_common_iterate = sorted(
            phase_counts.items(), key=lambda x: (-x[1], x[0])
        )[0][0]

    contradictions = _detect_contradictions(all_findings)
    model_routing = _merge_model_routing(results)

    # -- Lane states (Spec 004 P5-V1/V2): an input result may carry
    #    the AEE lane pair in metadata.lanes (lane 1 machine
    #    verification, lane 2 human acceptance). Composition carries
    #    each pair through VERBATIM, per evaluator — the lanes are
    #    never merged, averaged, or reduced to a single figure
    #    (lane 2 contains no score, and none is invented here).
    lane_states: list[dict[str, Any]] = []
    for r in results:
        metadata = r.get("metadata")
        if not isinstance(metadata, dict):
            continue
        lanes = metadata.get("lanes")
        if not isinstance(lanes, dict):
            continue
        lane_states.append(
            {
                "evaluator_id": r["evaluator"]["id"],
                "lane_1": lanes.get("lane_1"),
                "lane_2": lanes.get("lane_2"),
                "not_understood": metadata.get("not_understood") or [],
            }
        )
    lane_lag = _lane_lag_summary(lane_states)

    evaluator_states: dict[str, Any] = {}
    for r in results:
        if "state" in r:
            evaluator_states[r["evaluator"]["id"]] = r["state"]

    evaluator_summaries: list[dict[str, Any]] = [
        {
            "evaluator_id": r["evaluator"]["id"],
            "outcome": r["outcome"],
            "findings_count": len(r.get("findings", [])),
        }
        for r in results
    ] + [
        {
            "evaluator_id": f"invalid:{filename}",
            "outcome": "block",
            "findings_count": 1,
            "invalid": True,
            "file": filename,
            "reason": problem,
        }
        for filename, problem in invalid
    ]

    outcomes = ", ".join(
        f"{s['evaluator_id']}={s['outcome']}" for s in evaluator_summaries
    )
    summary = (
        f"{len(results)} evaluator(s) ran. "
        f"Outcomes: {outcomes}. "
        f"{len(all_findings)} finding(s) total."
    )
    if invalid:
        summary += (
            f" {len(invalid)} invalid result file(s) were wrapped as "
            "blocking findings."
        )
    if not gating:
        summary += f" Strategy '{strategy}' is non-gating (advisory)."
    if lane_lag:
        # P5-V2: lag is stated in the headline itself, pass or not —
        # a lane-1-green composed outcome must never read as
        # settled, accepted, or digested work.
        summary += f" {lane_lag}"

    metadata_extra: dict[str, Any] = {
        "evaluator_count": len(results),
        "contradictory_findings": contradictions,
        "evaluator_results": evaluator_summaries,
        "invalid_results": [
            {"file": filename, "reason": problem} for filename, problem in invalid
        ],
        "duplicate_results_ignored": duplicates,
        "gating": gating,
    }
    if lane_states:
        metadata_extra["lane_states"] = lane_states
    if not gating:
        metadata_extra["non_gating_reason"] = (
            f"Strategy '{strategy}' composes advisory outcomes; the result "
            "is marked non-gating and must not be used as a release gate "
            "(Spec 003 FR-6.6)."
        )
    if block_overridden:
        metadata_extra["block_overridden"] = True

    composed = _composed_shell(
        phase,
        strategy,
        composed_outcome,
        summary,
        all_findings,
        _outcome_to_next_action(composed_outcome, most_common_iterate),
        metadata_extra,
        evaluator_states,
        model_routing,
    )
    _assert_composed_valid(composed, schema)
    return composed


def _assert_composed_valid(composed: dict[str, Any], schema: dict[str, Any]) -> None:
    problem = _schema_problem(composed, schema)
    if problem is not None:
        raise ComposeError(
            f"internal error: composed result failed schema validation: {problem}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compose multiple evaluator results with deterministic precedence."
    )
    parser.add_argument(
        "--results-dir",
        required=True,
        type=Path,
        help="Directory containing evaluator result JSON files.",
    )
    parser.add_argument(
        "--phase",
        required=True,
        help="Lifecycle phase to compose results for (e.g., after_plan).",
    )
    parser.add_argument(
        "--strategy",
        choices=["strict", "majority", "optimistic"],
        default="strict",
        help="Composition strategy (default: strict).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write composed result to this file instead of stdout.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output raw JSON to stdout (default when --output is not specified).",
    )

    args = parser.parse_args(argv)

    try:
        composed = compose_results(
            results_dir=args.results_dir,
            phase=args.phase,
            strategy=args.strategy,
        )
    except ComposeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if composed["metadata"].get("no_results"):
        print(
            f"Error: no evaluator results found for phase '{args.phase}' "
            f"in {args.results_dir}; composing a fail-closed block result.",
            file=sys.stderr,
        )
    for entry in composed["metadata"].get("invalid_results", []):
        print(
            f"Error: invalid evaluator result '{entry['file']}': {entry['reason']}",
            file=sys.stderr,
        )

    output_json = json.dumps(composed, indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"Composed result written to {args.output}")
    else:
        print(output_json)

    return _GATE_EXIT_CODES[composed["outcome"]]


if __name__ == "__main__":
    sys.exit(main())
