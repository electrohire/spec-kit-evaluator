"""Reproducible input fuzzing: malformed results must block without mutation."""

import importlib.util
import random
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fuzz_composer", ROOT / "scripts/python/compose_results.py"
)
assert SPEC is not None and SPEC.loader is not None
COMPOSER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPOSER)


class InputFuzzTests(unittest.TestCase):
    def test_generated_malformed_results_fail_closed(self):
        rng = random.Random(20261016)
        seeds = [b"\xff\xfe", b"", b"null", b"[]", b'{"outcome":"pass"}']
        seeds.extend(rng.randbytes(rng.randrange(1, 256)) for _ in range(100))
        schema = COMPOSER._load_schema()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fuzz-after_specify-001.json"
            for seed in seeds:
                for strategy in ("strict", "majority", "optimistic"):
                    with self.subTest(seed=seed[:12], strategy=strategy):
                        path.write_bytes(seed)
                        result = COMPOSER.compose_results(
                            Path(directory), "after_specify", strategy, schema=schema
                        )
                        self.assertEqual(result["outcome"], "block")
                        self.assertIsNone(COMPOSER._schema_problem(result, schema))
                        self.assertEqual(path.read_bytes(), seed)
