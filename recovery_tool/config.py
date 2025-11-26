"""Configuration utilities for the recovery tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024


@dataclass(slots=True)
class RecoveryConfig:
    """Runtime configuration for the recovery workflow."""

    image_path: Path
    targets: List[str]
    output_path: Path
    chunk_size: int = DEFAULT_CHUNK_SIZE
    verify_hashes: bool = False


def _ensure_path(value: Path | str) -> Path:
    if isinstance(value, Path):
        return value
    return Path(value)


def from_args(args: object) -> RecoveryConfig:
    """Create a :class:`RecoveryConfig` instance from argparse arguments."""

    image_path = _ensure_path(getattr(args, "image"))
    output_path = _ensure_path(getattr(args, "output"))
    targets_raw: Iterable[str] = getattr(args, "targets", [])
    targets = [str(item) for item in targets_raw]

    verify = bool(getattr(args, "verify", False))

    return RecoveryConfig(
        image_path=image_path,
        targets=targets,
        output_path=output_path,
        verify_hashes=verify,
    )
