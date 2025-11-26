"""Shared typed structures for recovery operations."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class FileEntry(TypedDict):
    """Representation of a filesystem entry discovered during traversal."""

    path: str
    size: int
    is_dir: bool
    sha256: NotRequired[str]

