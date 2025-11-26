"""EXT4 image reader stubs for the recovery tool."""

from __future__ import annotations

from pathlib import Path
from typing import Generator, Iterable, IO, Tuple


class Ext4ImageReader:
    """Stream-oriented ext4 reader for an inner VM disk image.

    The real implementation may rely on pytsk3 or a custom parser to traverse
    directories and files. It must avoid loading the full image into memory and
    instead stream data in manageable chunks.
    """

    def __init__(self, image: Path | IO[bytes]):
        self.image = image

    def list_dir(self, path: str) -> Iterable[str]:
        """List directory entries at ``path`` within the ext4 filesystem."""

        raise NotImplementedError("ext4 directory listing not implemented yet")

    def walk(self, root: str) -> Generator[Tuple[str, bool, int, dict], None, None]:
        """Yield filesystem entries starting at ``root``.

        Each yielded tuple should look like ``(path, is_dir, size, metadata)``.
        The real implementation must stream metadata traversal without reading
        the full tree into memory.
        """

        raise NotImplementedError("ext4 walking not implemented yet")

    def open_file(self, path: str) -> IO[bytes]:
        """Open a file for streamed reading from the ext4 image."""

        raise NotImplementedError("ext4 file access not implemented yet")

