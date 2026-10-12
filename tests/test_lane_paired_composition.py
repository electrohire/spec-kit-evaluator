"""Spec 004 P5 evaluator-half tests: lane-paired composition.

An AEE result carrying the lane pair in metadata (the engine's
P5 contract) must compose WITHOUT re-blending: the pair is
carried verbatim per evaluator, lane-2 lag is stated in the
composed summary — including on a pass — and no score is ever
computed from lane-2 state. Lane-less results compose exactly as
before.

Run:  python3 -m unittest tests.test_lane_paired_composition -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE = REPO_ROOT / "scripts" / "python" / "compose_results.py"
PHASE = "after_specify"

LANES = {
    "lane_1": {
        "label": "machine verification",
        "bundle": {"outcome": "pass", "at_or_above_threshold": 2},
    },
    "lane_2": {
        "label": "human acceptance",
        "bundle": {
            "stage_counts": {"created": 0, "checked": 2, "explained": 0,
                             "accepted": 0, "digested": 0},
            "below_explained": 2,
            "verified_unexplained": 1,
        },
    },
}


def _result(eid: str, outcome: str, metadata: dict | None = None) -> dict:
    data = {
        "schema_version": "1.0",
        "evaluator": {"id": eid, "version": "1.0.0"},
        "phase": PHASE,
        "outcome": outcome,
        "summary": f"{eid} summary.",
        "findings": [],
    }
    if metadata is not None:
        data["metadata"] = metadata
    return data


def _compose(directory: Path, files: dict[str, dict]):
    for name, payload in files.items():
        (directory / name).write_text(json.dumps(payload), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(COMPOSE), "--results-dir", str(directory),
         "--phase", PHASE, "--strategy", "strict", "--json"],
        capture_output=True, text=True, timeout=60,
    )
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


def _walk_numbers(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _walk_numbers(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from _walk_numbers(value, f"{path}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield path, obj


class LaneCompositionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_lanes_carried_verbatim_and_lag_stated_on_pass(self):
        aee = _result("aee", "pass", metadata={
            "lanes": LANES,
            "not_understood": ["CAP: no human has explained the mechanism"],
            "reported_statuses": {"CAP": "partially_supported"},
        })
        rc, composed, stderr = _compose(self.dir, {"aee-after_specify-20261012T000000Z.json": aee})
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(composed["outcome"], "pass")
        states = composed["metadata"]["lane_states"]
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["evaluator_id"], "aee")
        self.assertEqual(states[0]["lane_1"], LANES["lane_1"])
        self.assertEqual(states[0]["lane_2"], LANES["lane_2"])
        self.assertEqual(
            states[0]["not_understood"],
            ["CAP: no human has explained the mechanism"],
        )
        # Even on a pass the headline states the lane-2 lag.
        self.assertIn("Lane 2 (human acceptance) lags lane 1", composed["summary"])
        self.assertIn("2 claim(s) below the explained stage", composed["summary"])
        self.assertIn("1 verified-but-unexplained", composed["summary"])
        self.assertIn("not acceptance or digestion", composed["summary"])

    def test_no_score_is_computed_from_lane_2(self):
        aee = _result("aee", "pass", metadata={"lanes": LANES, "not_understood": []})
        rc, composed, stderr = _compose(self.dir, {"aee-after_specify-20261012T000000Z.json": aee})
        self.assertEqual(rc, 0, stderr)
        lane_2_numbers = dict(_walk_numbers(composed["metadata"]["lane_states"][0]["lane_2"]))
        input_numbers = dict(_walk_numbers(LANES["lane_2"]))
        # Every number under lane_2 in the output came from the
        # input record itself — composition computed none.
        self.assertEqual(lane_2_numbers, input_numbers)

    def test_two_lanes_carrying_evaluators_stay_separate(self):
        other = _result("aee-peer", "pass", metadata={
            "lanes": {"lane_1": {"label": "machine verification", "bundle": {}},
                      "lane_2": {"label": "human acceptance",
                                 "bundle": {"below_explained": 0, "verified_unexplained": 0}}},
            "not_understood": [],
        })
        aee = _result("aee", "pass", metadata={"lanes": LANES, "not_understood": []})
        rc, composed, stderr = _compose(self.dir, {"a-after_specify-20261012T000000Z.json": aee, "b-after_specify-20261012T000100Z.json": other})
        self.assertEqual(rc, 0, stderr)
        states = composed["metadata"]["lane_states"]
        self.assertEqual({s["evaluator_id"] for s in states}, {"aee", "aee-peer"})
        # The non-lagging peer contributes no lag language.
        self.assertNotIn("aee-peer:", composed["summary"])

    def test_laneless_results_compose_exactly_as_before(self):
        plain = _result("spec-structure", "pass")
        rc, composed, stderr = _compose(self.dir, {"p-after_specify-20261012T000000Z.json": plain})
        self.assertEqual(rc, 0, stderr)
        self.assertNotIn("lane_states", composed["metadata"])
        self.assertNotIn("Lane 2", composed["summary"])


if __name__ == "__main__":
    unittest.main()
