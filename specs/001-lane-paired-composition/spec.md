# Feature Specification: Lane-Paired Composition (Spec 004 P5, evaluator half)

**Feature Branch**: `impl/004-p5-lane-paired-composition`

**Created**: 2026-10-12

**Status**: Implemented on this branch (2026-10-12). Claims:
EVAL-P5-01 0.62 → 0.775, EVAL-P5-02 0.62 → 0.75, EVAL-P5-03
0.695 → 0.75, EVAL-P5-04 0.256 → 0.675 (below threshold — it
rests on the regression test plus the unchanged FR-6 suite,
recorded as-is); outcome `gather_evidence` → `iterate`. Suite:
31 passed + 1 skipped at baseline → 35 passed + 1 skipped (4 new
lane tests). Not merged — the coordinator merges.

**Input**: Spec 004 (Tao realignment) Phase P5, evaluator half:
"the composition contract checked against lane-paired outcomes —
a composed result must not re-blend the lanes into a single
headline; any contract change is specced in that repo." The
engine side of the contract landed on the engine repo's P5
branch: an AEE Evaluator Contract result now carries
`metadata.lanes` (the lane-1 / lane-2 bundle pair),
`metadata.not_understood`, and `metadata.reported_statuses`.

## Requirements

- **P5-V1 Lane carry-through.** When an input result carries
  `metadata.lanes`, the composed result's metadata carries a
  `lane_states` list — one entry per such evaluator, naming the
  evaluator and its lane pair verbatim (plus its
  `not_understood` entries). Lane states are never merged,
  averaged, or reduced to a single figure: lane 2 contains no
  score, and composition must not invent one.
- **P5-V2 Lag is stated, including on green.** The composed
  summary names lane-2 lag whenever any carried lane state shows
  it (claims below the explained stage, verified-but-unexplained
  claims, or residual `not_understood` entries) — in particular
  when the composed outcome is `pass`, so a lane-1-green headline
  never reads as settled, accepted, or digested work.
- **P5-V3 No re-blending, pinned.** Outcome resolution remains
  the existing strategy precedence over outcome strings; no code
  path computes a combined lane score or a blended headline
  number. A test walks a composed result built from
  lanes-carrying inputs and asserts no lane-2-derived numeric
  score exists anywhere in it.
- **P5-V4 Absence stays honest.** Results without lane data
  compose exactly as before (no `lane_states` key, no fabricated
  lane sentence).

## Non-goals

- No change to outcome strategies, the fail-closed rules, or the
  result schema's required shape (`lane_states` is additive
  metadata).
- No engine or extension changes here.
