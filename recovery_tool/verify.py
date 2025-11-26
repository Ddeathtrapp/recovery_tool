"""Verification helpers for streamed file reads."""

from __future__ import annotations

import hashlib
from typing import IO

DEFAULT_HASH_CHUNK_SIZE = 1024 * 1024


def compute_sha256(stream: IO[bytes], chunk_size: int = DEFAULT_HASH_CHUNK_SIZE) -> str:
    """Compute a SHA256 digest from a byte stream without loading it all into RAM."""

    digest = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def verify_file(
    expected_size: int, expected_hash: str, stream: IO[bytes], chunk_size: int = DEFAULT_HASH_CHUNK_SIZE
) -> bool:
    """Verify a streamed file against expected size and SHA256 hash."""

    bytes_read = 0
    digest = hashlib.sha256()

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        bytes_read += len(chunk)
        digest.update(chunk)

    if bytes_read != expected_size:
        return False

    return digest.hexdigest() == expected_hash

