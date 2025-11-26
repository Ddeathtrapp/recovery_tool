"""Minimal progress reporting utilities."""

from __future__ import annotations

import sys
import time
from typing import Optional


class ProgressBar:
    """Lightweight text progress helper.

    Designed for streaming workflows where feedback is useful but full-featured
    progress bars may not be available. Writing to stderr avoids mixing with
    streamed data.
    """

    def __init__(self, total: Optional[int] = None, label: str = "") -> None:
        self.total = total
        self.label = label
        self.current = 0
        self._start_time: float | None = None

    def __enter__(self) -> "ProgressBar":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.finish()

    def start(self) -> None:
        self._start_time = time.time()
        self._render()

    def update(self, increment: int) -> None:
        self.current += increment
        self._render()

    def finish(self) -> None:
        self._render(final=True)
        sys.stderr.write("\n")
        sys.stderr.flush()

    def _render(self, final: bool = False) -> None:
        elapsed = 0.0
        if self._start_time is not None:
            elapsed = time.time() - self._start_time

        if self.total:
            percent = (self.current / self.total) * 100
            message = f"{self.label} {percent:6.2f}% ({self.current}/{self.total})"
        else:
            message = f"{self.label} {self.current} bytes"

        if final and self.total:
            message += " complete"

        sys.stderr.write(f"\r{message} [elapsed: {elapsed:.1f}s]")
        sys.stderr.flush()

