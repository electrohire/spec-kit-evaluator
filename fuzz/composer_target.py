"""Shared file-boundary target for Atheris and portable corpus tests."""

from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.python import compose_results as composer

SCHEMA = composer._load_schema()


def fuzz_one(data: bytes) -> None:
    """Every result must validate; invalid inputs must block without mutation."""
    with TemporaryDirectory(prefix="evaluator-fuzz-") as directory:
        root = Path(directory)
        path = root / "fuzz-after_specify-001.json"
        path.write_bytes(data)
        valid = composer._classify_file(path, "after_specify", SCHEMA)[0] == "valid"
        for strategy in ("strict", "majority", "optimistic"):
            result = composer.compose_results(
                root, "after_specify", strategy, schema=SCHEMA
            )
            problem = composer._schema_problem(result, SCHEMA)
            if problem is not None:
                raise AssertionError(problem)
            if not valid and result["outcome"] != "block":
                raise AssertionError("invalid input did not fail closed")
            if path.read_bytes() != data:
                raise AssertionError("composition mutated its input")
