"""Entry point for the Crostini VM recovery tool."""

from __future__ import annotations

import argparse
from pathlib import Path

from recovery_tool import extractor
from recovery_tool.btrfs_reader import BtrfsReader, BtrfsParseError
from recovery_tool.config import RecoveryConfig, from_args
from recovery_tool.logging_utils import get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Crostini VM recovery helper. It can inspect BTRFS images, "
            "guess Crostini container paths, and export selected directories to a ZIP archive."
        )
    )
    parser.add_argument(
        "--image",
        type=Path,
        required=True,
        help="Path to the ChromeOS Crostini backup image (.img).",
    )
    parser.add_argument(
        "--target",
        dest="targets",
        nargs="+",
        default=[],
        help="One or more internal paths to extract from the VM image.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to the output archive (.zip).",
    )
    parser.add_argument(
        "--list-roots",
        action="store_true",
        help="List top-level entries inside the default Crostini subvolume and exit.",
    )
    parser.add_argument(
        "--guess-crostini-root",
        action="store_true",
        help="Attempt to identify an LXD rootfs path inside the image and exit.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Re-read the generated archive and verify recorded SHA256 digests.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logger = get_logger(__name__)

    if args.list_roots or args.guess_crostini_root:
        _handle_inspection(args, logger)
        return

    if not args.targets or not args.output:
        parser.error("--target and --output are required unless using listing options")

    config = from_args(args)
    logger.info("Starting recovery: %s", config)
    extractor.run_extraction(config)


def _handle_inspection(args: argparse.Namespace, logger) -> None:
    reader = BtrfsReader(args.image, logger)
    force_raw = bool(args.guess_crostini_root)
    if force_raw:
        reader.enable_raw_mode()
    try:
        with reader:
            if force_raw:
                reader.enable_raw_mode()
            if args.list_roots:
                _print_roots_with_fallback(reader, logger)
            if args.guess_crostini_root:
                _guess_and_print_targets(reader, logger)
    except OSError as exc:
        logger.error("Failed to open BTRFS image: %s", exc)


def _with_raw_fallback(reader: BtrfsReader, logger, action):
    try:
        return action()
    except BtrfsParseError as exc:
        logger.warning("BTRFS metadata inspection failed: %s", exc)
        logger.warning("Falling back to raw leaf scan + graph reconstruction.")
        reader.enable_raw_mode()
        return action()


def _print_roots_with_fallback(reader: BtrfsReader, logger) -> None:
    try:
        roots = _with_raw_fallback(reader, logger, reader.list_roots)
    except BtrfsParseError as exc:
        logger.error("Unable to list roots even after fallback: %s", exc)
        return
    if not roots:
        logger.warning("No top-level entries discovered")
    for item in roots:
        print(item)


def _guess_and_print_targets(reader: BtrfsReader, logger) -> None:
    reader.enable_raw_mode()
    try:
        guess = _with_raw_fallback(reader, logger, reader.guess_crostini_root)
    except BtrfsParseError as exc:
        logger.error("Unable to guess Crostini root: %s", exc)
        guess = None
    if guess:
        print(guess)
    # Always ensure raw scan before listing targets
    reader.enable_raw_mode()
    suggestions = reader.discover_project_targets()
    if suggestions:
        logger.info("Discovered project/Android directories:")
        for candidate in suggestions:
            print(candidate)
    else:
        logger.warning("No 'projects' or 'Android*' directories found during raw scan")


if __name__ == "__main__":
    main()
