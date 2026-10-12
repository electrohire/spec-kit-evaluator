"""Cross-implementation parity harness for composition (Spec 003 FR-6.4/T605).

Runs the shared fixture corpus (tests/fixtures/compose/<case>/results)
through every composer implementation available in the environment —
Python, Bash (needs bash + jq), PowerShell (needs pwsh) — and asserts
they agree on the composed outcome AND the exit code for every case,
and that each matches the expected contract values.

PowerShell: where `pwsh` is absent the ps1 leg is SKIPPED CLEANLY
(the skip is reported by unittest; the ps1 composer is exercised in CI,
whose runners ship pwsh). The harness never fabricates a ps1 result.

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


def _parse_stdout_json(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stdout[start:end + 1])
        raise


def _run_python(results_dir: Path, strategy: str) -> tuple[str, int]:
    proc = subprocess.run(
        [sys.executable, str(PY_COMPOSE), "--results-dir", str(results_dir),
         "--phase", PHASE, "--strategy", strategy, "--json"],
        capture_output=True, text=True, timeout=60)
    return _parse_stdout_json(proc.stdout)["outcome"], proc.returncode


def _run_bash(results_dir: Path, strategy: str) -> tuple[str, int]:
    proc = subprocess.run(
        ["bash", str(SH_COMPOSE), "--results-dir", str(results_dir),
         "--phase", PHASE, "--strategy", strategy],
        capture_output=True, text=True, timeout=60)
    return _parse_stdout_json(proc.stdout)["outcome"], proc.returncode


def _run_powershell(results_dir: Path, strategy: str) -> tuple[str, int]:
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(PS_COMPOSE),
         "-ResultsDir", str(results_dir), "-Phase", PHASE,
         "-Strategy", strategy],
        capture_output=True, text=True, timeout=120)
    return _parse_stdout_json(proc.stdout)["outcome"], proc.returncode


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


if __name__ == "__main__":
    unittest.main()
