#!/usr/bin/env python3
"""Deterministic spec-structure reference evaluator (Spec 002 FR-7).

Checks a Spec Kit feature directory for the contract's basics and emits a
schema-valid evaluator result (the same envelope the AEE engine's
EvaluatorAdapter emits):

  * spec.md / plan.md / tasks.md presence
  * spec.md required sections (title, requirements, acceptance/success)
  * claims.json presence and strict-load validity (structural mirror of
    the engine's strict loader: object with a ``claims`` list, no unknown
    fields, non-empty ``id``/``text``, valid enum values, list-typed
    fields are lists of strings, no duplicate claim ids, no duplicate
    JSON keys)
  * every claim carries at least one falsification test
  * assessment.json presence (and that it parses as a JSON object)
  * tasks traceable to requirements: every task line in tasks.md carries
    a requirement reference, and every requirement id in spec.md is
    referenced from tasks.md

The evaluator is deliberately small and deterministic (no model calls):
same feature directory + same phase -> byte-identical result modulo the
``metadata.timestamp`` field (pin it with ``--timestamp`` for full
byte-identity). Its job is to prove the contract composes end-to-end,
not to judge epistemics — that remains AEE's role (FR-7.3).

Usage:
    spec_structure_evaluator.py --feature-dir <path> [--phase <phase>]
                                [--output <path>] [--timestamp <iso8601>]

Exit codes: 0 on a completed evaluation (the outcome lives in the
result), 2 on usage/IO errors (missing feature directory, bad phase).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVALUATOR_ID = "spec-structure"
EVALUATOR_VERSION = "1.0.0"
EVALUATOR_NAME = "Spec Structure (reference evaluator)"
EVALUATOR_URL = "https://github.com/electrohire/spec-kit-evaluator"

_VALID_PHASES = {
    "after_specify",
    "after_plan",
    "after_tasks",
    "after_implement",
    "after_analyze",
    "after_checklist",
    "after_clarify",
    "after_constitution",
    "after_converge",
    "after_taskstoissues",
}

# Structural mirror of the AEE engine's strict loader (engine 1.4.0,
# src/aee/model.py Claim._FIELDS / Evidence._FIELDS). Kept as data so a
# future engine field addition is a one-line change here.
_CLAIM_FIELDS = {
    "id", "text", "kind", "status", "boundary", "depends_on",
    "conflicts_with", "evidence", "assumptions", "alternatives",
    "falsification_tests", "uncertainty", "severity", "source_ref",
    "domain", "confidence", "confidence_band", "failures", "metadata",
    "dispositions",
}
_EVIDENCE_FIELDS = {
    "ref", "kind", "direction", "source_quality", "description",
    "source_id", "independent_of", "observed_at", "content_hash",
    "content_hash_status",
}
_CLAIM_KINDS = {
    "observation", "requirement", "assumption", "inference",
    "hypothesis", "decision", "prediction", "compliance",
}
_CLAIM_STATUSES = {
    "draft", "supported", "partially_supported", "unsupported",
    "contradicted", "unverifiable", "superseded",
}
_EVIDENCE_KINDS = {"observed", "inferred", "asserted", "contradicted", "unsupported"}
_LIST_OF_STRING_FIELDS = (
    "boundary", "depends_on", "conflicts_with", "assumptions",
    "alternatives", "falsification_tests",
)

_REQ_ID_RE = re.compile(r"\b(?:FR|NFR|REQ)-\d+\b")
_TASK_LINE_RE = re.compile(r"^\s*-\s*\[[ xX]\]")
_TASK_REF_RE = re.compile(r"\b(?:FR|NFR|REQ|US)-?\d+\b|§")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _finding(findings: list[dict[str, Any]], severity: str, kind: str,
             subject: str, description: str, action: str,
             ref: str) -> None:
    """Append a finding with the next deterministic SS-NNN id."""
    findings.append({
        "id": f"SS-{len(findings) + 1:03d}",
        "severity": severity,
        "kind": kind,
        "subject": subject,
        "description": description[:500],
        "evidence_refs": [{
            "ref": ref,
            "kind": "observed",
            "description": "Direct filesystem inspection by the spec-structure evaluator.",
        }],
        "provenance_refs": [ref],
        "uncertainty": "none",
        "recommended_action": action,
        "rationale": description[:500],
    })


def _no_dup_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key '{key}'")
        obj[key] = value
    return obj


def _claims_validity_problems(bundle: Any) -> list[str]:
    """Structural strict-load problems in a claims bundle (deterministic).

    Mirrors the engine strict loader's load-time rules; an empty list
    means the bundle would strict-load. Falsifier *presence* is a
    separate quality check, not a load failure.
    """
    problems: list[str] = []
    if not isinstance(bundle, dict):
        return ["claims bundle is not a JSON object"]
    if "claims" not in bundle:
        return ["claims bundle has no 'claims' key"]
    claims = bundle["claims"]
    if not isinstance(claims, list):
        return ["'claims' is not a list"]

    seen_ids: set[str] = set()
    for idx, claim in enumerate(claims):
        where = f"claims[{idx}]"
        if not isinstance(claim, dict):
            problems.append(f"{where}: claim is not an object")
            continue
        cid = claim.get("id")
        if isinstance(cid, str) and cid:
            where = f"claim '{cid}'"
            if cid in seen_ids:
                problems.append(f"{where}: duplicate claim id")
            seen_ids.add(cid)
        unknown = sorted(set(claim) - _CLAIM_FIELDS)
        if unknown:
            problems.append(f"{where}: unknown field(s): {', '.join(unknown)}")
        if not isinstance(cid, str) or not cid:
            problems.append(f"{where}: 'id' is missing or not a non-empty string")
        text = claim.get("text")
        if not isinstance(text, str) or not text:
            problems.append(f"{where}: 'text' is missing or empty")
        kind = claim.get("kind")
        if kind is not None and kind not in _CLAIM_KINDS:
            problems.append(f"{where}: 'kind' value '{kind}' is not a valid claim kind")
        status = claim.get("status")
        if status is not None and status not in _CLAIM_STATUSES:
            problems.append(f"{where}: 'status' value '{status}' is not a valid claim status")
        for field_name in _LIST_OF_STRING_FIELDS:
            value = claim.get(field_name)
            if value is not None and (
                not isinstance(value, list)
                or any(not isinstance(item, str) for item in value)
            ):
                problems.append(f"{where}: '{field_name}' must be a list of strings")
        evidence = claim.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, list):
                problems.append(f"{where}: 'evidence' must be a list")
            else:
                for e_idx, item in enumerate(evidence):
                    e_where = f"{where} evidence[{e_idx}]"
                    if not isinstance(item, dict):
                        problems.append(f"{e_where}: evidence item is not an object")
                        continue
                    e_unknown = sorted(set(item) - _EVIDENCE_FIELDS)
                    if e_unknown:
                        problems.append(
                            f"{e_where}: unknown field(s): {', '.join(e_unknown)}")
                    e_kind = item.get("kind")
                    if e_kind is not None and e_kind not in _EVIDENCE_KINDS:
                        problems.append(
                            f"{e_where}: 'kind' value '{e_kind}' is not a valid evidence kind")
                    e_ref = item.get("ref")
                    if e_ref is not None and not isinstance(e_ref, str):
                        problems.append(f"{e_where}: 'ref' must be a string")
    return problems


def _spec_sections(spec_text: str) -> dict[str, bool]:
    """Required-section presence in spec.md (heading-based, deterministic)."""
    headings: list[str] = []
    has_title = False
    for line in spec_text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if m.group(1) == "#":
                has_title = True
            headings.append(m.group(2).strip().lower())
    return {
        "title": has_title,
        "requirements": any("requirement" in h for h in headings),
        "acceptance": any(
            ("acceptance" in h) or ("success criteria" in h) for h in headings
        ),
    }


def evaluate_spec_structure(feature_dir: Path, phase: str,
                            timestamp: str | None = None) -> dict[str, Any]:
    """Evaluate one feature directory and return the evaluator result."""
    findings: list[dict[str, Any]] = []
    artifacts: list[str] = []

    spec_path = feature_dir / "spec.md"
    plan_path = feature_dir / "plan.md"
    tasks_path = feature_dir / "tasks.md"
    claims_path = feature_dir / "claims.json"
    assessment_path = feature_dir / "assessment.json"

    spec_text: str | None = None
    tasks_text: str | None = None

    # -- Presence: spec / plan / tasks ------------------------------------
    if spec_path.is_file():
        artifacts.append("spec.md")
        spec_text = spec_path.read_text(encoding="utf-8")
    else:
        _finding(findings, "critical", "schema_violation", "spec.md",
                 "Feature directory has no spec.md; there is no specification to evaluate.",
                 "revise", "spec.md")
    if plan_path.is_file():
        artifacts.append("plan.md")
    else:
        _finding(findings, "high", "schema_violation", "plan.md",
                 "Feature directory has no plan.md; the specification has no implementation plan.",
                 "revise", "plan.md")
    if tasks_path.is_file():
        artifacts.append("tasks.md")
        tasks_text = tasks_path.read_text(encoding="utf-8")
    else:
        _finding(findings, "high", "schema_violation", "tasks.md",
                 "Feature directory has no tasks.md; the plan has no task breakdown.",
                 "revise", "tasks.md")

    # -- Required sections in spec.md --------------------------------------
    if spec_text is not None:
        sections = _spec_sections(spec_text)
        for section, present in sections.items():
            if not present:
                _finding(findings, "medium", "schema_violation", "spec.md",
                         f"spec.md is missing its required '{section}' section.",
                         "revise", "spec.md")

    # -- Claims bundle: presence, strict-load validity, falsifiers ---------
    bundle: Any = None
    if claims_path.is_file():
        artifacts.append("claims.json")
        try:
            bundle = json.loads(
                claims_path.read_text(encoding="utf-8"),
                object_pairs_hook=_no_dup_object,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            _finding(findings, "high", "schema_violation", "claims.json",
                     f"claims.json does not parse / strict-load: {exc}",
                     "revise", "claims.json")
        if bundle is not None:
            for problem in _claims_validity_problems(bundle):
                _finding(findings, "high", "schema_violation", "claims.json",
                         f"claims.json fails strict-load validity: {problem}",
                         "revise", "claims.json")
            if isinstance(bundle, dict) and isinstance(bundle.get("claims"), list):
                for claim in bundle["claims"]:
                    if not isinstance(claim, dict):
                        continue
                    tests = claim.get("falsification_tests")
                    if not tests or not any(
                        isinstance(t, str) and t.strip() for t in tests
                        if isinstance(tests, list)
                    ):
                        cid = claim.get("id") if isinstance(claim.get("id"), str) else "?"
                        _finding(findings, "medium", "missing_evidence", str(cid),
                                 f"Claim '{cid}' carries no falsification test; "
                                 "an unfalsifiable claim cannot be checked.",
                                 "revise", "claims.json")
    else:
        _finding(findings, "high", "missing_evidence", "claims.json",
                 "Feature directory has no claims.json; no claims bundle was produced for this spec.",
                 "revise", "claims.json")

    # -- Assessment presence ----------------------------------------------
    if assessment_path.is_file():
        artifacts.append("assessment.json")
        try:
            parsed = json.loads(assessment_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                _finding(findings, "medium", "schema_violation", "assessment.json",
                         "assessment.json parses but is not a JSON object.",
                         "revise", "assessment.json")
        except json.JSONDecodeError as exc:
            _finding(findings, "medium", "schema_violation", "assessment.json",
                     f"assessment.json does not parse as JSON: {exc}",
                     "revise", "assessment.json")
    else:
        _finding(findings, "medium", "missing_evidence", "assessment.json",
                 "Feature directory has no assessment.json; the claims were never assessed.",
                 "iterate", "assessment.json")

    # -- Traceability: tasks <-> requirements ------------------------------
    if spec_text is not None and tasks_text is not None:
        requirement_ids = sorted(set(_REQ_ID_RE.findall(spec_text)))
        for req_id in requirement_ids:
            if req_id not in tasks_text:
                _finding(findings, "medium", "coverage_gap", req_id,
                         f"Requirement {req_id} in spec.md is not referenced by any task in tasks.md.",
                         "revise", "tasks.md")
        for line in tasks_text.splitlines():
            if _TASK_LINE_RE.match(line) and not _TASK_REF_RE.search(line):
                label = line.strip()[:80]
                _finding(findings, "low", "traceability_gap", "tasks.md",
                         f"Task line carries no requirement reference: {label}",
                         "revise", "tasks.md")

    # -- Outcome ------------------------------------------------------------
    if any(f["severity"] in ("critical", "high") for f in findings):
        outcome = "block"
    elif findings:
        outcome = "iterate"
    else:
        outcome = "pass"

    if outcome == "pass":
        summary = (
            f"Spec structure complete for '{feature_dir.name}': spec/plan/tasks present, "
            "claims bundle strict-load valid with falsifiers, assessment present, "
            "tasks traceable to requirements."
        )
        next_action = {"kind": "pass", "target_phase": None,
                       "message": "Spec structure checks passed; continue to the next phase."}
    elif outcome == "block":
        summary = (
            f"Spec structure for '{feature_dir.name}' is missing contract basics: "
            f"{len(findings)} finding(s), including blocking structural gaps. "
            "See findings for the exact files and rules."
        )
        next_action = {"kind": "block", "target_phase": None,
                       "message": "Restore the missing/invalid spec artifacts before proceeding."}
    else:
        summary = (
            f"Spec structure for '{feature_dir.name}' is present but incomplete: "
            f"{len(findings)} finding(s) to address. See findings for details."
        )
        next_action = {"kind": "iterate", "target_phase": "specify",
                       "message": "Revise the specification artifacts to close the findings."}

    return {
        "schema_version": "1.0",
        "evaluator": {
            "id": EVALUATOR_ID,
            "version": EVALUATOR_VERSION,
            "name": EVALUATOR_NAME,
            "url": EVALUATOR_URL,
        },
        "phase": phase,
        "outcome": outcome,
        "summary": summary[:500],
        "findings": findings,
        "next_action": next_action,
        "metadata": {
            "timestamp": timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_ms": 0,
            "artifacts_evaluated": artifacts,
            "model": None,
            "deterministic": True,
        },
        "state": {},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic spec-structure reference evaluator (Spec 002 FR-7)."
    )
    parser.add_argument("--feature-dir", required=True, type=Path,
                        help="Feature directory containing spec.md/plan.md/tasks.md/claims.json.")
    parser.add_argument("--phase", default="after_specify",
                        help="Lifecycle phase for the result (default: after_specify).")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write the result JSON to this file instead of stdout.")
    parser.add_argument("--timestamp", default=None,
                        help="Pin metadata.timestamp (ISO 8601) for byte-identical output.")
    args = parser.parse_args(argv)

    if args.phase not in _VALID_PHASES:
        print(f"Error: unsupported phase '{args.phase}'. "
              f"Valid phases: {', '.join(sorted(_VALID_PHASES))}", file=sys.stderr)
        return 2
    if not args.feature_dir.is_dir():
        print(f"Error: feature directory not found: {args.feature_dir}", file=sys.stderr)
        return 2

    result = evaluate_spec_structure(args.feature_dir, args.phase, args.timestamp)
    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"Evaluator result written to {args.output}")
    else:
        print(output_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
