"""Unit tests for the Python composer contract (Spec 003 FR-6).

Covers T601 (fail-closed empty), T602 (schema always applied,
jsonschema a hard dependency), T603 (invalid inputs wrapped as block
findings, malformed JSON is a named error, no tracebacks), T604
(composed output schema-valid on the engine-shaped fixture), T605
(parity lives in test_compose_parity.py), T606 (phase match, payload
identity dedup, namespaced finding ids), T607 (non-gating marks, gate
exit codes), T608 (demo runs end-to-end).

Run:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE = REPO_ROOT / "scripts" / "python" / "compose_results.py"
DEMO = REPO_ROOT / "examples" / "demo.py"
SCHEMA = REPO_ROOT / "schemas" / "evaluator-result.schema.json"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "compose"
PHASE = "after_specify"

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


def _result(eid: str, outcome: str, findings=None, **extra) -> dict:
    data = {
        "schema_version": "1.0",
        "evaluator": {"id": eid, "version": "1.0.0"},
        "phase": PHASE,
        "outcome": outcome,
        "summary": f"{eid} summary.",
        "findings": findings or [],
    }
    data.update(extra)
    return data


def _write(directory: Path, name: str, payload) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (directory / name).write_text(text, encoding="utf-8")


def _compose(directory: Path, phase: str = PHASE, strategy: str = "strict",
             env: dict | None = None):
    proc = subprocess.run(
        [sys.executable, str(COMPOSE), "--results-dir", str(directory),
         "--phase", phase, "--strategy", strategy, "--json"],
        capture_output=True, text=True, timeout=60, env=env,
    )
    parsed = None
    if proc.stdout.strip():
        parsed = json.loads(proc.stdout)
    return proc.returncode, parsed, proc.stderr


class _TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class FailClosedTests(_TempDirCase):
    def test_empty_dir_blocks_with_explicit_no_results_error(self):
        rc, composed, stderr = _compose(self.dir)
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")
        self.assertIn("no evaluator results", stderr.lower())
        self.assertTrue(composed["metadata"]["no_results"])
        self.assertEqual(composed["findings"][0]["id"], "composed:NO-RESULTS")

    def test_missing_dir_blocks(self):
        rc, composed, _ = _compose(self.dir / "does-not-exist")
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")

    def test_only_composed_files_present_blocks(self):
        _write(self.dir, f"composed-{PHASE}-20260101T000000Z.json",
               _result("composed", "pass"))
        rc, composed, _ = _compose(self.dir)
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")


class GateExitCodeTests(_TempDirCase):
    def test_exit_codes_by_outcome(self):
        cases = [("pass", 0), ("warn", 0), ("iterate", 1),
                 ("clarify", 1), ("gather_evidence", 1), ("block", 2)]
        for outcome, expected_rc in cases:
            with self.subTest(outcome=outcome):
                sub = self.dir / outcome
                sub.mkdir()
                _write(sub, f"a-{PHASE}-20260101T000000Z.json",
                       _result("a", outcome))
                rc, composed, _ = _compose(sub)
                self.assertEqual(composed["outcome"], outcome)
                self.assertEqual(rc, expected_rc)


class InvalidInputTests(_TempDirCase):
    def test_malformed_json_wrapped_not_skipped_no_traceback(self):
        _write(self.dir, f"good-{PHASE}-20260101T000000Z.json",
               _result("good", "pass"))
        _write(self.dir, f"bad-{PHASE}-20260101T000100Z.json", "{not json")
        rc, composed, stderr = _compose(self.dir)
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")
        self.assertNotIn("Traceback", stderr)
        self.assertIn("malformed JSON", stderr)
        kinds = {(f["kind"], f["subject"]) for f in composed["findings"]}
        self.assertIn(
            ("schema_violation", f"bad-{PHASE}-20260101T000100Z.json"), kinds)

    def test_hostile_fixture_rejected_by_real_schema(self):
        rc, composed, stderr = _compose(FIXTURES / "invalid-schema" / "results")
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")
        reason = composed["metadata"]["invalid_results"][0]["reason"]
        self.assertIn("schema validation failed", reason)

    def test_phase_mismatch_is_invalid(self):
        rc, composed, _ = _compose(FIXTURES / "phase-mismatch" / "results")
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")
        reason = composed["metadata"]["invalid_results"][0]["reason"]
        self.assertIn("phase mismatch", reason)

    def test_crash_shaped_payloads_are_wrapped(self):
        # RT4-H7 shapes: finding without id, model_routing without tier,
        # next_action as a string — all schema-invalid, all wrapped.
        payload = _result("weird", "iterate")
        payload["findings"] = [{"severity": "high", "kind": "other",
                                 "subject": "x"}]  # no id
        payload["model_routing"] = {"reason": "no tier here"}
        payload["next_action"] = "iterate please"
        _write(self.dir, f"weird-{PHASE}-20260101T000000Z.json", payload)
        rc, composed, stderr = _compose(self.dir)
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")
        self.assertNotIn("Traceback", stderr)


@unittest.skipUnless(jsonschema, "jsonschema not installed")
class ComposedOutputValidityTests(_TempDirCase):
    def _assert_valid(self, composed):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(instance=composed, schema=schema)

    def test_engine_path_fixture_composes_schema_valid(self):
        # T604 regression: an engine-adapter-shaped result (Spec 002
        # claims) composes to output its own schema accepts — no
        # consumer workarounds, no _evaluator_id, no model_routing:null.
        rc, composed, _ = _compose(FIXTURES / "engine-path" / "results")
        self.assertEqual(rc, 1)  # iterate -> gate exit 1
        self.assertEqual(composed["outcome"], "iterate")
        self._assert_valid(composed)
        self.assertNotIn("model_routing", composed)
        raw = json.dumps(composed)
        self.assertNotIn("_evaluator_id", raw)
        self.assertTrue(
            all(f["id"].startswith("aee:") for f in composed["findings"]))
        self.assertEqual(
            composed["next_action"]["target_phase"], "specify")

    def test_empty_composed_is_schema_valid(self):
        _, composed, _ = _compose(self.dir)
        self._assert_valid(composed)

    def test_summary_respects_schema_cap_with_many_evaluators(self):
        for i in range(12):
            eid = f"evaluator-with-a-rather-long-identifier-{i:02d}"
            _write(self.dir, f"{eid}-{PHASE}-20260101T000000Z.json",
                   _result(eid, "pass"))
        rc, composed, _ = _compose(self.dir)
        self.assertEqual(rc, 0)
        self.assertLessEqual(len(composed["summary"]), 500)
        self._assert_valid(composed)

    def test_model_routing_merged_consistently(self):
        standard = _result("std", "pass", model_routing={
            "recommended_tier": "standard", "reason": "routine",
            "estimated_tokens": 100, "estimated_cost_usd": 1.0,
            "tier_breakdown": {"standard": {"estimated_tokens": 100,
                                            "estimated_cost_usd": 1.0}},
        })
        premium = _result("prm", "warn", model_routing={
            # 300 chars is the schema cap for an input's reason; the
            # composed prefix pushes it past the cap, exercising the
            # composer's own truncation to 300.
            "recommended_tier": "premium", "reason": "x" * 300,
            "estimated_tokens": 50, "estimated_cost_usd": 2.0,
            "tier_breakdown": {"premium": {"estimated_tokens": 50,
                                           "estimated_cost_usd": 2.0}},
            "escalation_triggers": [
                {"condition": "critical finding", "escalate_to": "premium"}],
        })
        _write(self.dir, f"std-{PHASE}-20260101T000000Z.json", standard)
        _write(self.dir, f"prm-{PHASE}-20260101T000100Z.json", premium)
        rc, composed, _ = _compose(self.dir)
        self.assertEqual(rc, 0)
        routing = composed["model_routing"]
        self.assertEqual(routing["recommended_tier"], "premium")
        # Headline numbers and breakdown come from the SAME routing.
        self.assertEqual(routing["estimated_tokens"], 50)
        self.assertEqual(
            routing["tier_breakdown"],
            {"premium": {"estimated_tokens": 50, "estimated_cost_usd": 2.0}})
        self.assertLessEqual(len(routing["reason"]), 300)
        self._assert_valid(composed)


class DedupAndStrategyTests(unittest.TestCase):
    def test_dedup_majority_duplicate_cannot_outvote_block(self):
        rc, composed, _ = _compose(
            FIXTURES / "dedup-majority" / "results", strategy="majority")
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")
        self.assertEqual(composed["metadata"]["evaluator_count"], 2)
        self.assertEqual(
            len(composed["metadata"]["duplicate_results_ignored"]), 1)

    def test_majority_override_is_marked_non_gating(self):
        rc, composed, _ = _compose(
            FIXTURES / "appeal-majority-override" / "results",
            strategy="majority")
        self.assertEqual(rc, 0)
        self.assertEqual(composed["outcome"], "pass")
        self.assertFalse(composed["metadata"]["gating"])
        self.assertTrue(composed["metadata"]["block_overridden"])
        self.assertIn("non_gating_reason", composed["metadata"])
        # The overturned block stays visible as evidence.
        outcomes = {s["evaluator_id"]: s["outcome"]
                    for s in composed["metadata"]["evaluator_results"]}
        self.assertEqual(outcomes["b1"], "block")

    def test_strict_same_inputs_gate_and_block(self):
        rc, composed, _ = _compose(
            FIXTURES / "appeal-majority-override" / "results",
            strategy="strict")
        self.assertEqual(rc, 2)
        self.assertEqual(composed["outcome"], "block")
        self.assertTrue(composed["metadata"]["gating"])
        self.assertNotIn("block_overridden", composed["metadata"])


class DependencyTests(_TempDirCase):
    def test_missing_jsonschema_is_a_hard_error(self):
        stub = self.dir / "stub"
        stub.mkdir()
        (stub / "jsonschema.py").write_text(
            "raise ImportError('blocked by test')\n", encoding="utf-8")
        results = self.dir / "results"
        results.mkdir()
        _write(results, f"a-{PHASE}-20260101T000000Z.json", _result("a", "pass"))
        env = dict(os.environ)
        env["PYTHONPATH"] = str(stub)
        rc, composed, stderr = _compose(results, env=env)
        self.assertEqual(rc, 2)
        self.assertIsNone(composed)
        self.assertIn("jsonschema", stderr)
        self.assertIn("required", stderr)


class DemoTests(unittest.TestCase):
    def test_demo_runs_end_to_end(self):
        proc = subprocess.run(
            [sys.executable, str(DEMO)],
            capture_output=True, text=True, timeout=120,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertIn("COMPOSED RESULT", proc.stdout)
        self.assertIn("BLOCK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
