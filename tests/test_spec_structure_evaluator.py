"""Tests for the spec-structure reference evaluator (Spec 002 FR-7).

Covers T701 (evaluator behaviour), T702 (evaluators.yml registration),
T703/T704 (the README walkthrough in a clean checkout: discovery -> run
-> compose, with schema validation of the emitted result).

Run:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "python" / "spec_structure_evaluator.py"
COMPOSE = REPO_ROOT / "scripts" / "python" / "compose_results.py"
SCHEMA = REPO_ROOT / "schemas" / "evaluator-result.schema.json"
REGISTRY = REPO_ROOT / "evaluators.yml"
FIXTURES = REPO_ROOT / "examples" / "fixtures" / "spec-structure"
PINNED_TS = "2026-01-01T00:00:00Z"

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _load_evaluator_module():
    spec = importlib.util.spec_from_file_location("spec_structure_evaluator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=60,
    )


class EvaluatorBehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_evaluator_module()

    def test_passing_fixture_passes_with_no_findings(self):
        result = self.mod.evaluate_spec_structure(
            FIXTURES / "passing", "after_specify", PINNED_TS)
        self.assertEqual(result["outcome"], "pass")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["evaluator"]["id"], "spec-structure")
        self.assertEqual(result["next_action"]["kind"], "pass")

    @unittest.skipUnless(jsonschema, "jsonschema not installed")
    def test_passing_result_is_schema_valid(self):
        result = self.mod.evaluate_spec_structure(
            FIXTURES / "passing", "after_specify", PINNED_TS)
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(instance=result, schema=schema)

    @unittest.skipUnless(jsonschema, "jsonschema not installed")
    def test_failing_result_is_schema_valid(self):
        result = self.mod.evaluate_spec_structure(
            FIXTURES / "failing", "after_specify", PINNED_TS)
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(instance=result, schema=schema)

    def test_failing_fixture_blocks_and_names_each_defect(self):
        result = self.mod.evaluate_spec_structure(
            FIXTURES / "failing", "after_specify", PINNED_TS)
        self.assertEqual(result["outcome"], "block")
        by_kind_subject = {(f["kind"], f["subject"]) for f in result["findings"]}
        # plan.md missing
        self.assertIn(("schema_violation", "plan.md"), by_kind_subject)
        # claims.json strict-load invalid (unknown field / missing text)
        self.assertIn(("schema_violation", "claims.json"), by_kind_subject)
        # claim without a falsification test
        self.assertIn(("missing_evidence", "FIX-F-02"), by_kind_subject)
        # assessment.json missing
        self.assertIn(("missing_evidence", "assessment.json"), by_kind_subject)
        # uncovered requirements FR-002 / FR-003
        self.assertIn(("coverage_gap", "FR-002"), by_kind_subject)
        self.assertIn(("coverage_gap", "FR-003"), by_kind_subject)
        # untraceable task line
        self.assertIn(("traceability_gap", "tasks.md"), by_kind_subject)
        # missing success-criteria section
        self.assertTrue(any(
            f["kind"] == "schema_violation" and f["subject"] == "spec.md"
            for f in result["findings"]))

    def test_deterministic_byte_identical_with_pinned_timestamp(self):
        a = self.mod.evaluate_spec_structure(
            FIXTURES / "failing", "after_specify", PINNED_TS)
        b = self.mod.evaluate_spec_structure(
            FIXTURES / "failing", "after_specify", PINNED_TS)
        self.assertEqual(
            json.dumps(a, indent=2, sort_keys=True),
            json.dumps(b, indent=2, sort_keys=True),
        )

    def test_deterministic_modulo_timestamp(self):
        a = self.mod.evaluate_spec_structure(FIXTURES / "passing", "after_plan")
        b = self.mod.evaluate_spec_structure(FIXTURES / "passing", "after_plan")
        a["metadata"].pop("timestamp")
        b["metadata"].pop("timestamp")
        self.assertEqual(a, b)

    def test_cli_missing_feature_dir_is_named_error_exit_2(self):
        proc = _run_cli(["--feature-dir", "/nonexistent/feature-dir"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("feature directory not found", proc.stderr)

    def test_cli_bad_phase_is_named_error_exit_2(self):
        proc = _run_cli(["--feature-dir", str(FIXTURES / "passing"),
                         "--phase", "whenever"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unsupported phase", proc.stderr)


class RegistrationTests(unittest.TestCase):
    def test_registry_exists_and_registers_spec_structure(self):
        self.assertTrue(REGISTRY.is_file(), "evaluators.yml missing (T702)")
        text = REGISTRY.read_text(encoding="utf-8")
        self.assertIn("spec-structure", text)
        if yaml is not None:
            data = yaml.safe_load(text)
            entries = data["evaluators"]
            match = [e for e in entries if e["id"] == "spec-structure"]
            self.assertEqual(len(match), 1)
            entry = match[0]
            self.assertEqual(entry["type"], "deterministic")
            self.assertTrue((REPO_ROOT / entry["script"]).is_file(),
                            "registered script path does not exist")


class WalkthroughTests(unittest.TestCase):
    """T703/T704: discovery -> run -> compose, no hand registration."""

    def _discover(self) -> dict:
        if yaml is not None:
            data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
            return data["evaluators"][0]
        return {"id": "spec-structure",
                "script": "scripts/python/spec_structure_evaluator.py"}

    def _run_and_compose(self, fixture: str, phase: str,
                         expected_compose_rc: int = 0) -> tuple[dict, dict]:
        entry = self._discover()
        script = REPO_ROOT / entry["script"]
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "results"
            results_dir.mkdir()
            out = results_dir / f"{entry['id']}-{phase}-20260101T000000Z.json"
            proc = subprocess.run(
                [sys.executable, str(script),
                 "--feature-dir", str(FIXTURES / fixture),
                 "--phase", phase,
                 "--timestamp", PINNED_TS,
                 "--output", str(out)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            emitted = json.loads(out.read_text(encoding="utf-8"))
            if jsonschema is not None:
                schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
                jsonschema.validate(instance=emitted, schema=schema)
            comp = subprocess.run(
                [sys.executable, str(COMPOSE),
                 "--results-dir", str(results_dir),
                 "--phase", phase, "--strategy", "strict", "--json"],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(comp.returncode, expected_compose_rc, comp.stderr)
            composed = json.loads(comp.stdout)
            return emitted, composed

    def test_walkthrough_passing_fixture(self):
        emitted, composed = self._run_and_compose("passing", "after_specify")
        self.assertEqual(emitted["outcome"], "pass")
        self.assertEqual(composed["outcome"], "pass")
        self.assertEqual(composed["metadata"]["evaluator_count"], 1)

    def test_walkthrough_failing_fixture(self):
        # FR-6 gate contract: a block composition exits 2, not 0.
        emitted, composed = self._run_and_compose(
            "failing", "after_specify", expected_compose_rc=2)
        self.assertEqual(emitted["outcome"], "block")
        self.assertEqual(composed["outcome"], "block")
        self.assertGreater(len(composed["findings"]), 0)


if __name__ == "__main__":
    unittest.main()
