"""Archive writing utilities for streamed Crostini recoveries."""

from __future__ import annotations

import calendar
import hashlib
import json
import logging
import stat
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from recovery_tool.verify import compute_sha256


@dataclass(slots=True)
class ArchiveRecord:
    """Metadata describing one file stored in the archive."""

    name: str
    size: int
    sha256: str


class ArchiveWriter:
    """ZIP archive helper that streams entries without buffering them in RAM."""

    def __init__(self, output_path: Path, logger: logging.Logger, verify: bool = False) -> None:
        self.output_path = Path(output_path)
        self._logger = logger
        self._verify = verify
        self._zip: zipfile.ZipFile | None = None
        self._manifest: List[ArchiveRecord] = []
        self._added_dirs: set[str] = set()
        self._closed = False

    def __enter__(self) -> "ArchiveWriter":
        self._open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    def _open(self) -> None:
        if self._zip is not None:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        compression = zipfile.ZIP_DEFLATED if zipfile.ZIP_DEFLATED else zipfile.ZIP_STORED
        self._zip = zipfile.ZipFile(self.output_path, "w", compression=compression, allowZip64=True)
        self._logger.info("Writing archive to %s", self.output_path)

    def close(self) -> None:
        if self._zip is None or self._closed:
            return
        self._write_manifest()
        self._zip.close()
        self._closed = True

    def add_directory(self, arcname: str, mode: int = 0o755, mtime_ns: int | None = None) -> None:
        name = self._normalize_arcname(arcname)
        if not name.endswith("/"):
            name = f"{name}/"
        if name in self._added_dirs or self._zip is None:
            return
        info = self._build_info(name, mode, mtime_ns)
        info.external_attr = (stat.S_IFDIR | mode) << 16
        self._zip.writestr(info, b"")
        self._added_dirs.add(name)

    def add_symlink(self, arcname: str, target: str, mode: int = 0o777, mtime_ns: int | None = None) -> None:
        name = self._normalize_arcname(arcname)
        if self._zip is None:
            raise RuntimeError("Archive is not open")
        info = self._build_info(name, mode, mtime_ns)
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | mode) << 16
        data = target.encode("utf-8")
        self._zip.writestr(info, data)
        digest = hashlib.sha256(data).hexdigest()
        self._manifest.append(ArchiveRecord(name=name, size=len(data), sha256=digest))

    def add_file(
        self,
        arcname: str,
        data_iter: Iterable[bytes],
        size: int | None,
        mode: int = 0o644,
        mtime_ns: int | None = None,
    ) -> None:
        name = self._normalize_arcname(arcname)
        if self._zip is None:
            raise RuntimeError("Archive is not open")
        info = self._build_info(name, mode, mtime_ns)
        info.external_attr = (stat.S_IFREG | mode) << 16
        hasher = hashlib.sha256()
        written = 0
        with self._zip.open(info, "w") as handle:
            for chunk in data_iter:
                if not chunk:
                    continue
                handle.write(chunk)
                hasher.update(chunk)
                written += len(chunk)
        if size is not None and written != size:
            self._logger.warning(
                "Size mismatch for %s (expected %s bytes, wrote %s bytes)",
                name,
                size,
                written,
            )
        self._manifest.append(ArchiveRecord(name=name, size=written, sha256=hasher.hexdigest()))

    def verify_contents(self) -> None:
        if not self._manifest or not self._verify:
            return
        self._logger.info("Verifying archive contents for %s entries", len(self._manifest))
        with zipfile.ZipFile(self.output_path, "r") as archive:
            for record in self._manifest:
                try:
                    with archive.open(record.name) as entry:
                        digest = compute_sha256(entry)
                except KeyError:
                    self._logger.error("Manifest entry %s missing from archive", record.name)
                    continue
                if digest != record.sha256:
                    self._logger.error("Digest mismatch for %s", record.name)
                    continue
        self._logger.info("Archive verification completed")

    def _normalize_arcname(self, name: str) -> str:
        name = name.replace("\\", "/")
        while "//" in name:
            name = name.replace("//", "/")
        if name.startswith("/"):
            name = name[1:]
        return name or "root"

    def _build_info(self, arcname: str, mode: int, mtime_ns: int | None) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(arcname)
        info.date_time = self._zip_timestamp(mtime_ns)
        return info

    def _zip_timestamp(self, mtime_ns: int | None) -> tuple[int, int, int, int, int, int]:
        if mtime_ns:
            seconds = max(0, int(mtime_ns // 1_000_000_000))
        else:
            seconds = int(time.time())
        min_stamp = calendar.timegm((1980, 1, 1, 0, 0, 0))
        if seconds < min_stamp:
            seconds = min_stamp
        t = time.gmtime(seconds)
        return (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)

    def _write_manifest(self) -> None:
        if not self._manifest or self._zip is None:
            return
        manifest_payload = [
            {"path": record.name, "size": record.size, "sha256": record.sha256}
            for record in self._manifest
        ]
        data = json.dumps(manifest_payload, indent=2, sort_keys=True).encode("utf-8")
        info = self._build_info("MANIFEST.json", 0o644, None)
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        self._zip.writestr(info, data)
