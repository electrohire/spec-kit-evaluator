#!/usr/bin/env bash
# Compose multiple evaluator results with deterministic precedence.
#
# Usage:
#   compose-results.sh --results-dir <path> --phase <phase> [--strategy strict|majority|optimistic] [--output <path>]
#
# Composition contract (Spec 003 FR-6), at parity with the Python
# composer on outcomes and exit codes:
#   * Empty composition fails closed: outcome "block", exit 2, with an
#     explicit no-results finding — never "pass".
#   * Every input is validated against the same minimum contract the
#     Python composer enforces via the JSON Schema (required keys,
#     outcome/finding enums, evaluator id+version, payload phase equal
#     to the requested phase). Malformed or invalid files are wrapped
#     as blocking schema_violation findings that vote "block" under
#     every strategy — never skipped toward pass, never a crash.
#   * Dedup/counting use payload evaluator.id+version (greatest
#     filename wins); finding ids are namespaced "<evaluator>:<id>".
#   * Lane pairing (Spec 004 P5): a result carrying the AEE lane pair
#     in metadata.lanes is carried through verbatim per evaluator as
#     metadata.lane_states — never merged, averaged, or scored — and
#     the composed summary states lane-2 lag whenever present,
#     including on a pass. Lane-less inputs compose exactly as before.
#   * majority/optimistic results are marked non-gating in metadata.
#   * Exit codes: 0 pass/warn, 1 iterate/clarify/gather_evidence,
#     2 block or hard error.
#
# Requires `jq` for JSON processing.

set -euo pipefail

RESULTS_DIR=""
PHASE=""
STRATEGY="strict"
OUTPUT=""

usage() {
    cat <<EOF
Usage: $0 --results-dir <path> --phase <phase> [--strategy strict|majority|optimistic] [--output <path>]

Compose multiple evaluator results with deterministic precedence.

Options:
  --results-dir <path>   Directory containing evaluator result JSON files.
  --phase <phase>        Lifecycle phase to compose results for (e.g., after_plan).
  --strategy <strategy>  Composition strategy: strict (default), majority, or optimistic.
  --output <path>        Write composed result to this file instead of stdout.

Exit codes: 0 = pass/warn, 1 = iterate/clarify/gather_evidence, 2 = block/error.
EOF
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --results-dir) RESULTS_DIR="$2"; shift 2 ;;
        --phase) PHASE="$2"; shift 2 ;;
        --strategy) STRATEGY="$2"; shift 2 ;;
        --output) OUTPUT="$2"; shift 2 ;;
        *) usage ;;
    esac
done

if [[ -z "$RESULTS_DIR" || -z "$PHASE" ]]; then
    echo "Error: --results-dir and --phase are required." >&2
    usage
fi

case "$STRATEGY" in
    strict|majority|optimistic) ;;
    *) echo "Error: unknown strategy '$STRATEGY'." >&2; exit 2 ;;
esac

# Check for jq
if ! command -v jq &>/dev/null; then
    echo "Error: jq is required but not installed." >&2
    exit 2
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

emit_and_exit() {
    # $1 = composed JSON. Prints (or writes) it, then exits with the
    # gate code for its outcome.
    local composed="$1" outcome code
    outcome=$(echo "$composed" | jq -r '.outcome')
    case "$outcome" in
        pass|warn) code=0 ;;
        iterate|clarify|gather_evidence) code=1 ;;
        *) code=2 ;;
    esac
    if [[ -n "$OUTPUT" ]]; then
        mkdir -p "$(dirname "$OUTPUT")"
        echo "$composed" > "$OUTPUT"
        echo "Composed result written to $OUTPUT"
    else
        echo "$composed"
    fi
    exit "$code"
}

no_results_composed() {
    # $1 = detail message. Fail-closed empty composition (FR-6.1).
    jq -n \
        --arg phase "$PHASE" \
        --arg strategy "$STRATEGY" \
        --arg ts "$TIMESTAMP" \
        --arg detail "$1" \
        '{
            schema_version: "1.0",
            evaluator: { id: "composed", version: "1.0", name: "Composed (\($strategy))" },
            phase: $phase,
            outcome: "block",
            summary: ("No evaluator results for phase " + $phase + ": composition requires at least one valid evaluator result and fails closed — absence of evidence is not a pass. " + $detail)[0:500],
            findings: [{
                id: "composed:NO-RESULTS",
                severity: "critical",
                kind: "missing_evidence",
                subject: $phase,
                description: "No valid evaluator results were available to compose for this phase. A missing/crashed evaluator or a mistyped phase must never read downstream as a green gate.",
                evidence_refs: [],
                provenance_refs: [],
                uncertainty: "insufficient_evidence",
                recommended_action: "block",
                rationale: "Fail-closed composition (Spec 003 FR-6.1)."
            }],
            next_action: { kind: "block", target_phase: null, message: ("No evaluator results found for phase " + $phase + ".") },
            metadata: {
                timestamp: $ts,
                duration_ms: 0,
                artifacts_evaluated: [],
                deterministic: true,
                evaluator_count: 0,
                contradictory_findings: [],
                composition_strategy: $strategy,
                evaluator_results: [],
                invalid_results: [],
                duplicate_results_ignored: [],
                gating: ($strategy == "strict"),
                no_results: true
            },
            state: {}
        }'
}

if [[ ! -d "$RESULTS_DIR" ]]; then
    echo "Error: no evaluator results found for phase '$PHASE' in $RESULTS_DIR (directory missing); composing a fail-closed block result." >&2
    emit_and_exit "$(no_results_composed "Results directory not found: $RESULTS_DIR.")"
fi

# Collect result files for the phase (exclude previously composed files)
# Portable to bash 3.2+ (macOS): avoid mapfile (bash 4+)
RESULT_FILES=()
while IFS= read -r f; do
    RESULT_FILES+=("$f")
done < <(find "$RESULTS_DIR" -maxdepth 1 -name "*-${PHASE}-*.json" ! -name "composed-*" | sort)

if [[ ${#RESULT_FILES[@]} -eq 0 ]]; then
    echo "Error: no evaluator results found for phase '$PHASE' in $RESULTS_DIR; composing a fail-closed block result." >&2
    emit_and_exit "$(no_results_composed "The results directory contains no result files for this phase.")"
fi

# Per-file validation against the minimum contract. Emits one verdict
# object per line: {"file":..., "ok":bool, "problem":..., "result":...}
VALIDATE_JQ='
def in_list($list): . as $x | $list | index($x) != null;
def outcomes: ["pass", "warn", "iterate", "clarify", "gather_evidence", "block"];
def severities: ["critical", "high", "medium", "low", "info"];
def kinds: ["unsupported_claim", "contradiction", "missing_evidence",
  "ambiguous_requirement", "unverified_assertion", "provenance_gap",
  "schema_violation", "policy_violation", "security_concern",
  "coverage_gap", "traceability_gap", "risk_unaddressed",
  "assumption_unvalidated", "other"];
def finding_problem:
  [ to_entries[] | select(
      (.value | type) != "object"
      or (.value.id | type) != "string"
      or (.value.severity | in_list(severities) | not)
      or (.value.kind | in_list(kinds) | not)
      or (.value.subject | type) != "string")
    | "finding at index \(.key) violates the minimum contract (id/severity/kind/subject)" ]
  | .[0] // null;
def problems($phase):
  [ if type != "object" then "result is not a JSON object" else empty end,
    if type == "object" then
      ( if (.schema_version | type) != "string" then "missing or invalid schema_version" else empty end,
        if (.evaluator | type) != "object" then "missing or invalid evaluator object"
        elif (.evaluator.id | type) != "string" or (.evaluator.id | length) == 0 then "evaluator.id missing or empty"
        elif (.evaluator.version | type) != "string" or (.evaluator.version | length) == 0 then "evaluator.version missing or empty"
        else empty end,
        if (.phase | type) != "string" then "missing or invalid phase"
        elif .phase != $phase then "phase mismatch: payload phase \(.phase) != requested phase \($phase)"
        else empty end,
        if (.outcome | in_list(outcomes) | not) then "invalid outcome \(.outcome // "<missing>")" else empty end,
        if (.findings | type) != "array" then "findings is not an array"
        elif (.findings | finding_problem) != null then (.findings | finding_problem)
        else empty end )
    else empty end
  ] | .[0] // null;
{
  file: $file,
  problem: problems($phase),
  result: .
}
| if .problem == null then { file: .file, ok: true, problem: null, result: .result }
  else { file: .file, ok: false, problem: .problem, result: null } end
'

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT
VERDICTS="$WORKDIR/verdicts.jsonl"
: > "$VERDICTS"

for f in "${RESULT_FILES[@]}"; do
    fname=$(basename "$f")
    if verdict=$(jq -c --arg phase "$PHASE" --arg file "$fname" "$VALIDATE_JQ" "$f" 2>/dev/null); then
        echo "$verdict" >> "$VERDICTS"
    else
        jq -n --arg file "$fname" \
            '{ file: $file, ok: false, problem: "malformed JSON", result: null }' \
            >> "$VERDICTS"
    fi
done

# Final composition over the verdict array.
COMPOSE_JQ='
def in_list($list): . as $x | $list | index($x) != null;
def severity_order($s):
    if $s == "critical" then 0
    elif $s == "high" then 1
    elif $s == "medium" then 2
    elif $s == "low" then 3
    else 4 end;
def precedence: ["block", "gather_evidence", "iterate", "clarify", "warn", "pass"];
def resolve_outcome(outcomes; strategy):
    if strategy == "optimistic" then
        (precedence | reverse | map(select(in_list(outcomes))) | .[0] // "pass")
    elif strategy == "majority" then
        (outcomes | group_by(.) | map({ outcome: .[0], count: length,
            sev: (.[0] as $o | precedence | index($o)) })
          | sort_by([-.count, .sev]) | .[0].outcome // "pass")
    else
        (precedence | map(select(in_list(outcomes))) | .[0] // "pass")
    end;
def lane_states_of($results):
    # Spec 004 P5-V1: carry each lanes-carrying evaluator pair
    # through verbatim — never merged, averaged, or reduced.
    [ $results[]
      | select((.metadata | type) == "object")
      | select((.metadata.lanes | type) == "object")
      | {
          evaluator_id: .evaluator.id,
          lane_1: .metadata.lanes.lane_1,
          lane_2: .metadata.lanes.lane_2,
          not_understood: (.metadata.not_understood // [])
        } ];
def lane_lag_summary($states):
    # Spec 004 P5-V2: one headline sentence naming lane-2 lag, or ""
    # when no carried lane state lags. Signals are read from the
    # carried records (lane_2.bundle, falling back to lane_2 itself);
    # counts are reported as the records state them — nothing is
    # scored or combined, and lane 2 contains no score to invent.
    [ $states[]
      | . as $state
      | (if (.lane_2 | type) == "object"
         then (if (.lane_2.bundle | type) == "object" then .lane_2.bundle else .lane_2 end)
         else {} end) as $bundle
      | [ if (($bundle.below_explained | type) == "number" and $bundle.below_explained != 0)
          then "\($bundle.below_explained) claim(s) below the explained stage" else empty end,
          if (($bundle.verified_unexplained | type) == "number" and $bundle.verified_unexplained != 0)
          then "\($bundle.verified_unexplained) verified-but-unexplained claim(s)" else empty end,
          if ((.not_understood // []) | length) > 0
          then "\((.not_understood // []) | length) residual unknown(s) not understood" else empty end
        ] as $signals
      | select(($signals | length) > 0)
      | "\($state.evaluator_id): \($signals | join(", "))"
    ] as $parts
    | if ($parts | length) == 0 then ""
      else "Lane 2 (human acceptance) lags lane 1 (machine verification) — "
           + ($parts | join("; "))
           + ". A composed outcome is a checking-stage decision, not acceptance or digestion."
      end;

. as $verdicts
| ([$verdicts[] | select(.ok)]) as $valid_raw
| ([$verdicts[] | select(.ok | not)]) as $invalid
# dedup by payload identity (evaluator.id + version); greatest filename wins
| ($valid_raw | group_by([.result.evaluator.id, .result.evaluator.version])
   | map(max_by(.file))) as $selected
| ([$valid_raw[].file] - [$selected[].file]) as $duplicates
| ([$selected[].result]) as $results
| (lane_states_of($results)) as $lane_states
| (lane_lag_summary($lane_states)) as $lane_lag
| ([$results[].outcome] + ($invalid | map("block"))) as $outcomes
| resolve_outcome($outcomes; $STRATEGY) as $composed_outcome
| ([$selected[] | .result as $r | $r.findings[] | .id = "\($r.evaluator.id):\(.id)"]) as $valid_findings
| ([$invalid[] | {
    id: "invalid:\(.file)",
    severity: "critical",
    kind: "schema_violation",
    subject: .file,
    description: ("Invalid evaluator result " + .file + " was not composed: " + .problem + ". The invalid result is wrapped as a blocking finding; composition fails closed rather than skipping it toward pass.")[0:500],
    evidence_refs: [{ ref: .file, kind: "observed", description: .problem }],
    provenance_refs: [.file],
    uncertainty: "none",
    recommended_action: "block",
    rationale: "An evaluator result that cannot be validated cannot certify anything; it blocks composition (Spec 003 FR-6.2)."
  }]) as $invalid_findings
| (($valid_findings + $invalid_findings) | sort_by([severity_order(.severity), .id])) as $all_findings
| ([$results[] | select(.outcome == "iterate") | .next_action.target_phase // empty]
   | group_by(.) | map({ phase: .[0], count: length })
   | sort_by([-.count, .phase]) | .[0].phase // null) as $iterate_target
| {
    schema_version: "1.0",
    evaluator: { id: "composed", version: "1.0", name: "Composed (\($STRATEGY))" },
    phase: $PHASE,
    outcome: $composed_outcome,
    summary: (
      "\($results | length) evaluator(s) ran. Outcomes: \(
        ([$results[] | "\(.evaluator.id)=\(.outcome)"]
         + [$invalid[] | "invalid:\(.file)=block"]) | join(", ")). \($all_findings | length) finding(s) total."
      + (if ($invalid | length) > 0 then " \($invalid | length) invalid result file(s) were wrapped as blocking findings." else "" end)
      + (if $STRATEGY != "strict" then " Strategy \($STRATEGY) is non-gating (advisory)." else "" end)
      + (if $lane_lag != "" then " \($lane_lag)" else "" end)
    )[0:500],
    findings: $all_findings,
    next_action: {
        kind: $composed_outcome,
        target_phase: (if $composed_outcome == "iterate" then $iterate_target else null end),
        message: "Composed outcome: \($composed_outcome)."
    },
    metadata: ({
        timestamp: $TIMESTAMP,
        duration_ms: 0,
        artifacts_evaluated: [],
        deterministic: true,
        evaluator_count: $results | length,
        contradictory_findings: ([$all_findings | group_by(.subject) | .[] | select(length > 1) | {
            subject: .[0].subject,
            finding_ids: [.[].id],
            description: "Conflicting findings on subject \(.[0].subject)"
        }]),
        composition_strategy: $STRATEGY,
        evaluator_results: ([$results[] | { evaluator_id: .evaluator.id, outcome: .outcome, findings_count: (.findings | length) }]
            + [$invalid[] | { evaluator_id: "invalid:\(.file)", outcome: "block", findings_count: 1, invalid: true, file: .file, reason: .problem }]),
        invalid_results: [$invalid[] | { file: .file, reason: .problem }],
        duplicate_results_ignored: $duplicates,
        gating: ($STRATEGY == "strict")
    }
    + (if ($lane_states | length) > 0 then { lane_states: $lane_states } else {} end)
    + (if $STRATEGY != "strict" then { non_gating_reason: "Strategy \($STRATEGY) composes advisory outcomes; the result is marked non-gating and must not be used as a release gate (Spec 003 FR-6.6)." } else {} end)
    + (if (($outcomes | index("block")) != null and $composed_outcome != "block") then { block_overridden: true } else {} end)),
    state: ($selected | map({ key: .result.evaluator.id, value: (.result.state // {}) }) | from_entries)
}'

COMPOSED=$(jq -s "$COMPOSE_JQ" \
    --arg PHASE "$PHASE" \
    --arg STRATEGY "$STRATEGY" \
    --arg TIMESTAMP "$TIMESTAMP" \
    "$VERDICTS")

# Report invalid inputs by name on stderr (parity with Python composer).
while IFS= read -r line; do
    echo "Error: invalid evaluator result '$(echo "$line" | jq -r .file)': $(echo "$line" | jq -r .reason)" >&2
done < <(echo "$COMPOSED" | jq -c '.metadata.invalid_results[]')

emit_and_exit "$COMPOSED"
