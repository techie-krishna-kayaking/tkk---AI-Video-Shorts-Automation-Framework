"""Post-upload cleanup utilities."""

from __future__ import annotations

from pathlib import Path

from send2trash import send2trash

from app.utils.logging import get_logger

logger = get_logger(__name__)


def move_files_to_trash(paths: list[Path]) -> tuple[list[Path], list[str]]:
    moved: list[Path] = []
    errors: list[str] = []

    for path in paths:
        if not path.exists():
            continue
        try:
            send2trash(str(path))
            moved.append(path)
            logger.info("cleanup_file_trashed", file=str(path))
        except Exception as exc:
            msg = f"{path}: {exc}"
            errors.append(msg)
            logger.error("cleanup_file_trash_failed", file=str(path), error=str(exc))

    return moved, errors
