"""Verified file writes for the evaluator's durable outputs.

Vendored implementation of the fleet verified-writes standard
(2026-10-28; canonical text in ``~/workspace/system/safe-write/``):
an output file is written to a temp file in the destination
directory, flushed, fsynced, atomically renamed over the target,
then read back and hash-verified. A 0-byte or partial file never
stands as a successful write. If in-process attempts keep failing
(a process can lose write access for the rest of its life under the
VM write restriction), the write is retried in a fresh subprocess
running this file; if every attempt fails, ``SafeWriteError`` is
raised so the caller fails the run closed instead of reporting an
output that was never durably written.

The evaluator deliberately keeps grading deficient inputs: empty or
malformed artifacts under evaluation are findings, not errors. This
module guards only the evaluator's OWN output writes.
"""

from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

__all__ = [
    "SafeWriteError",
    "sha256_hex",
    "try_write_once",
    "write_file_verified",
    "write_text_verified",
]

# In-process attempts before escalating to a fresh subprocess.
LOCAL_ATTEMPTS = 3
# Subprocess attempts after the local ones.
CHILD_ATTEMPTS = 2
# Overall deadline in seconds; a single write must not hang a run.
DEADLINE_SECONDS = 120.0
# Subprocess timeout in seconds.
CHILD_TIMEOUT_SECONDS = 30


class SafeWriteError(RuntimeError):
    """Every verified-write attempt failed; nothing was committed."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def try_write_once(path: Path, data: bytes) -> bool:
    """One full temp + fsync + rename + read-back attempt."""
    path = Path(path)
    directory = path.parent
    tmp_name: str | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=directory, prefix=".evaluator-verified-", suffix=".tmp"
        )
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        _fsync_dir(directory)
        return path.read_bytes() == data
    except OSError:
        return False
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def _try_child(path: Path, data: bytes) -> bool:
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                base64.b64encode(data).decode("ascii"),
                str(path),
            ],
            capture_output=True,
            timeout=CHILD_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def write_file_verified(path: Path, data: bytes) -> dict:
    """Write ``data`` to ``path`` with the verified-write guarantee.

    Returns ``{"path", "bytes", "sha256", "via"}`` where ``via`` is
    ``local-<n>`` or ``child-<n>``. Raises ``ValueError`` on empty
    content and ``SafeWriteError`` when every attempt fails.
    """
    path = Path(path)
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not data:
        raise ValueError(f"refusing to write an empty file: {path}")
    deadline = time.monotonic() + DEADLINE_SECONDS
    attempts = 0
    for index in range(LOCAL_ATTEMPTS):
        attempts += 1
        if try_write_once(path, data):
            return {
                "path": str(path),
                "bytes": len(data),
                "sha256": sha256_hex(data),
                "via": f"local-{index + 1}",
            }
        if time.monotonic() > deadline:
            break
        time.sleep(0.25 * (index + 1))
    for index in range(CHILD_ATTEMPTS):
        attempts += 1
        if _try_child(path, data):
            return {
                "path": str(path),
                "bytes": len(data),
                "sha256": sha256_hex(data),
                "via": f"child-{index + 1}",
            }
        if time.monotonic() > deadline:
            break
        time.sleep(0.5)
    raise SafeWriteError(
        f"verified write failed after {attempts} attempts: {path} "
        f"({len(data)} bytes, sha256 {sha256_hex(data)})"
    )


def write_text_verified(path: Path, text: str) -> dict:
    return write_file_verified(path, text.encode("utf-8"))


def _self_test() -> int:
    import tempfile as _tempfile

    with _tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "self-test.txt"
        payload = b"safe-write self-test\n"
        result = write_file_verified(target, payload)
        ok = (
            target.read_bytes() == payload
            and result["sha256"] == sha256_hex(payload)
            and result["bytes"] == len(payload)
        )
        print(f"verified_write self-test: {'OK' if ok else 'MISMATCH'} ({result})")
        return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        raise SystemExit(_self_test())
    # Child mode: verified_write.py <base64 payload> <target path>
    _payload = base64.b64decode(sys.argv[1])
    raise SystemExit(0 if try_write_once(Path(sys.argv[2]), _payload) else 1)
