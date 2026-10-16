"""Instrument the production composer and fuzz it with Atheris."""

import sys

import atheris

with atheris.instrument_imports():
    from composer_target import fuzz_one

if __name__ == "__main__":
    atheris.Setup(sys.argv, fuzz_one)
    atheris.Fuzz()
