"""Cross-implementation parity harness for composition (Spec 003 FR-6.4/T605).

Runs the shared fixture corpus (tests/fixtures/compose/<case>/results)
through every composer implementation available in the environment —
Python, Bash (needs bash + jq), PowerShell (needs pwsh) — and asserts
they agree on the composed outcome AND the exit code for every case,
and that each matches the expected contract values.

Lane pairing (Spec 004 P5) is asserted the same way: for the lane
fixture cases, every composer's composed result must carry
`metadata.lane_states` deep-equal to the expected per-evaluator lane
pairs (fields AND values, not just outcome/exit), and the composed
summary must state lane-2 lag exactly where the contract requires it
— including on a pass — and nowhere else. A composer that drops,
re-blends, or scores the lanes fails these tests even when its
outcome and exit code agree.

PowerShell: where `pwsh` is absent the ps1 leg is SKIPPED CLEANLY
(the skip is reported by unittest; the ps1 composer is exercised in CI,
whose runners ship pwsh — including the lane assertions below). The
harness never fabricates a ps1 result.

The 'appeal-majority-override' case is the contract's only
block-override path: a `block` voted down under `majority`. Under the
old composers it silently became a gating `pass`; the contract now
requires outcome pass + exit 0 from an advisory, non-gating
composition whose metadata keeps the block visible (FR-6.6).

Run:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PY_COMPOSE = REPO_ROOT / "scripts" / "python" / "compose_results.py"
SH_COMPOSE = REPO_ROOT / "scripts" / "bash" / "compose-results.sh"
PS_COMPOSE = REPO_ROOT / "scripts" / "powershell" / "compose-results.ps1"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "compose"
PHASE = "after_specify"

# (case, strategy, expected outcome, expected exit code)
CASES = [
    ("empty", "strict", "block", 2),
    ("valid-pass", "strict", "pass", 0),
    ("valid-fail", "strict", "block", 2),
    ("malformed", "strict", "block", 2),
    ("invalid-schema", "strict", "block", 2),
    ("phase-mismatch", "strict", "block", 2),
    ("appeal-majority-override", "majority", "pass", 0),
    ("appeal-majority-override", "strict", "block", 2),
    ("dedup-majority", "majority", "block", 2),
]

# Lane-pairing cases (Spec 004 P5). All compose under `strict` to
# outcome pass / exit 0. Expected lane_states are the exact values the
# composed metadata must carry (compared deep-equal after sorting by
# evaluator_id, so entry order is not the assertion — the pairs are).
_LANE_1 = {"label": "machine verification",
           "bundle": {"outcome": "pass", "at_or_above_threshold": 2}}
_LANE_2_LAGGING = {
    "label": "human acceptance",
    "bundle": {
        "stage_counts": {"created": 0, "checked": 2, "explained": 0,
                         "accepted": 0, "digested": 0},
        "below_explained": 2,
        "verified_unexplained": 1,
    },
}
# (case, expected lane_states or None, summary must contain,
#  summary must NOT contain)
LANE_CASES = [
    ("lanes-lagging",
     [{"evaluator_id": "aee", "lane_1": _LANE_1, "lane_2": _LANE_2_LAGGING,
       "not_understood": ["CAP: no human has explained the mechanism"]}],
     ["Lane 2 (human acceptance) lags lane 1 (machine verification)",
      "aee: 2 claim(s) below the explained stage, "
      "1 verified-but-unexplained claim(s), "
      "1 residual unknown(s) not understood",
      "not acceptance or digestion"],
     []),
    ("lanes-clean",
     [{"evaluator_id": "aee", "lane_1": _LANE_1,
       "lane_2": {"label": "human acceptance",
                  "bundle": {
                      "stage_counts": {"created": 0, "checked": 2,
                                       "explained": 2, "accepted": 2,
                                       "digested": 2},
                      "below_explained": 0, "verified_unexplained": 0}},
       "not_understood": []}],
     [],
     ["Lane 2", "lags"]),
    ("lanes-flat",
     [{"evaluator_id": "aee",
       "lane_1": {"label": "machine verification",
                  "bundle": {"outcome": "pass"}},
       "lane_2": {"label": "human acceptance", "below_explained": 1,
                  "verified_unexplained": 0},
       "not_understood": []}],
     ["aee: 1 claim(s) below the explained stage"],
     []),
    ("lanes-mixed",
     [{"evaluator_id": "aee", "lane_1": _LANE_1, "lane_2": _LANE_2_LAGGING,
       "not_understood": []}],
     ["aee: 2 claim(s) below the explained stage, "
      "1 verified-but-unexplained claim(s)"],
     ["spec-structure:"]),
    ("valid-pass", None, [], ["Lane 2"]),
]


def _canon_lane_states(composed: dict):
    """metadata.lane_states as a canonical, order-insensitive value:
    the list sorted by evaluator_id, or None when the key is absent."""
    metadata = composed.get("metadata") or {}
    if "lane_states" not in metadata:
        return None
    return sorted(metadata["lane_states"],
                  key=lambda s: s.get("evaluator_id", ""))


def _lag_sentence(summary: str) -> str:
    """The lane-lag sentence of a composed summary, or "" — the exact
    text from 'Lane 2' to the end of the summary."""
    start = summary.find("Lane 2")
    return summary[start:] if start >= 0 else ""


def _parse_stdout_json(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stdout[start:end + 1])
        raise


def _run_python_composed(results_dir: Path, strategy: str) -> tuple[dict, int]:
    proc = subprocess.run(
        [sys.executable, str(PY_COMPOSE), "--results-dir", str(results_dir),
         "--phase", PHASE, "--strategy", strategy, "--json"],
        capture_output=True, text=True, timeout=60)
    return _parse_stdout_json(proc.stdout), proc.returncode


def _run_bash_composed(results_dir: Path, strategy: str) -> tuple[dict, int]:
    proc = subprocess.run(
        ["bash", str(SH_COMPOSE), "--results-dir", str(results_dir),
         "--phase", PHASE, "--strategy", strategy],
        capture_output=True, text=True, timeout=60)
    return _parse_stdout_json(proc.stdout), proc.returncode


def _run_powershell_composed(results_dir: Path, strategy: str) -> tuple[dict, int]:
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(PS_COMPOSE),
         "-ResultsDir", str(results_dir), "-Phase", PHASE,
         "-Strategy", strategy],
        capture_output=True, text=True, timeout=120)
    return _parse_stdout_json(proc.stdout), proc.returncode


def _run_python(results_dir: Path, strategy: str) -> tuple[str, int]:
    composed, rc = _run_python_composed(results_dir, strategy)
    return composed["outcome"], rc


def _run_bash(results_dir: Path, strategy: str) -> tuple[str, int]:
    composed, rc = _run_bash_composed(results_dir, strategy)
    return composed["outcome"], rc


def _run_powershell(results_dir: Path, strategy: str) -> tuple[str, int]:
    composed, rc = _run_powershell_composed(results_dir, strategy)
    return composed["outcome"], rc


class ParityTests(unittest.TestCase):
    def test_python_parity(self):
        for case, strategy, outcome, rc in CASES:
            with self.subTest(impl="python", case=case, strategy=strategy):
                got = _run_python(FIXTURES / case / "results", strategy)
                self.assertEqual(got, (outcome, rc))

    # On Windows, `bash` resolves to the WSL launcher stub, which is not
    # a usable POSIX bash for this composer; the bash leg is exercised on
    # POSIX hosts (and in the dedicated Test Bash CI jobs).
    @unittest.skipUnless(
        os.name != "nt" and shutil.which("bash") and shutil.which("jq"),
        "POSIX bash + jq required for the bash composer")
    def test_bash_parity(self):
        for case, strategy, outcome, rc in CASES:
            with self.subTest(impl="bash", case=case, strategy=strategy):
                got = _run_bash(FIXTURES / case / "results", strategy)
                self.assertEqual(got, (outcome, rc))

    @unittest.skipUnless(
        shutil.which("pwsh"),
        "pwsh not available: PowerShell composer parity leg skipped "
        "(exercised in CI, where runners ship pwsh)")
    def test_powershell_parity(self):
        for case, strategy, outcome, rc in CASES:
            with self.subTest(impl="powershell", case=case, strategy=strategy):
                got = _run_powershell(FIXTURES / case / "results", strategy)
                self.assertEqual(got, (outcome, rc))

    def test_python_and_bash_agree_with_each_other(self):
        if os.name == "nt" or not (shutil.which("bash") and shutil.which("jq")):
            self.skipTest("POSIX bash + jq required")
        for case, strategy, _, _ in CASES:
            with self.subTest(case=case, strategy=strategy):
                directory = FIXTURES / case / "results"
                self.assertEqual(
                    _run_python(directory, strategy),
                    _run_bash(directory, strategy),
                )

    # -- Lane pairing (Spec 004 P5): asserted per composer on fields
    #    AND values — lane_states deep-equal to the expected pairs,
    #    lag stated in the summary exactly where the contract
    #    requires it. Outcome/exit agreement alone cannot catch a
    #    composer that drops or re-blends the lanes.

    def _assert_lane_case(self, run_composed, case, expected_states,
                          must_contain, must_not_contain):
        composed, rc = run_composed(FIXTURES / case / "results", "strict")
        self.assertEqual((composed["outcome"], rc), ("pass", 0))
        expected = None
        if expected_states is not None:
            expected = sorted(expected_states,
                              key=lambda s: s.get("evaluator_id", ""))
        self.assertEqual(_canon_lane_states(composed), expected)
        for fragment in must_contain:
            self.assertIn(fragment, composed["summary"])
        for fragment in must_not_contain:
            self.assertNotIn(fragment, composed["summary"])

    def test_python_lane_parity(self):
        for case, states, contain, not_contain in LANE_CASES:
            with self.subTest(impl="python", case=case):
                self._assert_lane_case(
                    _run_python_composed, case, states, contain, not_contain)

    @unittest.skipUnless(
        os.name != "nt" and shutil.which("bash") and shutil.which("jq"),
        "POSIX bash + jq required for the bash composer")
    def test_bash_lane_parity(self):
        for case, states, contain, not_contain in LANE_CASES:
            with self.subTest(impl="bash", case=case):
                self._assert_lane_case(
                    _run_bash_composed, case, states, contain, not_contain)

    @unittest.skipUnless(
        shutil.which("pwsh"),
        "pwsh not available: PowerShell lane parity leg skipped "
        "(exercised in CI, where runners ship pwsh)")
    def test_powershell_lane_parity(self):
        for case, states, contain, not_contain in LANE_CASES:
            with self.subTest(impl="powershell", case=case):
                self._assert_lane_case(
                    _run_powershell_composed, case, states, contain,
                    not_contain)

    def test_python_and_bash_lane_agreement(self):
        if os.name == "nt" or not (shutil.which("bash") and shutil.which("jq")):
            self.skipTest("POSIX bash + jq required")
        for case, _, _, _ in LANE_CASES:
            with self.subTest(case=case):
                directory = FIXTURES / case / "results"
                py_composed, py_rc = _run_python_composed(directory, "strict")
                sh_composed, sh_rc = _run_bash_composed(directory, "strict")
                self.assertEqual(py_rc, sh_rc)
                self.assertEqual(
                    _canon_lane_states(py_composed),
                    _canon_lane_states(sh_composed),
                )
                self.assertEqual(
                    _lag_sentence(py_composed["summary"]),
                    _lag_sentence(sh_composed["summary"]),
                )


if __name__ == "__main__":
    unittest.main()
