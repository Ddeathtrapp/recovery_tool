"""Extraction orchestration for converting BTRFS backups into archives."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable, Set

from recovery_tool.archive_writer import ArchiveWriter
from recovery_tool.btrfs_reader import BtrfsParseError, BtrfsReader, DirEntry
from recovery_tool.config import RecoveryConfig
from recovery_tool.logging_utils import get_logger


def run_extraction(config: RecoveryConfig) -> None:
    """High-level extraction flow that emits a ZIP archive."""

    logger = get_logger(__name__)
    if not config.targets:
        logger.warning("No targets were provided; nothing to extract")
        return
    logger.info("Opening BTRFS image: %s", config.image_path)
    archive = ArchiveWriter(config.output_path, logger, verify=config.verify_hashes)

    reader = BtrfsReader(config.image_path, logger)
    reader.enable_raw_mode()
    with reader:
        reader.enable_raw_mode()
        with archive:
            used_prefixes: Set[str] = set()
            for target in config.targets:
                prefix = _derive_prefix(target, used_prefixes)
                logger.info("Exporting %s as %s", target, prefix)
                try:
                    entry = reader.stat_path(target)
                except FileNotFoundError:
                    logger.error("Target not found inside image: %s", target)
                    continue
                except BtrfsParseError as exc:
                    logger.error("Unable to stat %s: %s", target, exc)
                    continue
                if entry.kind == "dir":
                    _export_directory(reader, archive, target, prefix, config.chunk_size, logger)
                elif entry.kind in {"file", "symlink"}:
                    _export_file(reader, archive, target, prefix, entry, config.chunk_size, logger)
                else:
                    logger.warning("Skipping unsupported entry type %s at %s", entry.kind, target)
    if config.verify_hashes:
        archive.verify_contents()


def _export_directory(
    reader: BtrfsReader,
    archive: ArchiveWriter,
    target: str,
    prefix: str,
    chunk_size: int,
    logger,
) -> None:
    base = _normalize_target(target)
    try:
        for path, entry in reader.walk(base):
            rel_path = _relative_path(base, path, prefix)
            if entry.kind == "dir":
                archive.add_directory(rel_path, entry.mode, entry.mtime_ns)
            elif entry.kind == "symlink":
                archive.add_symlink(rel_path, entry.target or "", entry.mode, entry.mtime_ns)
            elif entry.kind == "file":
                _write_streamed_file(reader, archive, path, rel_path, entry, chunk_size, logger)
            else:
                logger.debug("Skipping special entry %s at %s", entry.kind, path)
    except (FileNotFoundError, BtrfsParseError) as exc:
        logger.error("Directory traversal failed for %s: %s", target, exc)


def _export_file(
    reader: BtrfsReader,
    archive: ArchiveWriter,
    target: str,
    prefix: str,
    entry: DirEntry,
    chunk_size: int,
    logger,
) -> None:
    base = _normalize_target(target)
    rel_path = prefix
    if entry.kind == "symlink":
        archive.add_symlink(rel_path, entry.target or "", entry.mode, entry.mtime_ns)
        return
    if entry.kind != "file":
        logger.warning("Skipping non-regular file at %s", target)
        return
    _write_streamed_file(reader, archive, base, rel_path, entry, chunk_size, logger)


def _write_streamed_file(
    reader: BtrfsReader,
    archive: ArchiveWriter,
    source_path: str,
    rel_path: str,
    entry: DirEntry,
    chunk_size: int,
    logger,
) -> None:
    if not _probe_file_readable(reader, source_path, entry, chunk_size, logger):
        return
    try:
        handle = reader.open_file(source_path)
    except (FileNotFoundError, BtrfsParseError) as exc:
        logger.error("Unable to open %s: %s", source_path, exc)
        return
    try:
        archive.add_file(
            rel_path,
            _chunk_stream(handle, chunk_size),
            entry.size,
            entry.mode,
            entry.mtime_ns,
        )
    except BtrfsParseError as exc:
        logger.warning("Skipping %s due to BTRFS parsing error: %s", source_path, exc)
    finally:
        handle.close()


def _probe_file_readable(
    reader: BtrfsReader,
    source_path: str,
    entry: DirEntry,
    chunk_size: int,
    logger,
) -> bool:
    """Ensure the file can be fully read before writing to the archive."""

    try:
        handle = reader.open_file(source_path)
    except (FileNotFoundError, BtrfsParseError) as exc:
        logger.warning("Skipping %s: %s", source_path, exc)
        return False
    total = 0
    try:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
    except BtrfsParseError as exc:
        logger.warning("Skipping %s due to read error: %s", source_path, exc)
        return False
    finally:
        handle.close()

    if total != entry.size:
        logger.warning(
            "Short read for %s: expected %d bytes but only got %d bytes",
            source_path,
            entry.size,
            total,
        )
        return False
    return True


def _chunk_stream(handle, chunk_size: int) -> Iterable[bytes]:
    while True:
        chunk = handle.read(chunk_size)
        if not chunk:
            break
        yield chunk


def _derive_prefix(target: str, used: Set[str]) -> str:
    name = PurePosixPath(target).name
    if not name:
        name = "root"
    base = name
    candidate = base
    counter = 1
    while candidate in used:
        candidate = f"{base}_{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def _normalize_target(path: str) -> str:
    pure = PurePosixPath(path)
    normalized = str(pure)
    if not normalized.startswith("/"):
        normalized = f"/{normalized}" if normalized else "/"
    return normalized or "/"


def _relative_path(root: str, current: str, prefix: str) -> str:
    if root == current:
        return prefix
    suffix = current[len(root) :].lstrip("/")
    return f"{prefix}/{suffix}" if suffix else prefix
