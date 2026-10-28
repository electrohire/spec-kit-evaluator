"""Verified-write retrofit tests (fleet standard, 2026-10-28).

Unit level: the vendored writer lands exact bytes, recovers through
the fresh-subprocess attempt when in-process writes keep failing,
refuses empty content, and raises when every attempt fails.
End to end: both scripts' --output paths produce files whose bytes
parse back to the emitted result.

Run:  python3 -m unittest tests.test_verified_write_output -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts" / "python"
COMPOSE = SCRIPTS / "compose_results.py"
EVALUATOR = SCRIPTS / "spec_structure_evaluator.py"

sys.path.insert(0, str(SCRIPTS))
import verified_write  # noqa: E402
from verified_write import SafeWriteError, write_text_verified  # noqa: E402


class VerifiedWriteUnitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_round_trip_exact_bytes(self):
        target = self.dir / "result.json"
        result = write_text_verified(target, '{"outcome": "pass"}\n')
        self.assertEqual(target.read_bytes(), b'{"outcome": "pass"}\n')
        self.assertEqual(result["bytes"], 20)

    def test_empty_content_refused(self):
        with self.assertRaises(ValueError):
            write_text_verified(self.dir / "empty.json", "")

    def test_recovers_via_child_when_local_attempts_fail(self):
        target = self.dir / "result.json"
        with mock.patch.object(verified_write, "try_write_once", return_value=False):
            # The mock also neutralizes the child's in-file call only
            # in THIS process; the child is a fresh interpreter whose
            # try_write_once is the real one, keyed off argv mode.
            real_child = verified_write._try_child
            result = verified_write.write_file_verified(target, b"payload\n")
        self.assertTrue(result["via"].startswith("child-"))
        self.assertEqual(target.read_bytes(), b"payload\n")
        self.assertIsNotNone(real_child)

    def test_total_failure_raises_and_writes_nothing(self):
        target = self.dir / "result.json"
        with (
            mock.patch.object(verified_write, "try_write_once", return_value=False),
            mock.patch.object(verified_write, "_try_child", return_value=False),
        ):
            with self.assertRaises(SafeWriteError):
                verified_write.write_file_verified(target, b"payload\n")
        self.assertFalse(target.exists())


class OutputPathEndToEndTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_compose_output_file_written_and_parseable(self):
        results_dir = self.dir / "results"
        results_dir.mkdir()
        payload = {
            "schema_version": "1.0",
            "evaluator": {"id": "spec-structure", "version": "1.0.0"},
            "phase": "after_specify",
            "outcome": "pass",
            "summary": "spec-structure summary.",
            "findings": [],
        }
        name = "spec-structure-after_specify-20261028T000000Z.json"
        (results_dir / name).write_text(json.dumps(payload), encoding="utf-8")
        output = self.dir / "composed.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(COMPOSE),
                "--results-dir",
                str(results_dir),
                "--phase",
                "after_specify",
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("written to", proc.stdout)
        composed = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(composed["outcome"], "pass")

    def test_evaluator_output_file_written_and_parseable(self):
        feature = self.dir / "001-feature"
        feature.mkdir()
        (feature / "spec.md").write_text(
            "# Feature Specification: Demo\n\n**Feature Branch**: `001`\n",
            encoding="utf-8",
        )
        output = self.dir / "eval.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(EVALUATOR),
                "--feature-dir",
                str(feature),
                "--phase",
                "after_specify",
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Exit code is the evaluator's gate outcome; the contract
        # under test is that the output file was durably written.
        self.assertIn("written to", proc.stdout + proc.stderr)
        self.assertTrue(output.exists())
        parsed = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("outcome", parsed)


if __name__ == "__main__":
    unittest.main()
