"""Exercise the instrumented target's invariants on every supported platform."""

import random
import unittest
from pathlib import Path

from fuzz.composer_target import fuzz_one

CORPUS = Path(__file__).resolve().parents[1] / "fuzz" / "corpus"


class ComposerFuzzTargetTests(unittest.TestCase):
    def test_corpus_and_reproducible_mutations(self):
        rng = random.Random(20261016)
        seeds = [path.read_bytes() for path in sorted(CORPUS.iterdir())]
        seeds.extend([b"", b"\xff\xfe", b"null", b"[]"])
        for seed in seeds:
            with self.subTest(seed=seed[:32]):
                fuzz_one(seed)
                for _ in range(8):
                    mutated = bytearray(seed or b"\x00")
                    mutated[rng.randrange(len(mutated))] = rng.randrange(256)
                    fuzz_one(bytes(mutated))
